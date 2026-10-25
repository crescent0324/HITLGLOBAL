"""Local facility upgrade: snapshot first, then resolve legacy owners without guessing."""
from contextlib import closing
from pathlib import Path
import json
import secrets
import sqlite3
from care_store import ASSESSORS, stamp

OWNER_MIGRATION = 'stable_case_owner_v1'


def backup_before_owner_migration(directory):
    directory = Path(directory)
    facility, core = directory / 'facility.sqlite3', directory / 'core/research.sqlite3'
    if not facility.exists() or not core.exists():
        return
    with closing(sqlite3.connect(core)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='cases'").fetchone():
            return
        has_id = 'operator_id' in {r[1] for r in db.execute('PRAGMA table_info(cases)')}
    with closing(sqlite3.connect(facility)) as db:
        done = db.execute('SELECT value FROM meta WHERE key=?', (OWNER_MIGRATION,)).fetchone()
    if has_id and done:
        return
    target = directory / 'backups' / ('before-stable-case-owner-v1-' + secrets.token_hex(8))
    target.mkdir(parents=True)
    for name, source in [('facility.sqlite3', facility), ('core.sqlite3', core)]:
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target / name)) as dst:
            src.backup(dst)
    for name in ('environment.json', 'core/integration-environment.json'):
        source = directory / name
        if source.exists():
            (target / source.name).write_bytes(source.read_bytes())
    (target / 'manifest.json').write_text(json.dumps({
        'purpose': OWNER_MIGRATION, 'created_at': stamp(), 'credentials_included': False,
    }), encoding='utf-8')


def migrate_case_owner_ids(workflow):
    with workflow.transaction() as db:
        # Include DDL and both attached databases in the same migration transaction.
        db.execute('BEGIN IMMEDIATE')
        if 'operator_id' not in {r['name'] for r in db.execute('PRAGMA table_info(cases)')}:
            db.execute('ALTER TABLE cases ADD COLUMN operator_id TEXT')
        db.execute('''CREATE TABLE IF NOT EXISTS care.case_owner_migrations(
            case_id INTEGER PRIMARY KEY, legacy_operator TEXT, legacy_status TEXT NOT NULL,
            resolved_user_id TEXT, result TEXT NOT NULL, migrated_at TEXT NOT NULL)''')
        if db.execute('SELECT 1 FROM care.meta WHERE key=?', (OWNER_MIGRATION,)).fetchone():
            return
        for case in db.execute('SELECT * FROM cases').fetchall():
            uid = None
            if case['operator_id']:
                matches = db.execute('SELECT id,role FROM care.users WHERE id=?', (case['operator_id'],)).fetchall()
            elif case['operator']:
                # Count every matching account, including non-assessors. A name
                # shared by two accounts is never sufficient identity evidence.
                matches = db.execute('SELECT id,role FROM care.users WHERE display_name=?', (case['operator'],)).fetchall()
            else:
                matches = []
            if len(matches) == 1 and matches[0]['role'] in ASSESSORS:
                uid, result = matches[0]['id'], 'resolved'
            elif len(matches) > 1:
                result = 'ambiguous_display_name'
            elif matches:
                result = 'ineligible_account'
            else:
                result = 'missing_identity' if case['operator'] or case['status'] == 'claimed' else 'no_owner'
            db.execute('INSERT INTO care.case_owner_migrations VALUES(?,?,?,?,?,?)',
                       (case['id'], case['operator'], case['status'], uid, result, stamp()))
            if uid:
                db.execute('UPDATE cases SET operator_id=?,operator=? WHERE id=?', (uid, uid, case['id']))
            elif case['status'] == 'claimed':
                db.execute("UPDATE cases SET status='pending',claimed_at=NULL,operator=NULL,operator_id=NULL WHERE id=?", (case['id'],))
                db.execute("UPDATE care.handoff_requests SET status='cancelled' WHERE case_id=? AND status='pending'", (case['id'],))
                workflow.service.cancel_jobs(db, case['conversation_id'], '舊案件責任身分無法唯一確認，請重新接手；舊草稿失效。')
                workflow.service.log(db, case['conversation_id'], 'case_owner_migration_pending', 'case='+str(case['id'])+'; reason='+result)
        db.execute('INSERT INTO care.meta VALUES(?,?)', (OWNER_MIGRATION, stamp()))
