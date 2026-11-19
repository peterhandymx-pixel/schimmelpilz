"""Create a dedicated local operator account; no default password and no legacy-case claim."""
import argparse
import json
import os
import secrets
import uuid
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True);parser.add_argument('--email',default='admin@schimmelpilz.local')
    parser.add_argument('--promote',metavar='EMAIL',help='make an existing account an administrator instead of creating a new one')
    args=parser.parse_args();folder=Path(args.data_dir).resolve();os.environ['DATA_DIR']=str(folder)
    from . import app as api
    api.init_db()
    if args.promote:
        email=args.promote.strip().lower()
        with api.db() as c:
            row=c.execute('SELECT id,is_admin FROM users WHERE email=?',(email,)).fetchone()
            if not row:raise SystemExit('No account with this email. Register it in the app first.')
            c.execute('UPDATE users SET is_admin=1,control_version=control_version+1 WHERE id=?',(row['id'],))
            api.control.audit(c,row['id'],None,'admin_promoted_locally',email)
        print('Administrator: '+email+'. Enable two-factor sign-in under Kanzlei / Profil, then sign in again to open ADMIN.');return
    output=folder/'admin-access.json'
    with api.db() as c:
        existing=c.execute('SELECT is_admin FROM users WHERE email=?',(args.email,)).fetchone()
        if existing:
            if not existing['is_admin']:raise SystemExit('This email belongs to a non-admin account. Choose another operator email; no account was changed.')
            print('Admin account already exists; credentials and account were not changed.');return
        password=secrets.token_urlsafe(24);salt=secrets.token_hex(16);identifier=str(uuid.uuid4())
        # Write credentials privately before committing the account. No credentials are printed or added to source control.
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x',encoding='utf-8') as stream:json.dump({'email':args.email,'password':password},stream,indent=2)
        try:
            c.execute('INSERT INTO users(id,email,password_hash,salt,audience,full_name,organisation,street,postal_code,city,country,phone,created_at,profile,is_admin) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)',(identifier,args.email,api.password_hash(password,salt),salt,'business','Systemadministration','Schimmelpilz Administration','Nicht angegeben','--','Nicht angegeben','Nicht angegeben','',api.now(),'{}'))
        except Exception:
            output.unlink(missing_ok=True);raise
    print('Dedicated admin created. Private credentials: '+str(output))


if __name__=='__main__':main()
