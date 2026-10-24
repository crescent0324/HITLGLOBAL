"""Resident ownership and contact conversations, separate from care records."""
from contextlib import closing
from pathlib import Path
import json
import secrets
import sqlite3

from care_store import ASSESSORS, stamp
from live import LiveService


def internal_conversation(rid):
    # Preserve old mixed records as staff-only history; never assign a recipient.
    return 'demo-care-' + rid


def backup_before_thread_schema(directory):
    directory = Path(directory)
    facility = directory / 'facility.sqlite3'
    if not facility.exists():
        return
    with closing(sqlite3.connect(facility)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='contact_conversations'").fetchone():
            return
    target = directory / 'backups' / ('before-contact-conversations-' + secrets.token_hex(8))
    target.mkdir(parents=True)
    for name, source in [('facility.sqlite3', facility), ('core.sqlite3', directory / 'core/research.sqlite3')]:
        if source.exists():
            with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(target / name)) as dst:
                src.backup(dst)
    for name in ('environment.json', 'core/integration-environment.json'):
        source = directory / name
        if source.exists():
            (target / source.name).write_bytes(source.read_bytes())
    (target / 'manifest.json').write_text(json.dumps({
        'created_at': stamp(), 'purpose': 'before_contact_conversations',
        'credentials_included': False,
    }), encoding='utf-8')


class ConversationDirectory:
    def __init__(self, store):
        self.store = store
        with store.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS contact_conversations(
                id TEXT PRIMARY KEY, resident_id TEXT NOT NULL, contact_id TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(resident_id,contact_id))''')

    def contact_thread(self, user, rid, contact_id):
        self.store.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('僅限院內工作人員操作。')
        contact = self.store.user(contact_id) if isinstance(contact_id, str) else None
        if not contact or contact['role'] not in {'family', 'resident'} or not self.store.demo_link(contact):
            raise ValueError('請指定有效的模擬 LINE 聯絡人。')
        self.store.require(contact, rid)
        with self.store.db() as db:
            db.execute('INSERT OR IGNORE INTO contact_conversations VALUES(?,?,?,?)',
                       ('care-contact-' + secrets.token_hex(16), rid, contact_id, stamp()))
            return db.execute('SELECT id FROM contact_conversations WHERE resident_id=? AND contact_id=?',
                              (rid, contact_id)).fetchone()['id']

    def describe(self, user, rid, thread_id=None):
        self.store.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('僅限院內工作人員查看對話。')
        if thread_id is None or thread_id == internal_conversation(rid):
            return {'id': internal_conversation(rid), 'kind': 'internal', 'contact_id': None,
                    'label': '院內測試／舊版紀錄', 'active': True, 'recipient': None}
        if not isinstance(thread_id, str):
            raise ValueError('對話識別碼格式不符。')
        with self.store.db() as db:
            row = db.execute('SELECT * FROM contact_conversations WHERE id=? AND resident_id=?',
                             (thread_id, rid)).fetchone()
        if not row:
            raise PermissionError('對話與目前住民不符。')
        contact = self.store.user(row['contact_id'])
        link = self.store.demo_link(contact) if contact else None
        active = bool(contact and contact['role'] in {'family', 'resident'}
                      and link and self.store.allowed(contact, rid))
        return {'id': row['id'], 'kind': 'contact', 'contact_id': row['contact_id'],
                'label': contact['display_name'] if contact else '已停用聯絡人',
                'active': active, 'recipient': link['demo_line_id'] if active else None}

    def list(self, user, rid):
        self.store.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('僅限院內工作人員查看對話。')
        with self.store.db() as db:
            contact_ids = [r['user_id'] for r in db.execute('''SELECT a.user_id FROM access a
                JOIN users u ON u.id=a.user_id JOIN line_links l ON l.user_id=u.id
                WHERE a.resident_id=? AND u.role IN ('family','resident') ORDER BY a.user_id''', (rid,))]
        for contact_id in contact_ids:
            self.contact_thread(user, rid, contact_id)
        with self.store.db() as db:
            ids = [r['id'] for r in db.execute(
                'SELECT id FROM contact_conversations WHERE resident_id=? ORDER BY created_at,id', (rid,))]
        return [self.describe(user, rid)] + [self.describe(user, rid, thread_id) for thread_id in ids]

    def delivery_allowed(self, thread_id):
        if thread_id.startswith('demo-care-'):
            rid = thread_id[len('demo-care-'):]
            return self.store.allowed(self.store.user('admin'), rid)
        with self.store.db() as db:
            row = db.execute('SELECT resident_id,contact_id FROM contact_conversations WHERE id=?', (thread_id,)).fetchone()
        if not row:
            return False
        contact = self.store.user(row['contact_id'])
        return bool(contact and contact['role'] in {'family', 'resident'}
                    and self.store.allowed(contact, row['resident_id']) and self.store.demo_link(contact))


class ScopedLiveService(LiveService):
    """Check current contact authorization at generation and delivery boundaries."""
    def __init__(self, directory, conversations, **kwargs):
        self.conversations = conversations
        super().__init__(directory, **kwargs)

    def _eligible(self, db, job):
        return self.conversations.delivery_allowed(job['conversation_id']) and super()._eligible(db, job)

    def deliver(self, participant, *args, **kwargs):
        with self.lock:
            if not self.conversations.delivery_allowed(participant):
                raise PermissionError('聯絡人配對已撤銷或對話無效，停止回覆。')
            # A logical thread ID is not a LINE recipient. Real routing is a
            # separate integration; even an accidental transport change fails closed.
            with self.db() as db:
                row = db.execute('SELECT transport FROM conversations WHERE id=?', (participant,)).fetchone()
            if not row or row['transport'] != 'simulation':
                raise PermissionError('本版尚未開放真實 LINE 傳送。')
            return super().deliver(participant, *args, **kwargs)
