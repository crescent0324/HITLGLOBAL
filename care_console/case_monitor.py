"""Read-only, resident-scoped case monitoring; no message bodies or implied deadlines."""
from datetime import datetime, timezone
import hashlib
import json
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.exceptions import Conflict, NotFound
from care_store import stamp
from workflow import ORIGINS


class CaseMonitor:
    def __init__(self, workflow, secret):
        self.workflow, self.store = workflow, workflow.store
        self.tokens = URLSafeTimedSerializer(secret, salt='case-monitor-v1')

    def scope(self, db, user):
        account = db.execute('SELECT role FROM care.users WHERE id=?', (user['id'],)).fetchone()
        if not account or account['role'] != 'head_nurse':
            raise PermissionError('案件監控僅限已授權護理長。')
        return [r['id'] for r in db.execute('''SELECT r.id FROM care.residents r
            JOIN care.access a ON a.resident_id=r.id WHERE a.user_id=? AND r.active=1 ORDER BY r.id''', (user['id'],))]

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    @staticmethod
    def fingerprint(rows):
        # Exactly the original JSON list hash, streamed one row at a time. Keeping all
        # scoped fields avoids weakening cursor invalidation to MAX(time)/COUNT alone.
        digest=hashlib.sha256();digest.update(b'[')
        for index,row in enumerate(rows):
            if index:
                digest.update(b', ')
            digest.update(json.dumps(dict(row),sort_keys=True,ensure_ascii=False).encode())
        digest.update(b']')
        return digest.hexdigest()

    @staticmethod
    def statistics(db, query, values):
        query=query.removesuffix(' ORDER BY c.id DESC')
        valid="""handoff_id IS NOT NULL AND status='claimed' AND owner_role='nurse'
            AND owner_access=1 AND operator_id=from_user AND target_role='nurse'
            AND target_access=1 AND handoff_message=latest_message"""
        row=db.execute('''SELECT COUNT(*) AS total_cases,
            COALESCE(SUM(status IN ('pending','claimed')),0) AS open_cases,
            COALESCE(SUM(status='pending'),0) AS pending_cases,
            COALESCE(SUM(status='claimed'),0) AS claimed_cases,
            COALESCE(SUM(status='closed'),0) AS closed_cases,
            COALESCE(SUM(CASE WHEN '''+valid+''' THEN 1 ELSE 0 END),0) AS pending_handoffs,
            COALESCE(SUM(handoff_id IS NOT NULL AND NOT COALESCE(('''+valid+'''),0)),0) AS stale_handoffs,
            COALESCE(SUM(due_at IS NULL),0) AS deadline_unset
            FROM ('''+query+')',values).fetchone()
        return dict(row)|{'overdue_cases':None}

    @staticmethod
    def parameters(args, timeline=False):
        allowed = {'cursor','limit'} if timeline else {'status','owner_id','from','to','cursor','limit'}
        if set(args) - allowed or any(len(args.getlist(k)) != 1 for k in args):
            raise ValueError('查詢欄位不符或重複。')
        raw = args.get('limit', '10' if not timeline else '20')
        if not raw.isascii() or not raw.isdigit() or not 1 <= int(raw) <= 50:
            raise ValueError('每頁筆數須為 1 至 50。')
        result = {'limit': int(raw)}
        if timeline:
            return result
        result['status'] = args.get('status', 'open')
        if result['status'] not in {'open','all','pending','claimed','closed'}:
            raise ValueError('案件狀態篩選無效。')
        result['owner_id'] = args.get('owner_id', '')
        if len(result['owner_id']) > 80:
            raise ValueError('責任帳號識別碼過長。')
        for key in ('from','to'):
            value = args.get(key, '')
            if value:
                try:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    if dt.tzinfo is None:
                        raise ValueError()
                    value = dt.astimezone(timezone.utc).isoformat(timespec='seconds')
                except (ValueError, OverflowError):
                    raise ValueError('時間篩選須包含時區。') from None
            result[key] = value
        if result['from'] and result['to'] and result['from'] > result['to']:
            raise ValueError('開始時間不能晚於結束時間。')
        return result

    def query(self, user, filters=None, case_id=None):
        # SQL joins authorization before selecting case or progress data.
        query = '''WITH scope AS (
            SELECT r.id,r.label,p.bed_id,b.ward FROM care.residents r
            JOIN care.access a ON a.resident_id=r.id AND a.user_id=?
            JOIN care.users viewer ON viewer.id=a.user_id AND viewer.role='head_nurse'
            LEFT JOIN care.placements p ON p.resident_id=r.id AND p.ended_at IS NULL
            LEFT JOIN care.beds b ON b.id=p.bed_id WHERE r.active=1),
          threads AS (
            SELECT s.*,'demo-care-'||s.id AS thread_id,NULL AS contact_id,'院內測試／舊版紀錄' AS contact_name,1 AS contact_active,'internal' AS kind FROM scope s
            UNION ALL
            SELECT s.*,t.id,t.contact_id,COALESCE(u.display_name,'已停用聯絡人'),
              CASE WHEN u.role IN ('family','resident') AND l.user_id IS NOT NULL AND ca.user_id IS NOT NULL THEN 1 ELSE 0 END,'contact'
            FROM scope s JOIN care.contact_conversations t ON t.resident_id=s.id
            LEFT JOIN care.users u ON u.id=t.contact_id LEFT JOIN care.line_links l ON l.user_id=u.id
            LEFT JOIN care.access ca ON ca.user_id=u.id AND ca.resident_id=s.id)
          SELECT c.*,t.id AS resident_id,t.label,t.bed_id,t.ward,t.contact_id,t.contact_name,t.contact_active,t.kind,
            u.display_name AS owner_name,u.role AS owner_role,
            CASE WHEN oa.user_id IS NOT NULL THEN 1 ELSE 0 END AS owner_access,
            n.summary,n.next_action,n.waiting_for,n.revision,n.updated_at AS progress_at,
            h.id AS handoff_id,h.from_user,h.to_user,h.message_id AS handoff_message,h.created_at AS handoff_at,
            fu.display_name AS from_name,tu.display_name AS to_name,tu.role AS target_role,
            CASE WHEN ta.user_id IS NOT NULL THEN 1 ELSE 0 END AS target_access,
            (SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=c.conversation_id) AS latest_message,
            (SELECT COALESCE(MAX(id),0) FROM care.case_activity WHERE case_id=c.id) AS last_activity
          FROM threads t JOIN cases c ON c.conversation_id=t.thread_id
          LEFT JOIN care.users u ON u.id=c.operator_id
          LEFT JOIN care.access oa ON oa.user_id=u.id AND oa.resident_id=t.id
          LEFT JOIN care.case_notes n ON n.case_id=c.id
          LEFT JOIN care.handoff_requests h ON h.case_id=c.id AND h.status='pending'
          LEFT JOIN care.users fu ON fu.id=h.from_user LEFT JOIN care.users tu ON tu.id=h.to_user
          LEFT JOIN care.access ta ON ta.user_id=tu.id AND ta.resident_id=t.id WHERE 1=1'''
        values = [user['id']]
        if case_id is not None:
            query += ' AND c.id=?'
            values.append(case_id)
        if filters:
            status = filters['status']
            if status == 'open':
                query += " AND c.status IN ('pending','claimed')"
            elif status != 'all':
                query += ' AND c.status=?'
                values.append(status)
            if filters['owner_id'] == '__unassigned__':
                query += ' AND c.operator_id IS NULL'
            elif filters['owner_id']:
                query += ' AND c.operator_id=?'
                values.append(filters['owner_id'])
            for key, comparison in [('from','>='),('to','<=')]:
                if filters[key]:
                    query += ' AND julianday(c.created_at) '+comparison+' julianday(?)'
                    values.append(filters[key])
        return query + ' ORDER BY c.id DESC', values

    @staticmethod
    def item(row, detailed=False):
        owner_valid = bool(row['owner_role'] == 'nurse' and row['owner_access'])
        handoff = None
        if row['handoff_id']:
            stale = row['handoff_message'] != row['latest_message']
            valid = bool(not stale and row['status']=='claimed' and owner_valid and
                         row['operator_id']==row['from_user'] and row['target_role']=='nurse' and row['target_access'])
            handoff = {'id':row['handoff_id'],'from_user':row['from_user'],'from_name':row['from_name'],
                       'to_user':row['to_user'],'to_name':row['to_name'],'created_at':row['handoff_at'],
                       'stale':stale,'valid':valid,'message_id':row['handoff_message']}
        progress = None if row['revision'] is None else {
            'next_action':row['next_action'],'waiting_for':row['waiting_for'],
            'revision':row['revision'],'updated_at':row['progress_at']}
        if progress and detailed:
            progress['summary'] = row['summary']
        return {'id':row['id'],'status':row['status'],'conversation_id':row['conversation_id'],
                'conversation_kind':row['kind'],'resident':{'id':row['resident_id'],'label':row['label'],
                'bed_id':row['bed_id'],'ward':row['ward']},
                'contact':{'id':row['contact_id'],'name':row['contact_name'],'active':bool(row['contact_active'])},
                'owner':{'id':row['operator_id'],'name':row['owner_name'],'valid':owner_valid} if row['operator_id'] else None,
                'origin':row['origin'],'reason':ORIGINS.get(row['origin'],'既有案件待確認'),
                'message_risk':row['trigger_risk'],'created_at':row['created_at'],'claimed_at':row['claimed_at'],
                'closed_at':row['closed_at'],'close_note':row['close_note'] if detailed else None,
                'progress':progress,'handoff':handoff,'due_at':row['due_at'],
                'deadline_status':'unset' if row['due_at'] is None else 'unverified', 'overdue':None}

    def cursor(self, raw, context):
        if not raw:
            return None
        try:
            token = self.tokens.loads(raw, max_age=900)
        except SignatureExpired:
            raise Conflict('分頁已過期，請從第一頁重新查詢。') from None
        except BadSignature:
            raise ValueError('分頁識別碼無效。') from None
        if not isinstance(token, dict) or any(token.get(k) != v for k,v in context.items()):
            raise Conflict('資料、範圍或篩選已更新，請從第一頁重新查詢。')
        if type(token.get('after')) is not int or token['after'] < 1:
            raise ValueError('分頁識別碼無效。')
        return token['after']

    def list(self, user, args):
        filters = self.parameters(args)
        with self.workflow.transaction() as db:
            db.execute('BEGIN')
            scope = self.scope(db, user)
            query, values = self.query(user, filters)
            revision = self.fingerprint(db.execute(query, values))
            # Fingerprints contain scoped metadata only; no family message text is loaded.
            context = {'kind':'list','uid':user['id'],'scope':self.digest(scope),
                       'filters':filters,'revision':revision}
            after = self.cursor(args.get('cursor'), context)
            page_values = list(values)
            page_query = 'SELECT * FROM ('+query+') WHERE 1=1'
            if after:
                page_query += ' AND id<?'
                page_values.append(after)
            page_query += ' ORDER BY id DESC LIMIT ?'
            page_values.append(filters['limit']+1)
            page = [dict(r) for r in db.execute(page_query,page_values)]
            stats = self.statistics(db,query,values)
            owners = [dict(r) for r in db.execute('''SELECT operator_id AS id,owner_name AS name
                FROM ('''+query.removesuffix(' ORDER BY c.id DESC')+''')
                WHERE operator_id IS NOT NULL GROUP BY operator_id,owner_name ORDER BY operator_id''',values)]
        next_cursor = self.tokens.dumps(context | {'after':page[filters['limit']-1]['id']}) if len(page)>filters['limit'] else None
        return {'cases':[self.item(r) for r in page[:filters['limit']]],'stats':stats,'filters':filters,
                'owners':owners,
                'scope_resident_ids':scope,'next_cursor':next_cursor,'updated_at':stamp(),
                'statistics_note':'交班待接受包含於已接手案件，不與已接手數相加。',
                'deadline_note':'機構時限未確認；未設定期限不判定逾期。'}

    def timeline(self, user, case_id, args):
        filters = self.parameters(args, timeline=True)
        with self.workflow.transaction() as db:
            db.execute('BEGIN')
            scope = self.scope(db,user)
            query, values = self.query(user,case_id=case_id)
            row = db.execute(query,values).fetchone()
            if not row:
                raise NotFound('案件不存在或不在授權範圍內。')
            row = dict(row)
            context = {'kind':'timeline','uid':user['id'],'case':case_id,'scope':self.digest(scope),
                       'limit':filters['limit'],'revision':self.digest(row)}
            after = self.cursor(args.get('cursor'),context)
            query = '''SELECT a.*,u.display_name AS actor_name FROM care.case_activity a
                LEFT JOIN care.users u ON u.id=a.actor WHERE a.case_id=?'''
            values = [case_id]
            if after:
                query += ' AND a.id<?'
                values.append(after)
            query += ' ORDER BY a.id DESC LIMIT ?'
            values.append(filters['limit']+1)
            events = [dict(r) for r in db.execute(query,values)]
        for event in events:
            event['payload'] = json.loads(event.pop('payload'))
        next_cursor = self.tokens.dumps(context | {'after':events[filters['limit']-1]['id']}) if len(events)>filters['limit'] else None
        return {'case':self.item(row,detailed=True),'events':events[:filters['limit']],
                'next_cursor':next_cursor,'updated_at':stamp(),
                'history_note':'升級前僅有既存操作紀錄與最新進度快照；未保留的舊進度內容維持未知。'}
