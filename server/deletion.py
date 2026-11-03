"""Explicit, owner-only permanent deletion of account data.

Rules:
- Only the workspace owner deletes. Team editors/viewers and operators acting in another workspace cannot.
- Deleting a case requires its reference as confirmation.
- Inbox originals belong to the Posteingang: deleting their case document returns the entry to "pending"
  instead of silently discarding the original. Delete the pending entry to remove the file itself.
- A stored file is removed from disk only when no remaining record references it.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException


def require_owner(user):
    if user.get('workspace_role', 'owner') != 'owner':
        raise HTTPException(403, 'workspace_owner_required_for_deletion')


def file_in_use(connection, stored_name):
    return bool(connection.execute('SELECT 1 FROM documents WHERE stored_name=? UNION ALL SELECT 1 FROM inbox_documents WHERE stored_name=? LIMIT 1', (stored_name, stored_name)).fetchone())


def remove_files(folder, names):
    """Called after commit. Deletion failures leave an unreferenced file, never a dangling record."""
    root = Path(folder).resolve()
    for name in names:
        if not name or Path(name).name != name:
            continue
        target = root / name
        try:
            if target.resolve().is_relative_to(root) and target.is_file() and not target.is_symlink():
                target.unlink()
        except OSError:
            pass


def delete_documents(connection, document_ids):
    """Remove case document records and their dependents. Returns stored names that may now be orphaned."""
    stored = []
    for document_id in document_ids:
        row = connection.execute('SELECT stored_name FROM documents WHERE id=?', (document_id,)).fetchone()
        if not row:
            continue
        stored.append(row['stored_name'])
        connection.execute('DELETE FROM inbox_corrections WHERE document_id=? OR old_document_id=?', (document_id, document_id))
        # The inbox keeps its original; the entry becomes assignable again.
        connection.execute('UPDATE inbox_documents SET case_id=NULL,document_id=NULL,assigned_at=NULL,version=version+1 WHERE document_id=?', (document_id,))
        connection.execute('UPDATE cost_reviews SET document_id=NULL WHERE document_id=?', (document_id,))
        connection.execute('DELETE FROM document_ocr_runs WHERE document_id=?', (document_id,))
        connection.execute('DELETE FROM document_auto_text WHERE document_id=?', (document_id,))
        connection.execute('DELETE FROM documents WHERE id=?', (document_id,))
    return [name for name in stored if not file_in_use(connection, name)]


def strip_case_grants(connection, owner_id, case_id):
    for table, key in (('team_members', 'user_id'), ('team_invites', 'id')):
        for row in connection.execute(f'SELECT {key},case_ids FROM {table} WHERE owner_id=? AND case_ids IS NOT NULL', (owner_id,)).fetchall():
            ids = json.loads(row['case_ids'])
            if case_id in ids:
                connection.execute(f'UPDATE {table} SET case_ids=? WHERE owner_id=? AND {key}=?', (json.dumps([value for value in ids if value != case_id]), owner_id, row[key]))


def delete_case(connection, case_id, owner_id):
    documents = [row['id'] for row in connection.execute('SELECT id FROM documents WHERE case_id=?', (case_id,))]
    orphans = delete_documents(connection, documents)
    connection.execute('DELETE FROM inbox_corrections WHERE case_id=? OR from_case_id=?', (case_id, case_id))
    connection.execute('UPDATE inbox_documents SET case_id=NULL,document_id=NULL,assigned_at=NULL,version=version+1 WHERE case_id=?', (case_id,))
    reviews = [row['id'] for row in connection.execute('SELECT id FROM cost_reviews WHERE case_id=?', (case_id,))]
    for review_id in reviews:
        connection.execute('DELETE FROM cost_review_versions WHERE review_id=?', (review_id,))
    connection.execute('DELETE FROM cost_reviews WHERE case_id=?', (case_id,))
    connection.execute('DELETE FROM route_plan_versions WHERE case_id=?', (case_id,))
    connection.execute('DELETE FROM route_plans WHERE case_id=?', (case_id,))
    strip_case_grants(connection, owner_id, case_id)
    # drafts (+versions/checks/events), tasks, activities, research, legal snapshots and contact links cascade.
    connection.execute('DELETE FROM cases WHERE id=? AND user_id=?', (case_id, owner_id))
    return orphans


def delete_account_data(connection, user_id):
    """Everything the account owns. Returns (upload names, letterhead names) to unlink after commit."""
    uploads = []
    for row in connection.execute('SELECT id FROM cases WHERE user_id=?', (user_id,)).fetchall():
        uploads += delete_case(connection, row['id'], user_id)
    inbox = [row['stored_name'] for row in connection.execute('SELECT stored_name FROM inbox_documents WHERE user_id=?', (user_id,))]
    connection.execute('DELETE FROM inbox_corrections WHERE inbox_id IN (SELECT id FROM inbox_documents WHERE user_id=?)', (user_id,))
    connection.execute('DELETE FROM inbox_documents WHERE user_id=?', (user_id,))
    uploads += [name for name in inbox if not file_in_use(connection, name)]
    letterheads = []
    for row in connection.execute('SELECT original_stored,pdf_stored FROM letterheads WHERE user_id=?', (user_id,)):
        letterheads += [row['original_stored'], row['pdf_stored']]
    connection.execute('UPDATE users SET letterhead_id=NULL WHERE id=?', (user_id,))
    connection.execute('DELETE FROM letterheads WHERE user_id=?', (user_id,))
    for statement in (
        'DELETE FROM contacts WHERE user_id=?',
        'DELETE FROM document_ocr_runs WHERE user_id=?',
        'DELETE FROM cost_review_versions WHERE review_id IN (SELECT id FROM cost_reviews WHERE user_id=?)',
        'DELETE FROM cost_reviews WHERE user_id=?',
        'DELETE FROM route_plan_versions WHERE case_id IN (SELECT case_id FROM route_plans WHERE user_id=?)',
        'DELETE FROM route_plans WHERE user_id=?',
        'DELETE FROM team_members WHERE owner_id=?1 OR user_id=?1',
        'DELETE FROM team_invites WHERE owner_id=?',
        'DELETE FROM billing_orders WHERE user_id=?',
        'DELETE FROM subscriptions WHERE user_id=?',
        'DELETE FROM operator_audit WHERE actor_id=?',
        'DELETE FROM sessions WHERE user_id=?',
    ):
        connection.execute(statement, (user_id,))
    for table in ('password_resets', 'email_verifications', 'mfa_recovery_codes', 'mailbox_settings', 'mailbox_messages'):
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            connection.execute(f'DELETE FROM {table} WHERE user_id=?', (user_id,))
    connection.execute('DELETE FROM users WHERE id=?', (user_id,))
    return uploads, letterheads


def router(db, require_user, record_activity, upload_dir, data_dir):
    routes = APIRouter()

    def owned_case(connection, case_id, user):
        row = connection.execute('SELECT * FROM cases WHERE id=? AND user_id=?', (case_id, user['id'])).fetchone()
        if not row or (user.get('allowed_cases') is not None and case_id not in user['allowed_cases']):
            raise HTTPException(404, 'Case not found')
        return row

    @routes.delete('/api/cases/{case_id}', status_code=204)
    def remove_case(case_id: str, confirm: str = '', user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            case = owned_case(connection, case_id, user)
            if confirm.strip().casefold() != case['reference'].casefold():
                raise HTTPException(422, 'case_reference_confirmation_required')
            orphans = delete_case(connection, case_id, user['id'])
        remove_files(upload_dir(), orphans)

    @routes.delete('/api/cases/{case_id}/documents/{document_id}', status_code=204)
    def remove_document(case_id: str, document_id: str, user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            owned_case(connection, case_id, user)
            row = connection.execute('SELECT original_name FROM documents WHERE id=? AND case_id=?', (document_id, case_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Document not found')
            orphans = delete_documents(connection, [document_id])
            record_activity(connection, case_id, 'document_deleted', row['original_name'])
        remove_files(upload_dir(), orphans)

    @routes.delete('/api/cases/{case_id}/drafts/{draft_id}', status_code=204)
    def remove_draft(case_id: str, draft_id: str, expected_version: int, user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            owned_case(connection, case_id, user)
            row = connection.execute('SELECT kind,version FROM drafts WHERE id=? AND case_id=?', (draft_id, case_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Draft not found')
            if row['version'] != expected_version:
                raise HTTPException(409, 'draft_version_conflict')
            connection.execute('DELETE FROM drafts WHERE id=?', (draft_id,))
            record_activity(connection, case_id, 'draft_deleted', f'{row["kind"]} v{row["version"]}')

    @routes.delete('/api/cases/{case_id}/tasks/{task_id}', status_code=204)
    def remove_task(case_id: str, task_id: str, user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            owned_case(connection, case_id, user)
            row = connection.execute('SELECT title FROM tasks WHERE id=? AND case_id=?', (task_id, case_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Task not found')
            connection.execute('DELETE FROM tasks WHERE id=?', (task_id,))
            record_activity(connection, case_id, 'task_deleted', row['title'])

    @routes.delete('/api/contacts/{contact_id}', status_code=204)
    def remove_contact(contact_id: str, expected_version: int, user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT version FROM contacts WHERE id=? AND user_id=?', (contact_id, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Contact not found')
            if row['version'] != expected_version:
                raise HTTPException(409, 'contact_version_conflict')
            connection.execute('DELETE FROM contacts WHERE id=?', (contact_id,))

    @routes.delete('/api/inbox/{identifier}', status_code=204)
    def remove_inbox(identifier: str, expected_version: int, user: dict = Depends(require_user)):
        require_owner(user)
        with db() as connection:
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM inbox_documents WHERE id=? AND user_id=?', (identifier, user['id'])).fetchone()
            if not row:
                raise HTTPException(404, 'Inbox document not found')
            if row['version'] != expected_version:
                raise HTTPException(409, 'Entry changed')
            if row['case_id']:
                raise HTTPException(409, 'inbox_entry_assigned_delete_case_document_first')
            connection.execute('DELETE FROM inbox_corrections WHERE inbox_id=?', (identifier,))
            connection.execute('DELETE FROM inbox_documents WHERE id=?', (identifier,))
            orphans = [row['stored_name']] if not file_in_use(connection, row['stored_name']) else []
        remove_files(upload_dir(), orphans)

    return routes
