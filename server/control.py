"""Explicit team delegation and operator controls, separate from private account identity."""
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

WORKSPACE_COOKIE='schimmelpilz_workspace'


def migrate(c):
    columns={r['name'] for r in c.execute('PRAGMA table_info(users)')}
    for name,definition in [('is_admin','INTEGER NOT NULL DEFAULT 0'),('disabled','INTEGER NOT NULL DEFAULT 0'),('control_version','INTEGER NOT NULL DEFAULT 0')]:
        if name not in columns:c.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
    c.executescript('''
        CREATE TABLE IF NOT EXISTS team_members(owner_id TEXT NOT NULL REFERENCES users(id),user_id TEXT NOT NULL REFERENCES users(id),role TEXT NOT NULL,case_ids TEXT,enabled INTEGER NOT NULL DEFAULT 1,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,PRIMARY KEY(owner_id,user_id));
        CREATE TABLE IF NOT EXISTS team_invites(id TEXT PRIMARY KEY,owner_id TEXT NOT NULL REFERENCES users(id),email TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,role TEXT NOT NULL,case_ids TEXT,expires_at TEXT NOT NULL,used_at TEXT,revoked INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS operator_audit(id TEXT PRIMARY KEY,actor_id TEXT NOT NULL REFERENCES users(id),workspace_id TEXT,action TEXT NOT NULL,target TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS operator_settings(id INTEGER PRIMARY KEY CHECK(id=1),ai_enabled INTEGER NOT NULL,registrations_enabled INTEGER NOT NULL,version INTEGER NOT NULL);
        INSERT OR IGNORE INTO operator_settings VALUES(1,1,1,0);
    ''')


def audit(c,actor,workspace,action,target):
    c.execute('INSERT INTO operator_audit VALUES(?,?,?,?,?,?)',(str(uuid.uuid4()),actor,workspace,action,target,datetime.now(UTC).isoformat()))


def membership(c,owner,actor,operator=False):
    if owner==actor:return {'role':'owner','case_ids':None,'version':0}
    if operator:
        if not c.execute('SELECT 1 FROM users WHERE id=?',(owner,)).fetchone():raise HTTPException(404,'Workspace unavailable')
        return {'role':'operator','case_ids':None,'version':0}
    row=c.execute('SELECT * FROM team_members WHERE owner_id=? AND user_id=? AND enabled=1',(owner,actor)).fetchone()
    if not row or not c.execute('SELECT 1 FROM users WHERE id=? AND disabled=0',(owner,)).fetchone():raise HTTPException(403,'workspace_access_revoked')
    return {**dict(row),'case_ids':json.loads(row['case_ids']) if row['case_ids'] is not None else None}


def principal(c,user,request):
    actor=user['id'];owner=request.cookies.get(WORKSPACE_COOKIE) or actor
    request.state.actor_id=actor;request.state.workspace_id=owner
    # Identity, membership management, subscriptions and operator actions always use the real account.
    path=request.url.path
    if path.startswith(('/api/auth/','/api/team','/api/admin','/api/billing')):return user
    member=membership(c,owner,actor,user.get('is_admin',False))
    if owner==actor:return {**user,'actor_id':actor,'workspace_role':'owner','allowed_cases':None}
    if member['role']=='viewer' and request.method not in {'GET','HEAD'}:raise HTTPException(403,'workspace_read_only')
    allowed=member['case_ids']
    if allowed is not None:
        # Case URLs are checked before every module handler. Account-wide endpoints are denied rather than leaking other cases.
        parts=path.split('/')
        case_id=parts[3] if path.startswith('/api/cases/') and len(parts)>3 else None
        if case_id:
            if case_id not in allowed:raise HTTPException(404,'Case not found')
        elif path=='/api/cases' and request.method=='GET':pass
        elif path in {'/api/research/status','/api/cost-reviews/calculate','/api/fee-tables/calculate'}:pass
        elif path.startswith('/api/legal/') and request.method=='GET':pass
        elif path=='/api/tasks/calendar.ics' and request.query_params.get('case_id') in allowed:pass
        elif path.startswith('/api/cost-reviews'):
            target=request.query_params.get('case_id') or getattr(request.state,'payload_case_id',None)
            if len(parts)>3:
                review=c.execute('SELECT case_id FROM cost_reviews WHERE id=? AND user_id=?',(parts[3],owner)).fetchone()
                if review:target=review['case_id']
            if target not in allowed:raise HTTPException(403,'case_not_granted')
        else:raise HTTPException(403,'case_scoped_member_use_case_workspace')
    elif not path.startswith(('/api/cases','/api/contacts','/api/inbox','/api/tasks/','/api/cost-reviews','/api/fee-tables','/api/legal/','/api/research/status')):
        raise HTTPException(403,'personal_account_endpoint')
    owner_row=c.execute('SELECT letterhead_id FROM users WHERE id=?',(owner,)).fetchone()
    return {**user,'id':owner,'actor_id':actor,'workspace_role':member['role'],'allowed_cases':allowed,'letterhead_id':owner_row['letterhead_id']}


