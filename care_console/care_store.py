"""Facility demo records. Clinical assessments are attributed, never inferred."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import io
import json
import math
import secrets
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

ROLES = {'admin': '管理者', 'nurse': '護理師', 'caregiver': '照服員', 'family': '家屬', 'resident': '住民'}
STAFF = {'admin', 'nurse', 'caregiver'}
ASSESSORS = {'admin', 'nurse'}
STATUSES = {'尚未評估', '一般照護', '需追蹤', '需優先確認'}
CSV_FIELDS = ['resident_code', 'source_record_id', 'observed_at', 'temperature_c',
              'pulse_bpm', 'spo2_pct', 'systolic_mmhg', 'diastolic_mmhg', 'care_status', 'care_note']
VITALS = {'temperature_c': (0, 60), 'pulse_bpm': (0, 400), 'spo2_pct': (0, 100),
          'systolic_mmhg': (0, 400), 'diastolic_mmhg': (0, 300)}
DEMO_PASSWORD = 'CareDemo2026!'

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def parse_time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        raise ValueError('回報時間須為包含時區的 ISO 8601 格式。') from None
    if dt.tzinfo is None:
        raise ValueError('回報時間須包含時區，例如 +08:00。')
    if dt > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError('回報時間不能超過目前時間五分鐘。')
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')

class CareStore:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'facility.sqlite3'
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE,
              display_name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS residents(id TEXT PRIMARY KEY, label TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS beds(id TEXT PRIMARY KEY, ward TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS placements(id INTEGER PRIMARY KEY, resident_id TEXT NOT NULL,
              bed_id TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS occupied_bed ON placements(bed_id) WHERE ended_at IS NULL;
            CREATE UNIQUE INDEX IF NOT EXISTS current_resident_bed ON placements(resident_id) WHERE ended_at IS NULL;
            CREATE TABLE IF NOT EXISTS access(user_id TEXT NOT NULL, resident_id TEXT NOT NULL,
              PRIMARY KEY(user_id,resident_id));
            CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY, resident_id TEXT NOT NULL,
              source_record_id TEXT UNIQUE NOT NULL, observed_at TEXT NOT NULL, received_at TEXT NOT NULL,
              source TEXT NOT NULL, entered_by TEXT NOT NULL, values_json TEXT NOT NULL,
              care_status TEXT NOT NULL, note TEXT NOT NULL, digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, actor TEXT NOT NULL,
              action TEXT NOT NULL, resident_id TEXT, detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS message_authors(event_id TEXT PRIMARY KEY, resident_id TEXT NOT NULL,
              actor TEXT NOT NULL, channel TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS line_links(user_id TEXT PRIMARY KEY, demo_line_id TEXT UNIQUE NOT NULL,
              confirmed_by TEXT NOT NULL, confirmed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
        self.seed()
        self.ensure_shift_account()

    def ensure_shift_account(self):
        # Add an independent colleague without resetting existing demo passwords.
        with self.db() as db:
            if not db.execute("SELECT 1 FROM users WHERE id='nurse2'").fetchone():
                db.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                           ('nurse2', 'nurse2', '接班護理師體驗帳號', 'nurse', generate_password_hash(DEMO_PASSWORD)))
                db.execute('INSERT INTO line_links VALUES(?,?,?,?)',
                           ('nurse2', 'demo-line-nurse2', 'admin', stamp()))

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def seed(self):
        with self.db() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='seeded'").fetchone():
                return
            for role, name in ROLES.items():
                db.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                           (role, role, name + '體驗帳號', role, generate_password_hash(DEMO_PASSWORD)))
            for i in range(1, 7):
                rid, bid = f'R{i:03}', f'A10{i}'
                db.execute('INSERT INTO residents(id,label) VALUES(?,?)', (rid, f'示範住民 {i:02}'))
                db.execute('INSERT INTO beds VALUES(?,?)', (bid, 'A 區'))
                db.execute('INSERT INTO placements(resident_id,bed_id,started_at) VALUES(?,?,?)', (rid, bid, stamp()))
            for bid in ('A107', 'A108'):
                db.execute('INSERT INTO beds VALUES(?,?)', (bid, 'A 區'))
            for role in ('family', 'resident'):
                db.execute('INSERT INTO access VALUES(?,?)', (role, 'R001'))
            for rid in ('R001', 'R002'):
                db.execute('INSERT INTO access VALUES(?,?)', ('caregiver', rid))
            for role in ROLES:
                db.execute('INSERT INTO line_links VALUES(?,?,?,?)', (role, 'demo-line-' + role, 'admin', stamp()))
            db.execute("INSERT INTO meta VALUES('seeded','1')")
        for i, status in enumerate(('一般照護', '需追蹤', '尚未評估', '需優先確認'), 1):
            self.add_observation(self.user('nurse'), f'R{i:03}', {
                'source_record_id': f'DEMO-{i}',
                'observed_at': (datetime.now(timezone.utc) - timedelta(minutes=i * 12)).isoformat(),
                'temperature_c': '36.7', 'pulse_bpm': '76', 'spo2_pct': '97',
                'systolic_mmhg': '128', 'diastolic_mmhg': '78',
                'care_status': status, 'care_note': '虛構院內紀錄，用於體驗來源、時效與人工追蹤；不代表實際健康評估。'
            }, '模擬院內資料')

    def user(self, uid):
        with self.db() as db:
            row = db.execute('SELECT id,username,display_name,role FROM users WHERE id=?', (uid,)).fetchone()
        return dict(row) if row else None

    def authenticate(self, username, password):
        with self.db() as db:
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        return self.user(row['id']) if row and check_password_hash(row['password_hash'], password) else None

    def allowed(self, user, rid):
        if not user:
            return False
        with self.db() as db:
            if not db.execute('SELECT 1 FROM residents WHERE id=? AND active=1', (rid,)).fetchone():
                return False
            return user['role'] in {'admin', 'nurse'} or bool(db.execute(
                'SELECT 1 FROM access WHERE user_id=? AND resident_id=?', (user['id'], rid)).fetchone())

    def require(self, user, rid):
        if not self.allowed(user, rid):
            raise PermissionError('無權查看或操作這位住民。')

    def residents(self, user):
        with self.db() as db:
            rows = db.execute('''SELECT r.id,r.label,p.bed_id,b.ward FROM residents r
              LEFT JOIN placements p ON p.resident_id=r.id AND p.ended_at IS NULL
              LEFT JOIN beds b ON b.id=p.bed_id WHERE r.active=1 ORDER BY p.bed_id,r.id''').fetchall()
        return [dict(r) for r in rows if self.allowed(user, r['id'])]

    def observations(self, user, rid, limit=30):
        self.require(user, rid)
        with self.db() as db:
            rows = db.execute('SELECT * FROM observations WHERE resident_id=? ORDER BY observed_at DESC,id DESC LIMIT ?', (rid, limit)).fetchall()
        return [dict(r) | {'values': json.loads(r['values_json'])} for r in rows]

    def latest_assessment(self, user, rid):
        self.require(user, rid)
        # A newer unassessed measurement does not resolve a recorded concern.
        # Select from all history, not the most recent 30 observation rows.
        with self.db() as db:
            row = db.execute('''SELECT o.id,o.source_record_id,o.observed_at,o.source,
                o.entered_by,o.care_status,o.note,u.display_name AS entered_name
                FROM observations o JOIN users u ON u.id=o.entered_by
                WHERE o.resident_id=? AND o.care_status!='尚未評估'
                  AND u.role IN ('admin','nurse')
                ORDER BY o.observed_at DESC,o.id DESC LIMIT 1''', (rid,)).fetchone()
        return dict(row) if row else None

    def log(self, db, user, action, rid, detail):
        db.execute('INSERT INTO audit(actor,action,resident_id,detail,created_at) VALUES(?,?,?,?,?)',
                   (user['id'], action, rid, detail, stamp()))

    def validated_observation(self, user, rid, data):
        self.require(user, rid)
        if user['role'] not in STAFF:
            raise PermissionError('照護回報僅限工作人員操作。')
        status = str(data.get('care_status', '尚未評估'))
        if status not in STATUSES:
            raise ValueError('回報狀態無效。')
        if user['role'] not in ASSESSORS and status != '尚未評估':
            raise PermissionError('照服員可記錄觀察；評估狀態由護理師確認。')
        note = data.get('care_note', '')
        if not isinstance(note,str) or len(note) > 2000:
            raise ValueError('回報內容最多 2000 字。')
        note = note.strip()
        if status in {'需追蹤','需優先確認'} and not note:
            raise ValueError('請記錄需要追蹤或優先確認的原因。')
        values = {}
        for key, bounds in VITALS.items():
            raw = data.get(key)
            if raw is None or str(raw).strip() == '':
                values[key] = None
                continue
            try:
                value = float(raw)
            except (ValueError, TypeError):
                raise ValueError('量測欄位須為數字，未知時請留白。') from None
            if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
                raise ValueError('量測資料超出可儲存範圍，請確認數值與單位。')
            values[key] = value
        record_id = str(data.get('source_record_id') or 'MANUAL-' + secrets.token_hex(12)).strip()
        if not record_id or len(record_id) > 120:
            raise ValueError('來源紀錄識別碼最多 120 字。')
        normalized = {'resident_id': rid, 'source_record_id': record_id,
                      'observed_at': parse_time(data.get('observed_at')), 'values': values,
                      'care_status': status, 'note': note}
        normalized['digest'] = hashlib.sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return normalized

    def add_observation(self, user, rid, data, source='工作人員測試回報'):
        row = self.validated_observation(user, rid, data)
        with self.db() as db:
            return self._insert_observation(db, user, row, source)

    def _insert_observation(self, db, user, row, source):
        previous = db.execute('SELECT digest FROM observations WHERE source_record_id=?', (row['source_record_id'],)).fetchone()
        if previous:
            if previous['digest'] != row['digest']:
                raise ValueError('來源紀錄識別碼已存在但內容不同，請用新的識別碼記錄更正。')
            return False
        db.execute('''INSERT INTO observations(resident_id,source_record_id,observed_at,received_at,
          source,entered_by,values_json,care_status,note,digest) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                   (row['resident_id'], row['source_record_id'], row['observed_at'], stamp(), source,
                    user['id'], json.dumps(row['values']), row['care_status'], row['note'], row['digest']))
        self.log(db, user, 'observation_added', row['resident_id'], 'source=' + source)
        return True

    def import_csv(self, user, text):
        if user['role'] not in ASSESSORS:
            raise PermissionError('資料匯入僅限管理者或護理師。')
        reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
        if not reader.fieldnames or set(reader.fieldnames) != set(CSV_FIELDS) or len(reader.fieldnames) != len(CSV_FIELDS):
            raise ValueError('CSV 欄位不符，請使用提供的範本。')
        rows = list(reader)
        if not rows or len(rows) > 500:
            raise ValueError('每次匯入須有 1 至 500 筆資料。')
        normalized = []
        for i, row in enumerate(rows, 2):
            try:
                if None in row or any(v is None for v in row.values()):
                    raise ValueError('CSV 欄位數不符。')
                if not row['source_record_id'].strip():
                    raise ValueError('來源紀錄識別碼不可留白。')
                normalized.append(self.validated_observation(user, row['resident_code'], row))
            except (ValueError, PermissionError) as exc:
                raise ValueError(f'第 {i} 列：{exc}') from None
        inserted = 0
        with self.db() as db:
            for row in normalized:
                inserted += self._insert_observation(db, user, row, '院內測試 CSV 匯入')
            self.log(db, user, 'csv_imported', None, f'inserted={inserted}; skipped={len(rows)-inserted}; demo=true')
        return {'inserted': inserted, 'skipped': len(rows) - inserted}

    def move(self, user, rid, bid):
        if user['role'] not in ASSESSORS:
            raise PermissionError('床位異動僅限管理者或護理師。')
        self.require(user, rid)
        with self.db() as db:
            if not db.execute('SELECT 1 FROM beds WHERE id=?', (bid,)).fetchone():
                raise ValueError('床位不存在。')
            occupant = db.execute('SELECT resident_id FROM placements WHERE bed_id=? AND ended_at IS NULL', (bid,)).fetchone()
            if occupant and occupant['resident_id'] != rid:
                raise ValueError('目的床位已有住民，不能覆寫。')
            if occupant:
                return
            db.execute('UPDATE placements SET ended_at=? WHERE resident_id=? AND ended_at IS NULL', (stamp(), rid))
            db.execute('INSERT INTO placements(resident_id,bed_id,started_at) VALUES(?,?,?)', (rid, bid, stamp()))
            self.log(db, user, 'bed_changed', rid, 'new_bed=' + bid)

    def bindings(self, user):
        if user['role'] != 'admin':
            raise PermissionError('帳號授權僅限管理者操作。')
        with self.db() as db:
            return {'users': [dict(r) for r in db.execute('SELECT id,username,display_name,role FROM users')],
                    'access': [dict(r) for r in db.execute('SELECT * FROM access')],
                    'line_links': [dict(r) for r in db.execute('SELECT * FROM line_links')],
                    'residents': [dict(r) for r in db.execute('SELECT id,label FROM residents WHERE active=1')],
                    'beds': [dict(r) for r in db.execute('SELECT * FROM beds')]}

    def beds(self, user):
        if user['role'] not in ASSESSORS:
            raise PermissionError('床位異動僅限管理者或護理師。')
        with self.db() as db:
            return [dict(r) for r in db.execute('''SELECT b.id,b.ward,p.resident_id
                FROM beds b LEFT JOIN placements p ON p.bed_id=b.id AND p.ended_at IS NULL ORDER BY b.id''')]

    def grant(self, user, target, rid, allowed):
        if user['role'] != 'admin':
            raise PermissionError('帳號授權僅限管理者操作。')
        if not self.user(target):
            raise ValueError('帳號不存在。')
        self.require(user, rid)
        with self.db() as db:
            if allowed:
                db.execute('INSERT OR IGNORE INTO access VALUES(?,?)', (target, rid))
            else:
                db.execute('DELETE FROM access WHERE user_id=? AND resident_id=?', (target, rid))
            self.log(db, user, 'access_granted' if allowed else 'access_revoked', rid, 'target=' + target)

    def audit(self, user, rid):
        self.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('操作稽核僅限護理師或照護管理人員。')
        with self.db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM audit WHERE resident_id=? ORDER BY id DESC LIMIT 40', (rid,))]

    def record_author(self, user, rid, event_id, channel):
        self.require(user, rid)
        with self.db() as db:
            db.execute('INSERT INTO message_authors VALUES(?,?,?,?,?)', (event_id, rid, user['id'], channel, stamp()))

    def authors(self, user, rid):
        self.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('訊息身分僅限護理師或照護管理人員。')
        with self.db() as db:
            return {r['event_id']: dict(r) for r in db.execute('''SELECT m.event_id,m.actor,m.channel,u.display_name
              FROM message_authors m JOIN users u ON u.id=m.actor WHERE resident_id=?''', (rid,))}

    def demo_link(self, user):
        with self.db() as db:
            row = db.execute('SELECT * FROM line_links WHERE user_id=?', (user['id'],)).fetchone()
        return dict(row) if row else None

    def line_contacts(self, user, rid):
        self.require(user, rid)
        if user['role'] not in ASSESSORS:
            raise PermissionError('LINE 訊息模擬僅限管理者或護理師。')
        with self.db() as db:
            return [dict(r) for r in db.execute('''SELECT u.id,u.display_name,u.role FROM users u
                JOIN access a ON a.user_id=u.id JOIN line_links l ON l.user_id=u.id
                WHERE a.resident_id=? AND u.role IN ('family','resident') ORDER BY u.role,u.id''', (rid,))]
