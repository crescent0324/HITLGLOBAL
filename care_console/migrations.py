"""Local facility upgrade: snapshot first, then resolve legacy owners without guessing."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import re
from werkzeug.security import generate_password_hash
from care_store import ASSESSORS, DEMO_PASSWORD, stamp
from snapshots import upgrade_snapshot

OWNER_MIGRATION = 'stable_case_owner_v1'
MONITOR_MIGRATION = 'staff_scope_monitor_v2'
MONITOR_INDEX_MIGRATION = 'case_monitor_indexes_v3'


def backup_before_monitor_indexes(directory):
    directory=Path(directory)
    facility,core=directory/'facility.sqlite3',directory/'core/research.sqlite3'
    if not facility.is_file() or not core.is_file():
        return
    with closing(sqlite3.connect(facility)) as db:
        if db.execute('SELECT 1 FROM meta WHERE key=?',(MONITOR_INDEX_MIGRATION,)).fetchone():
            return
    return upgrade_snapshot(directory,'before-case-monitor-indexes-v3',MONITOR_INDEX_MIGRATION)


def migrate_monitor_indexes(workflow):
    with workflow.transaction() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM care.meta WHERE key=?',(MONITOR_INDEX_MIGRATION,)).fetchone():
            return
        db.execute('CREATE INDEX IF NOT EXISTS monitor_cases_by_thread ON cases(conversation_id,id)')
        db.execute('CREATE INDEX IF NOT EXISTS monitor_messages_by_thread ON messages(conversation_id,id)')
        db.execute('INSERT INTO care.meta VALUES(?,?)',(MONITOR_INDEX_MIGRATION,stamp()))


def backup_before_monitor_upgrade(directory):
    directory = Path(directory)
    facility = directory / 'facility.sqlite3'
    if not facility.exists():
        return
    with closing(sqlite3.connect(facility)) as db:
        if db.execute('SELECT 1 FROM meta WHERE key=?', (MONITOR_MIGRATION,)).fetchone():
            return
    return upgrade_snapshot(directory,'before-staff-scope-monitor-v2',MONITOR_MIGRATION)


def migrate_monitor_access(workflow):
    with workflow.transaction() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM care.meta WHERE key=?', (MONITOR_MIGRATION,)).fetchone():
            return
        if 'due_at' not in {r['name'] for r in db.execute('PRAGMA table_info(cases)')}:
            db.execute('ALTER TABLE cases ADD COLUMN due_at TEXT DEFAULT NULL')
        current = stamp()
        # Preserve the old nurses' effective scope once; later revocation survives restart.
        db.execute('''INSERT OR IGNORE INTO care.access(user_id,resident_id)
            SELECT u.id,r.id FROM care.users u CROSS JOIN care.residents r
            WHERE u.role='nurse' AND r.active=1''')
        db.execute('''INSERT OR IGNORE INTO care.staff_role_migrations
            SELECT id,role,? FROM care.users WHERE role='admin' ''', (current,))
        db.execute("UPDATE care.users SET display_name='IT 管理體驗帳號' WHERE role='admin' AND display_name='管理者體驗帳號'")
        head = db.execute("SELECT role FROM care.users WHERE id='head_nurse'").fetchone()
        if head and head['role'] != 'head_nurse':
            raise ValueError('護理長示範帳號 ID 已屬於其他身分，請先核對；不自動提升權限。')
        if not head:
            if db.execute("SELECT 1 FROM care.users WHERE username='head_nurse'").fetchone():
                raise ValueError('護理長示範帳號名稱衝突，請先核對既有身分。')
            db.execute('INSERT INTO care.users VALUES(?,?,?,?,?)',
                       ('head_nurse', 'head_nurse', '護理長體驗帳號', 'head_nurse', generate_password_hash(DEMO_PASSWORD)))
            db.execute('''INSERT OR IGNORE INTO care.access
                SELECT 'head_nurse',id FROM care.residents WHERE active=1 AND id IN ('R001','R002')''')
        # Retain existing audit events without inventing old progress revisions.
        known = {r['id']: dict(r) for r in db.execute('SELECT * FROM cases')}
        actions = {'case_claim','case_reply','case_resolve','case_approve','case_reject',
                   'case_progress_saved','handoff_proposed','handoff_accepted','handoff_cancelled'}
        for row in db.execute('SELECT * FROM care.audit ORDER BY id').fetchall():
            match = re.search(r'(?:^|;)\s*case=(\d+)(?:;|$)', row['detail'])
            case = known.get(int(match[1])) if match and row['action'] in actions else None
            if case:
                db.execute('''INSERT INTO care.case_activity(case_id,actor,action,payload,created_at)
                    VALUES(?,?,?,?,?)''', (case['id'],row['actor'],row['action'],
                    json.dumps({'legacy_audit_id': row['id'], 'legacy': True}),row['created_at']))
        for case in known.values():
            note = db.execute('SELECT * FROM care.case_notes WHERE case_id=?', (case['id'],)).fetchone()
            workflow.activity(db, case['id'], None, 'legacy_snapshot', {
                'legacy': True, 'status': case['status'], 'operator_id': case['operator_id'],
                'progress': dict(note) if note else None, 'close_note': case['close_note'],
            })
            account = db.execute('SELECT role FROM care.users WHERE id=?', (case['operator_id'],)).fetchone()
            if case['status'] == 'claimed' and (not account or account['role'] not in ASSESSORS):
                db.execute("UPDATE cases SET status='pending',operator=NULL,operator_id=NULL,claimed_at=NULL WHERE id=?", (case['id'],))
                db.execute("UPDATE care.handoff_requests SET status='cancelled' WHERE case_id=? AND status='pending'", (case['id'],))
                workflow.service.cancel_jobs(db, case['conversation_id'], '舊合併管理身分已改為 IT，案件須由有權護理師重新接手。')
                workflow.activity(db, case['id'], None, 'role_split_pending', {'previous_operator_id': case['operator_id']})
                workflow.service.log(db, case['conversation_id'], 'case_role_split_pending', 'case='+str(case['id']))
        db.execute('''UPDATE care.handoff_requests SET status='cancelled' WHERE status='pending' AND
            (from_user NOT IN (SELECT id FROM care.users WHERE role='nurse') OR
             to_user NOT IN (SELECT id FROM care.users WHERE role='nurse'))''')
        db.execute('INSERT INTO care.meta VALUES(?,?)', (MONITOR_MIGRATION, current))


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
    return upgrade_snapshot(directory,'before-stable-case-owner-v1',OWNER_MIGRATION)


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