class Scope(BaseModel):
    model_config={'extra':'forbid'}
    role:Literal['editor','viewer']='viewer'
    case_ids:list[uuid.UUID]|None=Field(default_factory=list,max_length=200)


class Invite(Scope):
    email:str=Field(min_length=5,max_length=254)
    @field_validator('email')
    @classmethod
    def email_value(cls,value):
        value=value.strip().lower()
        if '@' not in value or any(c.isspace() for c in value):raise ValueError('Invalid email')
        return value


class MemberUpdate(Scope):
    enabled:bool=True
    expected_version:int=Field(ge=1)


class Switch(BaseModel):
    owner_id:uuid.UUID|None=None


class Join(BaseModel):
    token:str=Field(min_length=24,max_length=128)


class UserControl(BaseModel):
    model_config={'extra':'forbid'}
    disabled:bool
    is_admin:bool
    expected_version:int=Field(ge=0)
    reason:str=Field(min_length=10,max_length=500)


class SystemControl(BaseModel):
    ai_enabled:bool
    registrations_enabled:bool
    expected_version:int=Field(ge=0)
    reason:str=Field(min_length=10,max_length=500)


def router(db,require_user,now,system_status=None):
    r=APIRouter()
    def operator(user):
        if not user.get('is_admin'):raise HTTPException(403,'administrator_required')
    def owner(request,user):
        selected=request.cookies.get(WORKSPACE_COOKIE) or user['id']
        if selected!=user['id'] and not user.get('is_admin'):raise HTTPException(403,'workspace_owner_required')
        return selected
    def scope(c,owner_id,values):
        if values is None:return None
        ids=sorted(set(map(str,values)))
        for value in ids:
            if not c.execute('SELECT 1 FROM cases WHERE id=? AND user_id=?',(value,owner_id)).fetchone():raise HTTPException(404,'Case not found')
        return json.dumps(ids)

    @r.get('/api/admin/system')
    def system(user:dict=Depends(require_user)):
        operator(user)
        with db() as c:settings=dict(c.execute('SELECT * FROM operator_settings WHERE id=1').fetchone())
        return {'settings':settings,**(system_status() if system_status else {})}

    @r.put('/api/admin/system')
    def system_update(payload:SystemControl,user:dict=Depends(require_user)):
        operator(user)
        if len(payload.reason.strip())<10:raise HTTPException(422,'Reason required')
        with db() as c:
            result=c.execute('UPDATE operator_settings SET ai_enabled=?,registrations_enabled=?,version=version+1 WHERE id=1 AND version=?',(payload.ai_enabled,payload.registrations_enabled,payload.expected_version))
            if not result.rowcount:raise HTTPException(409,'Settings changed')
            audit(c,user['id'],None,'system_settings_changed',payload.reason.strip())
        return {'saved':True}

    @r.get('/api/team')
    def team(request:Request,user:dict=Depends(require_user)):
        selected=request.cookies.get(WORKSPACE_COOKIE) or user['id']
        with db() as c:
            member=membership(c,selected,user['id'],user.get('is_admin',False))
            choices=[{'owner_id':user['id'],'name':user['organisation'] or user['full_name'],'role':'owner'}]
            choices += [dict(row) for row in c.execute('SELECT m.owner_id,u.organisation AS name,m.role FROM team_members m JOIN users u ON u.id=m.owner_id WHERE m.user_id=? AND m.enabled=1 AND u.disabled=0',(user['id'],))]
            if user.get('is_admin'):
                choices=[{'owner_id':row['id'],'name':row['email'],'role':'operator' if row['id']!=user['id'] else 'owner'} for row in c.execute('SELECT id,email FROM users ORDER BY email')]
            members=[];invites=[]
            if member['role'] in {'owner','operator'}:
                members=[{**dict(row),'case_ids':json.loads(row['case_ids']) if row['case_ids'] is not None else None} for row in c.execute('SELECT m.*,u.email,u.full_name FROM team_members m JOIN users u ON u.id=m.user_id WHERE m.owner_id=?',(selected,))]
                invites=[dict(row) for row in c.execute('SELECT id,email,role,case_ids,expires_at,used_at,revoked FROM team_invites WHERE owner_id=? ORDER BY created_at DESC LIMIT 100',(selected,))]
            return {'selected':selected,'role':member['role'],'case_ids':member['case_ids'],'workspaces':choices,'members':members,'invites':invites}

    @r.post('/api/team/switch')
    def switch(payload:Switch,response:Response,request:Request,user:dict=Depends(require_user)):
        selected=str(payload.owner_id) if payload.owner_id else user['id']
        with db() as c:
            membership(c,selected,user['id'],user.get('is_admin',False))
            audit(c,user['id'],selected,'workspace_selected',selected)
        response.set_cookie(WORKSPACE_COOKIE,selected,httponly=True,samesite='strict',secure=request.url.scheme=='https' or __import__('os').getenv('COOKIE_SECURE','').lower()=='true',path='/',max_age=604800)
        return {'selected':selected}

    @r.post('/api/team/invites')
    def invite(payload:Invite,request:Request,user:dict=Depends(require_user)):
        selected=owner(request,user);token=secrets.token_urlsafe(32);identifier=str(uuid.uuid4())
        with db() as c:
            ids=scope(c,selected,payload.case_ids)
            if payload.email==user['email']:raise HTTPException(422,'Cannot invite yourself')
            c.execute('INSERT INTO team_invites VALUES(?,?,?,?,?,?,?,?,?,?)',(identifier,selected,payload.email,hashlib.sha256(token.encode()).hexdigest(),payload.role,ids,(datetime.now(UTC)+timedelta(hours=48)).isoformat(),None,0,now()))
            audit(c,user['id'],selected,'invite_created',identifier)
        return {'id':identifier,'token':token,'expires_in_hours':48}

    @r.post('/api/team/join')
    def join(payload:Join,user:dict=Depends(require_user)):
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            entry=c.execute('SELECT * FROM team_invites WHERE token_hash=? AND used_at IS NULL AND revoked=0 AND expires_at>?',(hashlib.sha256(payload.token.encode()).hexdigest(),now())).fetchone()
            if not entry or entry['email']!=user['email'] or entry['owner_id']==user['id']:raise HTTPException(404,'Invitation unavailable')
            if not c.execute('SELECT 1 FROM users WHERE id=? AND disabled=0',(entry['owner_id'],)).fetchone():raise HTTPException(404,'Invitation unavailable')
            c.execute('''INSERT INTO team_members VALUES(?,?,?,?,1,1,?) ON CONFLICT(owner_id,user_id) DO UPDATE SET role=excluded.role,case_ids=excluded.case_ids,enabled=1,version=team_members.version+1''',(entry['owner_id'],user['id'],entry['role'],entry['case_ids'],now()))
            c.execute('UPDATE team_invites SET used_at=? WHERE id=?',(now(),entry['id']))
            audit(c,user['id'],entry['owner_id'],'invite_accepted',entry['id'])
        return {'joined':True}

    @r.put('/api/team/members/{identifier}')
    def member_update(identifier:str,payload:MemberUpdate,request:Request,user:dict=Depends(require_user)):
        selected=owner(request,user)
        with db() as c:
            c.execute('BEGIN IMMEDIATE');ids=scope(c,selected,payload.case_ids)
            result=c.execute('UPDATE team_members SET role=?,case_ids=?,enabled=?,version=version+1 WHERE owner_id=? AND user_id=? AND version=?',(payload.role,ids,payload.enabled,selected,identifier,payload.expected_version))
            if not result.rowcount:raise HTTPException(409,'Membership changed')
            # Revoke outstanding invitations too, preventing an old token from restoring revoked access.
            c.execute('UPDATE team_invites SET revoked=1 WHERE owner_id=? AND email=(SELECT email FROM users WHERE id=?)',(selected,identifier))
            audit(c,user['id'],selected,'membership_updated',identifier)
        return {'saved':True}

    @r.post('/api/team/invites/{identifier}/revoke')
    def revoke(identifier:str,request:Request,user:dict=Depends(require_user)):
        with db() as c:
            c.execute('UPDATE team_invites SET revoked=1 WHERE id=? AND owner_id=?',(identifier,owner(request,user)))
            audit(c,user['id'],user['id'],'invite_revoked',identifier)
        return {'revoked':True}

    @r.get('/api/admin')
    def dashboard(user:dict=Depends(require_user)):
        operator(user)
        with db() as c:
            return {'users':[dict(row) for row in c.execute('SELECT id,email,full_name,organisation,audience,is_admin,disabled,control_version,created_at,(SELECT COUNT(*) FROM cases WHERE user_id=users.id) AS case_count FROM users ORDER BY created_at DESC')],
                    'counts':{table:c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ['users','cases','documents','sessions','team_members']},
                    'audit':[dict(row) for row in c.execute('SELECT a.*,u.email AS actor_email FROM operator_audit a JOIN users u ON u.id=a.actor_id ORDER BY a.created_at DESC LIMIT 100')]}

    @r.put('/api/admin/users/{identifier}')
    def user_control(identifier:str,payload:UserControl,user:dict=Depends(require_user)):
        operator(user)
        if identifier==user['id'] and (payload.disabled or not payload.is_admin):raise HTTPException(409,'Cannot disable or demote yourself')
        with db() as c:
            c.execute('BEGIN IMMEDIATE')
            if len(payload.reason.strip())<10:raise HTTPException(422,'Reason required')
            result=c.execute('UPDATE users SET disabled=?,is_admin=?,control_version=control_version+1 WHERE id=? AND control_version=?',(payload.disabled,payload.is_admin,identifier,payload.expected_version))
            if not result.rowcount:raise HTTPException(409,'User changed')
            if not c.execute('SELECT 1 FROM users WHERE is_admin=1 AND disabled=0 LIMIT 1').fetchone():raise HTTPException(409,'At least one active administrator is required')
            if payload.disabled:c.execute('DELETE FROM sessions WHERE user_id=?',(identifier,))
            audit(c,user['id'],None,'user_control',identifier+' · '+payload.reason.strip())
        return {'saved':True}

    @r.post('/api/admin/users/{identifier}/revoke-sessions')
    def sessions(identifier:str,user:dict=Depends(require_user)):
        operator(user)
        with db() as c:
            c.execute('DELETE FROM sessions WHERE user_id=?',(identifier,));audit(c,user['id'],None,'sessions_revoked',identifier)
        return {'revoked':True}
    return r
