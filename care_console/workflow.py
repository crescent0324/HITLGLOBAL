"""Staff work summaries and explicit handoffs; no clinical assessment is inferred."""
from contextlib import contextmanager
from datetime import datetime, timezone
from werkzeug.exceptions import Conflict
from care_store import STAFF, ASSESSORS, stamp
from migrations import migrate_case_owner_ids

ORIGINS = {
    'user_request': '使用者要求轉人工', 'risk': '訊息分級觸發人工處理',
    'service_coordination': '需要人員協調服務', 'medical_referral': '需要人員確認醫療銜接需求',
    'content_pending': '現有服務資料不足', 'scope_review': '問題超出自動資訊回覆範圍',
    'generation_failure': '回覆工作未完成，需人員確認',
}

def elapsed(value):
    return max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(value)).total_seconds()))

class StaffWorkflow:
    def __init__(self, store, service):
        self.store, self.service = store, service
        with store.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS case_notes(
              case_id INTEGER PRIMARY KEY,resident_id TEXT NOT NULL,summary TEXT NOT NULL,
              next_action TEXT NOT NULL,waiting_for TEXT NOT NULL,revision INTEGER NOT NULL,
              updated_by TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS handoff_requests(
              id INTEGER PRIMARY KEY,case_id INTEGER NOT NULL,resident_id TEXT NOT NULL,
              from_user TEXT NOT NULL,to_user TEXT NOT NULL,summary TEXT NOT NULL,
              next_action TEXT NOT NULL,waiting_for TEXT NOT NULL,message_id INTEGER NOT NULL,
              status TEXT NOT NULL,created_at TEXT NOT NULL,accepted_at TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_pending_handoff
              ON handoff_requests(case_id) WHERE status='pending';
            ''')
        migrate_case_owner_ids(self)

    @contextmanager
    def transaction(self):
        # One transaction covers the ownership update and its facility records.
        with self.service.lock, self.service.db() as db:
            db.execute('ATTACH DATABASE ? AS care', (str(self.store.path),))
            yield db

    def log(self, db, user, action, rid, detail):
        db.execute('INSERT INTO care.audit(actor,action,resident_id,detail,created_at) VALUES(?,?,?,?,?)',
                   (user['id'], action, rid, detail, stamp()))

    def require_staff(self, user, rid, assessor=False):
        self.store.require(user, rid)
        if user['role'] not in (ASSESSORS if assessor else STAFF):
            raise PermissionError('此資訊或操作僅限已授權工作人員。')

    def current_case(self, db, rid, conversation_id=None):
        cid = conversation_id or 'demo-care-'+rid
        if cid != 'demo-care-'+rid and not db.execute(
                'SELECT 1 FROM care.contact_conversations WHERE id=? AND resident_id=?', (cid, rid)).fetchone():
            raise PermissionError('對話與目前住民不符。')
        row = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (cid,)).fetchone()
        if not row:
            raise ValueError('目前沒有未結案案件。')
        return dict(row)

    def require_owner(self, user, case):
        if case['status'] != 'claimed' or case.get('operator_id') != user['id']:
            raise PermissionError('只有目前接手帳號可以更新進度或交班。')

    def identity(self, case):
        uid = case.get('operator_id')
        account = self.store.user(uid) if uid else None
        name = account['display_name'] if account else ('舊資料責任人待確認' if case.get('operator') else None)
        return {'operator_id': uid, 'operator_name': name, 'operator': name}

    def claim(self, user, rid, case_id, conversation_id=None):
        self.require_staff(user, rid, True)
        with self.transaction() as db:
            case = self.current_case(db, rid, conversation_id)
            if case['id'] != case_id or case['status'] != 'pending':
                raise Conflict('案件已變更或已接手，請更新紀錄後確認。')
            db.execute("UPDATE cases SET status='claimed',claimed_at=?,operator=?,operator_id=? WHERE id=?",
                       (stamp(), user['id'], user['id'], case_id))
            self.service.log(db, case['conversation_id'], 'case_claimed', 'case='+str(case_id)+'; operator_id='+user['id'])
            self.service.cancel_jobs(db, case['conversation_id'], '人工接手，自動生成作業停止。', only_auto=True)

    @staticmethod
    def latest_message(db, case):
        return db.execute('SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?', (case['conversation_id'],)).fetchone()[0]

    def context(self, source):
        case = source['case']
        if not case:
            return None
        recent = [m for m in source['messages'] if m['actor'] == 'user'][-3:]
        # The input event is saved before case creation; its timestamp can be
        # slightly earlier. Show the latest retained matching classification.
        evidence = next((e for e in source['events'] if e['risk'] == case['trigger_risk']), None)
        prior = next((m for m in reversed(source['messages']) if m['source'] == 'curated_summary'), None)
        return {'reason': ORIGINS.get(case['origin'], '既有案件待確認'),
                'evidence': {k:evidence[k] for k in ('text','risk','rationale')} if evidence else None,
                'recent_inputs': [{k:m[k] for k in ('text','created_at')} for m in recent],
                'last_service_reply': {'text':prior['text'],'created_at':prior['created_at']} if prior else None,
                'elapsed_seconds': elapsed(case['created_at']),
                'time_label': '等待接手' if case['status'] == 'pending' else '案件持續時間'}

    def view(self, user, rid, source):
        self.require_staff(user, rid, True)
        case = source['case']
        with self.transaction() as db:
            note = db.execute('SELECT n.*,u.display_name AS updated_name FROM care.case_notes n JOIN care.users u ON u.id=n.updated_by WHERE case_id=?',
                              (case['id'],)).fetchone() if case else None
            pending = db.execute('''SELECT h.*,f.display_name AS from_name,t.display_name AS to_name
                FROM care.handoff_requests h JOIN care.users f ON f.id=h.from_user
                JOIN care.users t ON t.id=h.to_user WHERE case_id=? AND status='pending' ''',
                                 (case['id'],)).fetchone() if case else None
            handoff = dict(pending) if pending else None
            if handoff:
                handoff['stale'] = handoff['message_id'] != self.latest_message(db, case)
            peers = [dict(r) for r in db.execute("SELECT id,display_name FROM care.users WHERE role IN ('admin','nurse') AND id!=?", (user['id'],))]
            history = [dict(r) for r in db.execute('''SELECT c.id,c.closed_at,c.close_note,c.operator,c.operator_id,
                n.summary,n.next_action,n.waiting_for FROM cases c LEFT JOIN care.case_notes n ON n.case_id=c.id
                WHERE c.conversation_id=? AND c.status='closed' ORDER BY c.id DESC LIMIT 5''',
                                     (source['conversation']['id'],))]
        history = [item | self.identity(item) for item in history]
        return {'context':self.context(source),'note':dict(note) if note else None,
                'handoff':handoff,'peers':peers,'history':history}

    def queue_item(self, user, resident, source):
        case=source['case']; view=self.view(user,resident['id'],source)
        return {k:resident[k] for k in ('id','label','bed_id','ward')} | {
            'case_id':case['id'],'case_status':case['status'],'state':source['state'],
            'message_risk':case['trigger_risk'],**self.identity(case),'created_at':case['created_at'],
            'context':view['context'],'note':view['note'],'handoff':view['handoff'],
            'mine':case.get('operator_id')==user['id'],
            'handoff_to_me':bool(view['handoff'] and view['handoff']['to_user']==user['id'])}

    @staticmethod
    def sort_queue(items):
        return sorted(items,key=lambda c:({'高':0,'中':1,'低':2}.get(c['message_risk'],3),
                    0 if c['case_status']=='pending' else 1,c['created_at'],c['case_id']))

    def validated_note(self, data):
        out={}
        for key,limit in [('summary',1000),('next_action',1000),('waiting_for',500)]:
            value=data.get(key,'')
            if not isinstance(value,str) or len(value)>limit or (key!='waiting_for' and not value.strip()):
                raise ValueError('請填寫已處理內容與下一步；每欄最多 1000 字，待確認事項最多 500 字。')
            out[key]=value.strip()
        if type(data.get('revision')) is not int or data['revision']<0:
            raise ValueError('進度版本不符，請重新整理。')
        out['revision']=data['revision']
        return out

    def save_note_in(self, db, user, rid, case, data):
        current=db.execute('SELECT revision FROM care.case_notes WHERE case_id=?',(case['id'],)).fetchone()
        revision=current['revision'] if current else 0
        if revision!=data['revision']:
            raise Conflict('進度已被更新，請重新整理後確認，避免覆蓋新內容。')
        db.execute('''INSERT INTO care.case_notes VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET
            summary=excluded.summary,next_action=excluded.next_action,waiting_for=excluded.waiting_for,
            revision=excluded.revision,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
                   (case['id'],rid,data['summary'],data['next_action'],data['waiting_for'],revision+1,user['id'],stamp()))
        db.execute("UPDATE care.handoff_requests SET status='cancelled' WHERE case_id=? AND status='pending'",(case['id'],))
        self.log(db,user,'case_progress_saved',rid,'case='+str(case['id']))

    def save_note(self, user, rid, data, conversation_id=None):
        self.require_staff(user,rid,True);note=self.validated_note(data)
        with self.transaction() as db:
            case=self.current_case(db,rid,conversation_id);self.require_owner(user,case)
            self.save_note_in(db,user,rid,case,note)

    def propose(self, user, rid, data, conversation_id=None):
        self.require_staff(user,rid,True);note=self.validated_note(data)
        target=self.store.user(data.get('to_user'))
        if not target or target['role'] not in ASSESSORS or target['id']==user['id']:
            raise ValueError('請選擇另一位可接班的工作人員。')
        self.store.require(target,rid)
        with self.transaction() as db:
            case=self.current_case(db,rid,conversation_id);self.require_owner(user,case)
            self.save_note_in(db,user,rid,case,note)
            db.execute('''INSERT INTO care.handoff_requests(case_id,resident_id,from_user,to_user,summary,
                next_action,waiting_for,message_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                       (case['id'],rid,user['id'],target['id'],note['summary'],note['next_action'],note['waiting_for'],
                        self.latest_message(db,case),'pending',stamp()))
            self.log(db,user,'handoff_proposed',rid,'case='+str(case['id'])+'; to='+target['id'])

    def accept(self, user, rid, request_id, conversation_id=None):
        self.require_staff(user,rid,True)
        if type(request_id) is not int:
            raise ValueError('交班識別碼不符。')
        with self.transaction() as db:
            case=self.current_case(db,rid,conversation_id)
            h=db.execute("SELECT * FROM care.handoff_requests WHERE id=? AND case_id=? AND resident_id=? AND status='pending'",(request_id,case['id'],rid)).fetchone()
            if not h or h['to_user']!=user['id']:
                raise PermissionError('只有指定接班帳號可以接收有效交班。')
            old=self.store.user(h['from_user'])
            if case['status']!='claimed' or not old or old['role'] not in ASSESSORS or case.get('operator_id')!=old['id']:
                raise Conflict('案件責任人已變更，請重新確認。')
            if h['message_id']!=self.latest_message(db,case):
                raise Conflict('交班提出後有新訊息或回覆，請原接手者更新內容並重新提出交班。')
            db.execute('UPDATE cases SET operator=?,operator_id=? WHERE id=?',(user['id'],user['id'],case['id']))
            db.execute("UPDATE care.handoff_requests SET status='accepted',accepted_at=? WHERE id=?",(stamp(),request_id))
            self.service.cancel_jobs(db,case['conversation_id'],'交班已確認，舊生成工作不沿用。')
            self.service.log(db,case['conversation_id'],'case_handoff_accepted','case='+str(case['id'])+'; operator_id='+user['id'])
            self.log(db,user,'handoff_accepted',rid,'case='+str(case['id'])+'; from='+old['id'])

    def cancel(self, user, rid, conversation_id=None):
        self.require_staff(user,rid,True)
        with self.transaction() as db:
            case=self.current_case(db,rid,conversation_id);self.require_owner(user,case)
            db.execute("UPDATE care.handoff_requests SET status='cancelled' WHERE case_id=? AND status='pending'",(case['id'],))
            self.log(db,user,'handoff_cancelled',rid,'case='+str(case['id']))

    def resolve(self, user, rid, note, conversation_id=None):
        self.require_staff(user,rid,True)
        with self.transaction() as db:
            case=self.current_case(db,rid,conversation_id);self.require_owner(user,case)
            db.execute("UPDATE cases SET status='closed',closed_at=?,close_note=? WHERE id=?",(stamp(),note,case['id']))
            db.execute("UPDATE care.handoff_requests SET status='cancelled' WHERE case_id=? AND status='pending'",(case['id'],))
            self.service.cancel_jobs(db,case['conversation_id'],'事件已結案，舊草稿不再適用。')
            self.service.log(db,case['conversation_id'],'case_closed_automation_resumed','case='+str(case['id'])+'; note='+note)
