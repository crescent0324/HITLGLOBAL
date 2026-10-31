"""Exercise authorization, identity continuity, atomic imports and offline workflows."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import csv
import io
import json
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from contextlib import closing
from app import create_app, conversation
from care_store import CSV_FIELDS, stamp
from integration import OfflineProvider
from backup_local import create_snapshot

class CareConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name) / 'data'
        self.network = patch.object(socket, 'create_connection', side_effect=AssertionError('External network forbidden'))
        self.network.start()
        self.provider = OfflineProvider()
        self.app = create_app(self.directory, provider=self.provider)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.service = self.app.extensions['care_service']
        self.store = self.app.extensions['care_store']
        self.csrf = self.client.get('/api/session').get_json()['csrf']
        self.selected_threads = {}

    def tearDown(self):
        self.service.stop_worker()
        self.network.stop()
        self.tmp.cleanup()

    def login(self, name='nurse'):
        response = self.post('/api/login', {'username': name, 'password': 'CareDemo2026!'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.csrf = response.get_json()['csrf']

    def post(self, path, data):
        if '/case/' in path:
            rid = path.split('/')[3]
            thread = self.selected_threads.get(rid, conversation(rid))
            source = self.service.detail(thread)
            data = dict(data)
            data.setdefault('conversation_id', thread)
            data.setdefault('case_id', source['case']['id'] if source['case'] else 0)
            # Act like a client that has just loaded the latest messages.
            with self.service.db() as db:
                data.setdefault('seen_message_id', db.execute(
                    'SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?', (thread,)).fetchone()[0])
        return self.client.post(path, json=data, headers={'X-CSRF-Token':self.csrf})

    def detail(self, rid='R001'):
        response=self.client.get('/api/residents/'+rid, query_string={
            'conversation_id': self.selected_threads.get(rid, conversation(rid))})
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()

    def row(self, **changes):
        return dict(resident_code='R001',source_record_id='TEST-001',observed_at=stamp(),
                    temperature_c='36.8',pulse_bpm='72',spo2_pct='98',systolic_mmhg='125',
                    diastolic_mmhg='76',care_status='尚未評估',care_note='虛構測試紀錄') | changes

    def csv(self, *rows):
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=CSV_FIELDS)
        writer.writeheader();writer.writerows(rows);return stream.getvalue()

    def imported(self, *rows):
        return self.post('/api/import',dict(csv=self.csv(*rows),synthetic_confirmed=True))

    def send(self, text, rid='R001', channel='web', actor='family'):
        response=self.post(f'/api/residents/{rid}/message',dict(text=text,channel=channel,line_actor=actor))
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertFalse(response.get_json()['actual_line_sent'])
        self.selected_threads[rid] = response.get_json()['conversation_id']

    def line_send(self, text, rid='R001', actor='family'):
        self.send(text,rid,'demo_line',actor)

    def test_caregiver_cannot_read_family_conversations_or_case_metadata(self):
        self.login();self.line_send('轉人工：虛構家屬私人訊息 PRIVATE-FAMILY-ONLY')
        thread=self.selected_threads['R001']
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress(
            summary='PRIVATE-CASE-PROGRESS',next_action='由護理師處理')).status_code,200)
        self.login('caregiver')
        board=self.client.get('/api/board').get_json()
        self.assertEqual(board['work_queue'],[])
        for card in board['cards']:
            self.assertFalse(set(card)&{'state','pending_case','pending_count','case_operator','risk'})
        detail=self.client.get('/api/residents/R001').get_json()
        self.assertEqual(set(detail),{'resident','observations','role'})
        self.assertNotIn('PRIVATE-',json.dumps(board|detail))
        for cid in [thread,conversation('R001'),'unknown-thread']:
            response=self.client.get('/api/residents/R001',query_string={'conversation_id':cid})
            self.assertEqual(response.status_code,403)
        self.assertEqual(self.post('/api/residents/R001/message',dict(text='不得讀寫共用對話')).status_code,403)
        self.assertEqual(self.post('/api/residents/R001/message',dict(text='不得冒用家屬',channel='demo_line',line_actor='family')).status_code,403)
        self.assertEqual(self.client.get('/api/residents/R003').status_code,403)
        self.assertEqual(self.client.get('/api/knowledge').status_code,200)
        self.assertEqual(self.post('/api/residents/R001/observation',self.row()).status_code,200)

    def test_same_display_name_cannot_impersonate_case_owner(self):
        self.open_owned_case()
        before=self.detail()
        with self.store.db() as db:
            db.execute("UPDATE users SET display_name=? WHERE id='nurse2'",(self.store.user('nurse')['display_name'],))
        self.login('nurse2')
        queue=self.client.get('/api/board').get_json()['work_queue']
        self.assertFalse(queue[0]['mine'])
        for action,payload in [
            ('reply',{'text':'不可冒名回覆'}),
            ('progress',self.progress(summary='不可冒名改進度')),
            ('handoff',self.progress(to_user='admin')),
            ('cancel_handoff',{}),
            ('resolve',{'note':'不可冒名結案'})]:
            with self.subTest(action=action):
                self.assertEqual(self.post('/api/residents/R001/case/'+action,payload).status_code,403)
        after=self.detail()
        self.assertEqual(after['case']['id'],before['case']['id'])
        self.assertEqual(after['case']['status'],'claimed')
        self.assertEqual(len(after['messages']),len(before['messages']))
        self.assertIsNone(after['workflow']['note'])

    def test_owner_rename_keeps_identity_and_handoff_respects_ids(self):
        self.open_owned_case()
        self.assertEqual(self.detail()['case']['operator_id'],'nurse')
        self.assertEqual(self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2')).status_code,200)
        request_id=self.detail()['workflow']['handoff']['id']
        with self.store.db() as db:
            db.execute("UPDATE users SET display_name='同名護理師' WHERE id IN ('nurse','nurse2')")
        self.login('nurse')
        self.assertEqual(self.detail()['case']['operator_id'],'nurse')
        self.assertEqual(self.detail()['case']['operator_name'],'同名護理師')
        self.assertEqual(self.post('/api/residents/R001/case/reply',{'text':'更名後仍由原帳號回覆'}).status_code,200)
        # A reply invalidates the old handoff; only the original ID may propose anew.
        self.assertEqual(self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2',revision=1)).status_code,200)
        request_id=self.detail()['workflow']['handoff']['id']
        self.login('admin')
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',{'request_id':request_id}).status_code,403)
        self.login('nurse2')
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',{'request_id':request_id}).status_code,200)
        self.assertEqual(self.detail()['case']['operator_id'],'nurse2')
        self.login('nurse')
        self.assertEqual(self.post('/api/residents/R001/case/reply',{'text':'原帳號不可再處理'}).status_code,403)
        self.login('nurse2')
        self.assertEqual(self.post('/api/residents/R001/case/resolve',{'note':'虛構案件已完成'}).status_code,200)

    def make_legacy_owner(self, legacy_name):
        """Build only temporary pre-upgrade storage, with the original name column."""
        case=self.detail()['case']
        with self.service.db() as db:
            db.execute('UPDATE cases SET operator=? WHERE id=?',(legacy_name,case['id']))
            db.execute('ALTER TABLE cases DROP COLUMN operator_id')
        with self.store.db() as db:
            db.execute("DELETE FROM meta WHERE key='stable_case_owner_v1'")
            db.execute('DROP TABLE case_owner_migrations')
        return case['id']

    def insert_review_fixture(self):
        # A retained draft fixture tests access/cancellation without any model call.
        thread=self.selected_threads.get('R001',conversation('R001'))
        with self.service.db() as db:
            cur=db.execute('''INSERT INTO generations(event_id,conversation_id,risk,mode,status,payload,sources,
                model,config_revision,prompt_version,knowledge_version,knowledge_hash,created_at,updated_at,response_text)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',('fixture-'+str(self.service.database),thread,'中','REVIEW','draft','{}','[]',
                    'offline-fixture',0,'fixture','fixture','fixture',stamp(),stamp(),'虛構草稿，不可冒名核准'))
            return cur.lastrowid

    def test_same_name_colleague_cannot_review_real_conversation_draft(self):
        self.open_owned_case();job_id=self.insert_review_fixture()
        with self.store.db() as db:
            db.execute("UPDATE users SET display_name=? WHERE id='nurse2'",(self.store.user('nurse')['display_name'],))
        self.login('nurse2')
        for action in ['approve','reject']:
            self.assertEqual(self.post('/api/residents/R001/case/'+action,dict(job_id=job_id,text='不可冒名核准',note='不可冒名審閱')).status_code,403)
        with self.service.db() as db:
            self.assertEqual(db.execute('SELECT status FROM generations WHERE id=?',(job_id,)).fetchone()[0],'draft')
        self.assertEqual(self.provider.calls,[])

    def test_unique_legacy_owner_is_backed_up_and_migrated_once(self):
        self.open_owned_case()
        self.assertEqual(self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2')).status_code,200)
        original=self.detail();case_id=self.make_legacy_owner(self.store.user('nurse')['display_name'])
        restored=create_app(self.directory,provider=OfflineProvider())
        service=restored.extensions['care_service']
        with service.db() as db:
            case=dict(db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone())
        self.assertEqual((case['operator_id'],case['operator'],case['status']),('nurse','nurse','claimed'))
        view=restored.extensions['care_workflow'].view(self.store.user('nurse'),'R001',service.detail(conversation('R001')))
        self.assertEqual(view['note']['summary'],original['workflow']['note']['summary'])
        self.assertEqual(view['handoff']['id'],original['workflow']['handoff']['id'])
        self.assertEqual(len(service.detail(conversation('R001'))['messages']),len(original['messages']))
        backups=list((self.directory/'backups').glob('before-stable-case-owner-v1-*'))
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups[0]/'core.sqlite3')) as db:
            self.assertNotIn('operator_id',{r[1] for r in db.execute('PRAGMA table_info(cases)')})
            self.assertEqual(db.execute('SELECT operator FROM cases WHERE id=?',(case_id,)).fetchone()[0],'護理師體驗帳號')
        self.assertFalse(any(p.name in {'session.key','config.local.json'} for p in backups[0].iterdir()))
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT legacy_operator FROM case_owner_migrations WHERE case_id=?',(case_id,)).fetchone()[0],'護理師體驗帳號')
            db.execute("UPDATE users SET display_name='後來同名' WHERE id IN ('nurse','nurse2')")
        again=create_app(self.directory,provider=OfflineProvider())
        with again.extensions['care_service'].db() as db:
            self.assertEqual(db.execute('SELECT operator_id FROM cases WHERE id=?',(case_id,)).fetchone()[0],'nurse')
        self.assertEqual(len(list((self.directory/'backups').glob('before-stable-case-owner-v1-*'))),1)

    def test_ambiguous_legacy_owner_returns_to_pending_and_cancels_draft(self):
        self.open_owned_case()
        self.assertEqual(self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2')).status_code,200)
        original=self.detail();job_id=self.insert_review_fixture()
        legacy=self.store.user('nurse')['display_name']
        with self.store.db() as db:
            db.execute("UPDATE users SET display_name=? WHERE id='nurse2'",(legacy,))
        case_id=self.make_legacy_owner(legacy)
        restored=create_app(self.directory,provider=OfflineProvider())
        service=restored.extensions['care_service']
        with service.db() as db:
            case=dict(db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone())
            self.assertEqual(db.execute('SELECT status FROM generations WHERE id=?',(job_id,)).fetchone()[0],'cancelled')
        self.assertEqual(case['status'],'pending');self.assertIsNone(case['operator_id']);self.assertIsNone(case['operator'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT result FROM case_owner_migrations WHERE case_id=?',(case_id,)).fetchone()[0],'ambiguous_display_name')
            self.assertEqual(db.execute('SELECT status FROM handoff_requests WHERE case_id=?',(case_id,)).fetchone()[0],'cancelled')
            self.assertEqual(db.execute('SELECT summary FROM case_notes WHERE case_id=?',(case_id,)).fetchone()[0],original['workflow']['note']['summary'])
        wf=restored.extensions['care_workflow']
        for uid in ['nurse','nurse2']:
            with self.assertRaises(PermissionError):wf.require_owner(self.store.user(uid),case)
        self.assertEqual(len(service.detail(conversation('R001'))['messages']),len(original['messages']))
        wf.claim(self.store.user('nurse2'),'R001',case_id)
        self.assertEqual(service.detail(conversation('R001'))['case']['operator_id'],'nurse2')

    def test_missing_or_ineligible_legacy_owner_never_grants_authority(self):
        self.open_owned_case();legacy='不存在的舊帳號'
        case_id=self.make_legacy_owner(legacy)
        restored=create_app(self.directory,provider=OfflineProvider())
        with restored.extensions['care_service'].db() as db:
            self.assertEqual(db.execute('SELECT status FROM cases WHERE id=?',(case_id,)).fetchone()[0],'pending')
        # A later matching display name must not revive the old owner on restart.
        with self.store.db() as db:db.execute("UPDATE users SET display_name=? WHERE id='nurse2'",(legacy,))
        again=create_app(self.directory,provider=OfflineProvider())
        with again.extensions['care_service'].db() as db:
            self.assertIsNone(db.execute('SELECT operator_id FROM cases WHERE id=?',(case_id,)).fetchone()[0])

    def test_caregiver_cannot_bypass_api_through_internal_read_helpers(self):
        self.login();self.line_send('轉人工')
        user=self.store.user('caregiver');directory=self.app.extensions['care_conversations']
        source=self.service.detail(self.selected_threads['R001'])
        for call in [lambda:directory.list(user,'R001'),lambda:directory.describe(user,'R001',self.selected_threads['R001']),
                     lambda:directory.contact_thread(user,'R001','family'),lambda:self.store.audit(user,'R001'),
                     lambda:self.store.authors(user,'R001'),lambda:self.app.extensions['care_workflow'].view(user,'R001',source)]:
            with self.assertRaises(PermissionError):call()

    def test_legacy_owner_matching_only_caregiver_is_not_migrated_as_owner(self):
        self.open_owned_case();case_id=self.make_legacy_owner(self.store.user('caregiver')['display_name'])
        restored=create_app(self.directory,provider=OfflineProvider())
        with restored.extensions['care_service'].db() as db:
            case=dict(db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone())
        self.assertEqual(case['status'],'pending');self.assertIsNone(case['operator_id'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT result FROM case_owner_migrations WHERE case_id=?',(case_id,)).fetchone()[0],'ineligible_account')

    def test_owner_migration_failure_rolls_back_schema_and_records(self):
        self.open_owned_case()
        legacy='無法辨認的舊責任人';case_id=self.make_legacy_owner(legacy)
        with patch.object(type(self.service),'cancel_jobs',side_effect=RuntimeError('injected migration failure')):
            with self.assertRaisesRegex(RuntimeError,'injected migration failure'):
                create_app(self.directory,provider=OfflineProvider())
        with self.service.db() as db:
            self.assertNotIn('operator_id',{r['name'] for r in db.execute('PRAGMA table_info(cases)')})
            case=db.execute('SELECT status,operator FROM cases WHERE id=?',(case_id,)).fetchone()
            self.assertEqual(tuple(case),('claimed',legacy))
        with self.store.db() as db:
            self.assertIsNone(db.execute("SELECT 1 FROM meta WHERE key='stable_case_owner_v1'").fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='case_owner_migrations'").fetchone())
        restored=create_app(self.directory,provider=OfflineProvider())
        with restored.extensions['care_service'].db() as db:
            self.assertEqual(db.execute('SELECT status FROM cases WHERE id=?',(case_id,)).fetchone()[0],'pending')

    def test_closed_legacy_case_keeps_history_without_inventing_owner_id(self):
        self.open_owned_case();case_id=self.detail()['case']['id']
        self.assertEqual(self.post('/api/residents/R001/case/resolve',{'note':'保留的舊結案內容'}).status_code,200)
        with self.service.db() as db:
            db.execute('UPDATE cases SET operator=? WHERE id=?',('已刪除的舊帳號',case_id))
            db.execute('ALTER TABLE cases DROP COLUMN operator_id')
        with self.store.db() as db:
            db.execute("DELETE FROM meta WHERE key='stable_case_owner_v1'")
            db.execute('DROP TABLE case_owner_migrations')
        restored=create_app(self.directory,provider=OfflineProvider())
        service=restored.extensions['care_service'];source=service.detail(conversation('R001'))
        self.assertIsNone(source['case'])
        view=restored.extensions['care_workflow'].view(self.store.user('nurse'),'R001',source)
        self.assertEqual(view['history'][0]['close_note'],'保留的舊結案內容')
        self.assertIsNone(view['history'][0]['operator_id'])

    def test_backup_failure_aborts_owner_upgrade(self):
        self.open_owned_case();case_id=self.make_legacy_owner('護理師體驗帳號')
        with patch('app.backup_before_owner_migration',side_effect=OSError('snapshot unavailable')):
            with self.assertRaisesRegex(OSError,'snapshot unavailable'):
                create_app(self.directory,provider=OfflineProvider())
        with self.service.db() as db:
            self.assertNotIn('operator_id',{r['name'] for r in db.execute('PRAGMA table_info(cases)')})
            self.assertEqual(db.execute('SELECT operator FROM cases WHERE id=?',(case_id,)).fetchone()[0],'護理師體驗帳號')

    def test_unauthenticated_and_remote_access_denied(self):
        self.assertEqual(self.client.get('/api/board').status_code,401)
        self.assertEqual(self.client.get('/health',base_url='http://evil.example').status_code,403)
        self.assertEqual(self.client.get('/health',environ_overrides={'REMOTE_ADDR':'192.168.1.2'}).status_code,403)

    def test_csrf_and_cross_origin_login_rejected(self):
        self.assertEqual(self.client.post('/api/login',json={}).status_code,403)
        self.assertEqual(self.client.post('/api/login',json={},headers={'X-CSRF-Token':self.csrf,'Origin':'https://evil.example'}).status_code,403)

    def test_password_and_login_rate_limit(self):
        for _ in range(8):
            self.assertEqual(self.post('/api/login',{'username':'nurse','password':'wrong'}).status_code,401)
        self.assertEqual(self.post('/api/login',{'username':'nurse','password':'wrong'}).status_code,429)

    def test_session_rotates_csrf_and_logout_revokes_access(self):
        old=self.csrf;self.login();self.assertNotEqual(old,self.csrf)
        self.assertEqual(self.post('/api/logout',{}).status_code,200)
        self.assertEqual(self.client.get('/api/board').status_code,401)

    def test_roles_have_distinct_resident_scopes(self):
        for role, count in [('nurse',6),('caregiver',2)]:
            self.login(role)
            body=self.client.get('/api/board').get_json()
            self.assertEqual(len(body['cards']),count)
            self.assertFalse(body['ai_enabled'])
            self.assertEqual(body['line_link']['user_id'],role)
        self.login('admin')
        self.assertEqual(self.client.get('/api/board').status_code,403)

    def test_family_and_resident_cannot_log_in_to_web(self):
        for role in ['family','resident']:
            self.assertEqual(self.post('/api/login',dict(username=role,password='CareDemo2026!')).status_code,403)
            self.assertEqual(self.client.get('/api/board').status_code,401)
            self.assertEqual(self.client.get('/api/residents/R001').status_code,401)
            self.assertEqual(self.post('/api/residents/R001/message',dict(text='測試')).status_code,401)
        self.assertEqual(set(self.client.get('/api/session').get_json()['roles']),{'admin','head_nurse','nurse','caregiver'})

    def test_caregiver_observation_cannot_set_assessment(self):
        self.login('caregiver')
        self.assertEqual(self.post('/api/residents/R001/observation',self.row(care_status='一般照護')).status_code,403)
        self.assertEqual(self.post('/api/residents/R001/observation',self.row()).status_code,200)
        response=self.client.get('/api/residents/R001')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['observations'][0]['care_status'],'尚未評估')
        self.assertEqual(self.post('/api/residents/R003/observation',self.row()).status_code,403)

    def test_information_answer_is_offline_and_sourced(self):
        self.login('nurse');self.line_send('想了解喘息服務')
        data=self.detail();text='\n'.join(m['text'] for m in data['messages'] if m['actor']!='user')
        self.assertIn('未使用模型生成',text)
        self.assertIn('1966',text)
        self.assertEqual(data['state'],'automatic')
        self.assertEqual(self.provider.calls,[])
        self.assertEqual(data['messages'][0]['author'],'家屬體驗帳號')
        self.assertEqual(data['messages'][0]['input_channel'],'demo_line')

    def test_same_contact_conversation_keeps_manual_state(self):
        self.login('nurse');self.line_send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.line_send('想了解日照',actor='family')
        data=self.detail();self.assertEqual(data['state'],'human_active')
        self.assertEqual(data['messages'][-1]['actor'],'user')
        self.assertEqual(data['messages'][-1]['text'],'想了解日照')
        self.assertEqual(data['drafts'],[])
        self.assertEqual(data['messages'][-1]['author'],'家屬體驗帳號')
        self.assertTrue(any(a['action']=='line_message_simulated' and a['actor']=='nurse' for a in data['audit']))

    def test_only_current_case_owner_can_reply_and_resolve(self):
        self.login('nurse');self.line_send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.login('admin')
        self.assertEqual(self.post('/api/residents/R001/case/reply',dict(text='代為操作')).status_code,403)
        self.assertEqual(self.post('/api/residents/R001/case/resolve',dict(note='代為結案')).status_code,403)
        self.login('nurse')
        self.assertEqual(self.post('/api/residents/R001/case/reply',dict(text='虛構人工回覆')).status_code,200)
        reply=self.detail()['messages'][-1]
        self.assertEqual(reply['actor'],'human')
        self.assertEqual(reply['author'],'護理師體驗帳號')
        self.assertEqual(self.detail()['state'],'human_active')
        self.assertEqual(self.post('/api/residents/R001/case/resolve',dict(note='虛構流程已完成')).status_code,200)
        self.assertEqual(self.detail()['state'],'automatic')

    def test_high_risk_has_no_general_generation(self):
        self.login('nurse');self.send('長輩剛剛倒地')
        self.assertEqual(self.detail()['state'],'awaiting_takeover')
        self.assertEqual(self.detail()['drafts'],[])
        self.assertEqual(self.provider.calls,[])

    def test_atomic_csv_rejects_invalid_row_without_partial_insert(self):
        self.login();before=len(self.detail()['observations'])
        result=self.imported(self.row(),self.row(source_record_id='TEST-002',spo2_pct='NaN'))
        self.assertEqual(result.status_code,400)
        self.assertEqual(len(self.detail()['observations']),before)

    def test_csv_duplicate_idempotency_and_conflict_roll_back(self):
        self.login();row=self.row()
        self.assertEqual(self.imported(row).get_json(),dict(inserted=1,skipped=0))
        self.assertEqual(self.imported(row).get_json(),dict(inserted=0,skipped=1))
        before=len(self.detail()['observations'])
        result=self.imported(self.row(source_record_id='TEST-002'),row|dict(care_note='不一致的更正'))
        self.assertEqual(result.status_code,400)
        self.assertEqual(len(self.detail()['observations']),before)

    def test_csv_requires_synthetic_confirmation_and_known_resident(self):
        self.login()
        self.assertEqual(self.post('/api/import',dict(csv=self.csv(self.row()),synthetic_confirmed=False)).status_code,400)
        self.assertEqual(self.imported(self.row(resident_code='R999')).status_code,400)
        self.assertEqual(self.imported(self.row(observed_at='2026-10-03T10:00:00')).status_code,400)
        future=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        self.assertEqual(self.imported(self.row(observed_at=future)).status_code,400)

    def test_missing_values_remain_unknown_and_old_record_is_not_latest(self):
        self.login()
        old=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        row=self.row(observed_at=old,temperature_c='',pulse_bpm='',spo2_pct='',systolic_mmhg='',diastolic_mmhg='')
        self.assertEqual(self.imported(row).status_code,200)
        data=self.detail();self.assertTrue(all(v is None for v in data['observations'][-1]['values'].values()))
        card=self.client.get('/api/board').get_json()['cards'][0]
        self.assertEqual(card['latest']['source_record_id'],'DEMO-1')

    def test_transfer_keeps_resident_records_and_grants(self):
        self.login();before=[o['id'] for o in self.detail()['observations']]
        self.assertEqual(self.post('/api/residents/R001/move',dict(bed_id='A102')).status_code,400)
        self.assertEqual(self.post('/api/residents/R001/move',dict(bed_id='A107')).status_code,200)
        data=self.detail()
        self.assertEqual(data['resident']['bed_id'],'A107')
        self.assertEqual([o['id'] for o in data['observations']],before)
        self.assertTrue(self.store.allowed(self.store.user('family'),'R001'))
        self.line_send('虛構：轉床後的家屬詢問')
        self.assertEqual(self.detail()['messages'][-1]['author'],'家屬體驗帳號')

    def test_access_revocation_takes_effect_on_current_session(self):
        self.login('nurse');self.line_send('虛構：配對撤銷前的訊息')
        other=self.app.test_client();token=other.get('/api/session').get_json()['csrf']
        result=other.post('/api/login',json=dict(username='admin',password='CareDemo2026!'),headers={'X-CSRF-Token':token})
        token=result.get_json()['csrf']
        result=other.post('/api/bindings',json=dict(user_id='family',resident_id='R001',allowed=False),headers={'X-CSRF-Token':token})
        self.assertEqual(result.status_code,200)
        result=self.post('/api/residents/R001/message',dict(text='虛構：撤銷後不應寫入',channel='demo_line',line_actor='family'))
        self.assertEqual(result.status_code,403)
        self.assertFalse(any(m['text']=='虛構：撤銷後不應寫入' for m in self.detail()['messages']))

    def test_backup_restores_into_new_directory_without_secrets(self):
        self.login('nurse');self.send('轉人工')
        # Full databases are no longer downloadable through a portal role.
        self.login('admin');self.assertEqual(self.post('/api/backup',{}).status_code,403)
        with self.service.lock:
            snapshot=create_snapshot(self.directory)
        dest=Path(self.tmp.name)/'restored';dest.mkdir()
        with zipfile.ZipFile(snapshot) as archive:
            self.assertEqual(set(archive.namelist()),{'facility.sqlite3','core.sqlite3','manifest.json','environment.json','core-environment.json'})
            archive.extract('facility.sqlite3',dest);archive.extract('environment.json',dest)
            (dest/'core').mkdir();(dest/'core/research.sqlite3').write_bytes(archive.read('core.sqlite3'))
            (dest/'core/integration-environment.json').write_bytes(archive.read('core-environment.json'))
        for filename in ['facility.sqlite3','core/research.sqlite3']:
            with closing(sqlite3.connect(dest/filename)) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        restored=create_app(dest,provider=OfflineProvider())
        data=restored.extensions['care_service'].detail(conversation('R001'))
        self.assertEqual(data['state'],'awaiting_takeover')
        self.assertEqual(len(restored.extensions['care_store'].residents(self.store.user('nurse'))),6)
        self.assertEqual(restored.extensions['care_service'].settings.snapshot()['openai_key'],'')

    def test_restart_keeps_existing_data_and_does_not_reseed(self):
        self.login();self.assertEqual(self.imported(self.row()).status_code,200)
        other=create_app(self.directory,provider=OfflineProvider())
        store=other.extensions['care_store'];rows=store.observations(store.user('nurse'),'R001')
        self.assertEqual(len(rows),2)
        self.assertEqual(len(store.beds(store.user('nurse'))),8)

    def test_rejects_existing_unmarked_data_directory(self):
        foreign=Path(self.tmp.name)/'foreign';foreign.mkdir();(foreign/'facility.sqlite3').touch()
        with self.assertRaises(ValueError):create_app(foreign,provider=OfflineProvider())

    def open_owned_case(self, rid='R001'):
        self.login('nurse');self.send('轉人工',rid)
        self.assertEqual(self.post(f'/api/residents/{rid}/case/claim',{}).status_code,200)

    def progress(self, **changes):
        return dict(summary='虛構：已確認家屬的服務詢問',next_action='虛構：待下一班確認聯絡需求',
                    waiting_for='虛構：等待家屬補充時間',revision=0)|changes

    def test_second_nurse_has_independent_identity(self):
        self.login('nurse2');body=self.client.get('/api/board').get_json()
        self.assertEqual(body['user']['role'],'nurse')
        self.assertEqual(body['user']['id'],'nurse2')
        self.assertEqual(len(body['cards']),6)

    def test_work_queue_orders_message_risk_and_explains_origin(self):
        self.login();self.send('轉人工','R001');self.send('長輩剛剛倒地','R002')
        body=self.client.get('/api/board').get_json();queue=body['work_queue']
        self.assertEqual([q['id'] for q in queue],['R002','R001'])
        self.assertEqual(queue[1]['context']['reason'],'使用者要求轉人工')
        self.assertEqual(queue[0]['message_risk'],'高')
        self.assertEqual(queue[0]['context']['recent_inputs'][-1]['text'],'長輩剛剛倒地')
        self.assertTrue(queue[0]['context']['evidence'])
        self.assertTrue(any(c['id']=='R004' and c['latest']['care_status']=='需優先確認' for c in body['cards']))
        self.assertFalse(any(q['id']=='R004' for q in queue))

    def test_family_cannot_read_internal_queue_or_notes(self):
        self.open_owned_case();self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress()).status_code,200)
        with self.client.session_transaction() as legacy:
            legacy['uid']='family';legacy['csrf']=self.csrf
        self.assertEqual(self.client.get('/api/board').status_code,401)
        self.assertEqual(self.client.get('/api/residents/R001').status_code,401)
        for action in ['progress','handoff','accept_handoff','cancel_handoff']:
            self.assertEqual(self.post('/api/residents/R001/case/'+action,self.progress()).status_code,401)
        self.assertIsNone(self.client.get('/api/session').get_json()['user'])
        with self.client.session_transaction() as cleared:
            self.assertNotIn('uid',cleared)

    def test_caregiver_queue_stays_within_assigned_residents(self):
        self.login();self.send('轉人工','R003');self.send('轉人工','R001')
        self.login('caregiver');queue=self.client.get('/api/board').get_json()['work_queue']
        self.assertEqual(queue,[])  # A care assignment does not grant family-message access.
        self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress()).status_code,403)

    def test_progress_requires_owner_and_resists_stale_overwrite(self):
        self.open_owned_case()
        self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress()).status_code,200)
        self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress(summary='過時內容')).status_code,409)
        self.assertEqual(self.detail()['workflow']['note']['revision'],1)
        self.login('nurse2');self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress(revision=1)).status_code,403)

    def test_handoff_requires_summary_next_action_and_valid_recipient(self):
        self.open_owned_case()
        for data in [self.progress(summary='',to_user='nurse2'),self.progress(next_action='',to_user='nurse2'),
                     self.progress(to_user='nurse'),self.progress(to_user='family')]:
            self.assertEqual(self.post('/api/residents/R001/case/handoff',data).status_code,400)
        self.assertIsNone(self.detail()['workflow']['note'])

    def test_handoff_changes_owner_only_after_recipient_accepts(self):
        self.open_owned_case()
        self.assertEqual(self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2')).status_code,200)
        data=self.detail();request_id=data['workflow']['handoff']['id']
        self.assertEqual(data['case']['operator'],'護理師體驗帳號')
        self.assertEqual(data['state'],'human_active')
        self.login('admin');self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=request_id)).status_code,403)
        self.login('nurse2')
        self.assertTrue(self.client.get('/api/board').get_json()['work_queue'][0]['handoff_to_me'])
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=request_id)).status_code,200)
        self.assertEqual(self.detail()['case']['operator'],'接班護理師體驗帳號')
        self.assertEqual(self.detail()['state'],'human_active')
        self.assertIsNone(self.detail()['workflow']['handoff'])
        self.assertEqual(self.post('/api/residents/R001/case/reply',dict(text='虛構：已接班')).status_code,200)
        self.login('nurse');self.assertEqual(self.post('/api/residents/R001/case/reply',dict(text='舊接手者回覆')).status_code,403)

    def test_new_message_invalidates_pending_handoff_acceptance(self):
        self.open_owned_case();self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2'))
        request_id=self.detail()['workflow']['handoff']['id']
        self.send('補充：請確認明天的洽詢方式')
        self.login('nurse2');self.assertTrue(self.detail()['workflow']['handoff']['stale'])
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=request_id)).status_code,409)
        self.assertEqual(self.detail()['case']['operator'],'護理師體驗帳號')
        self.assertEqual(self.detail()['state'],'human_active')

    def test_progress_update_cancels_old_handoff_and_new_request_can_be_accepted(self):
        self.open_owned_case();self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2'))
        old_id=self.detail()['workflow']['handoff']['id']
        self.assertEqual(self.post('/api/residents/R001/case/progress',self.progress(revision=1,next_action='虛構：修正下一步')).status_code,200)
        self.assertIsNone(self.detail()['workflow']['handoff'])
        self.post('/api/residents/R001/case/handoff',self.progress(revision=2,to_user='nurse2'))
        new_id=self.detail()['workflow']['handoff']['id'];self.assertNotEqual(old_id,new_id)
        self.login('nurse2')
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=old_id)).status_code,403)
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=new_id)).status_code,200)

    def test_resolve_cancels_handoff_and_keeps_history(self):
        self.open_owned_case();self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2'))
        request_id=self.detail()['workflow']['handoff']['id']
        self.assertEqual(self.post('/api/residents/R001/case/resolve',dict(note='虛構：本班已完成')).status_code,200)
        data=self.detail();self.assertEqual(data['state'],'automatic')
        self.assertEqual(data['workflow']['history'][0]['close_note'],'虛構：本班已完成')
        self.assertEqual(data['workflow']['history'][0]['summary'],self.progress()['summary'])
        self.login('nurse2');self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',dict(request_id=request_id)).status_code,400)

    def test_context_includes_existing_service_reply_without_generated_summary(self):
        self.login('nurse');self.line_send('想了解喘息服務');self.line_send('轉人工')
        context=self.detail()['workflow']['context']
        self.assertIn('未使用模型生成',context['last_service_reply']['text'])
        self.assertEqual(len(context['recent_inputs']),2)
        self.assertEqual(self.provider.calls,[])

    def test_tracking_status_requires_reason(self):
        self.login();self.assertEqual(self.post('/api/residents/R001/observation',self.row(care_status='需追蹤',care_note='')).status_code,400)
        self.assertEqual(self.post('/api/residents/R001/observation',self.row(care_status='需追蹤',care_note='虛構：需要確認來源紀錄')).status_code,200)

    def test_line_simulation_requires_valid_paired_contact_and_staff_permission(self):
        self.login('nurse')
        contacts=self.detail()['line_contacts']
        self.assertEqual({c['id'] for c in contacts},{'family','resident'})
        before=len(self.detail()['messages'])
        for actor in ['nurse','unknown']:
            self.assertEqual(self.post('/api/residents/R001/message',dict(text='虛構：不得寫入',channel='demo_line',line_actor=actor)).status_code,400)
        self.assertEqual(self.post('/api/residents/R002/message',dict(text='虛構：未配對住民',channel='demo_line',line_actor='family')).status_code,403)
        self.assertEqual(len(self.detail()['messages']),before)
        self.login('caregiver')
        self.assertNotIn('line_contacts',self.client.get('/api/residents/R001').get_json())
        self.assertEqual(self.post('/api/residents/R001/message',dict(text='虛構：不得代為模擬',channel='demo_line',line_actor='family')).status_code,403)

    def test_former_resident_web_session_is_denied(self):
        with self.client.session_transaction() as legacy:
            legacy['uid']='resident';legacy['csrf']=self.csrf
        self.assertEqual(self.client.get('/api/knowledge').status_code,401)
        self.assertEqual(self.client.get('/api/bindings').status_code,401)
        self.assertIsNone(self.client.get('/api/session').get_json()['user'])

    def test_unassessed_reports_do_not_clear_recorded_followup(self):
        self.login('caregiver')
        base=datetime.now(timezone.utc)
        # More than the detail-history limit must not erase a prior assessment.
        for index in range(31):
            self.store.add_observation(self.store.user('caregiver'),'R002',self.row(
                source_record_id=f'PENDING-{index}',observed_at=(base+timedelta(seconds=index)).isoformat()))
        card=next(c for c in self.client.get('/api/board').get_json()['cards'] if c['id']=='R002')
        self.assertEqual(card['latest']['care_status'],'尚未評估')
        self.assertEqual(card['latest']['source_record_id'],'PENDING-30')
        self.assertIsNotNone(card.get('assessment'))
        self.assertEqual(card['assessment']['care_status'],'需追蹤')
        self.assertEqual(card['assessment']['source_record_id'],'DEMO-2')
        self.login('nurse')
        self.assertEqual(self.post('/api/residents/R002/observation',self.row(
            source_record_id='FOLLOWUP-REVIEWED',observed_at=(base+timedelta(seconds=32)).isoformat(),
            care_status='一般照護')).status_code,200)
        card=next(c for c in self.client.get('/api/board').get_json()['cards'] if c['id']=='R002')
        self.assertEqual(card['assessment']['source_record_id'],'FOLLOWUP-REVIEWED')
        self.assertEqual(card['assessment']['care_status'],'一般照護')

    def test_assessment_uses_observed_time_and_keeps_unknown_separate(self):
        self.login('nurse')
        old=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
        self.assertEqual(self.imported(self.row(resident_code='R002',source_record_id='OLDER-GENERAL',
            observed_at=old,care_status='一般照護')).status_code,200)
        self.assertEqual(self.post('/api/residents/R005/observation',self.row(
            source_record_id='ONLY-PENDING')).status_code,200)
        cards={c['id']:c for c in self.client.get('/api/board').get_json()['cards']}
        self.assertIsNotNone(cards['R002'].get('assessment'))
        self.assertEqual(cards['R002']['assessment']['source_record_id'],'DEMO-2')
        self.assertIsNone(cards['R005']['assessment'])
        self.assertEqual(cards['R005']['latest']['care_status'],'尚未評估')
        self.assertIsNone(cards['R006']['assessment'])
        self.assertIsNone(cards['R006']['latest'])

    def test_handoff_and_progress_survive_restart(self):
        self.open_owned_case();self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2'))
        restored=create_app(self.directory,provider=OfflineProvider());workflow=restored.extensions['care_workflow']
        source=restored.extensions['care_service'].detail(conversation('R001'))
        view=workflow.view(self.store.user('nurse2'),'R001',source)
        self.assertEqual(view['note']['revision'],1)
        self.assertEqual(view['handoff']['to_user'],'nurse2')
        self.assertEqual(source['state'],'human_active')

    def test_contacts_have_separate_messages_cases_and_reply_recipients(self):
        self.login()
        self.line_send('轉人工')
        family_thread = self.selected_threads['R001']
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.line_send('轉人工', actor='resident')
        resident_thread = self.selected_threads['R001']
        self.assertNotEqual(family_thread,resident_thread)
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.post('/api/residents/R001/case/reply',{'text':'僅回覆住民的虛構訊息'})
        self.assertEqual(self.detail()['selected_conversation']['recipient'],'demo-line-resident')
        self.selected_threads['R001'] = family_thread
        self.assertFalse(any(m['text']=='僅回覆住民的虛構訊息' for m in self.detail()['messages']))
        self.assertEqual(self.detail()['state'],'human_active')
        self.post('/api/residents/R001/case/resolve',{'note':'家屬案件完成'})
        self.assertEqual(self.service.detail(resident_thread)['state'],'human_active')
        self.assertEqual(self.service.detail(conversation('R001'))['messages'],[])

    def test_two_family_contacts_do_not_share_context(self):
        self.login()
        with self.store.db() as db:
            db.execute("""INSERT INTO users SELECT 'family2','family2','第二位家屬','family',password_hash
                          FROM users WHERE id='family'""")
            db.execute("INSERT INTO access VALUES('family2','R001')")
            db.execute("INSERT INTO line_links VALUES('family2','demo-line-family2','admin',?)",(stamp(),))
        self.line_send('想了解喘息服務')
        first = self.selected_threads['R001']
        self.line_send('想了解日照',actor='family2')
        second = self.selected_threads['R001']
        self.assertNotEqual(first,second)
        self.assertFalse(any(m['text']=='想了解喘息服務' for m in self.detail()['messages']))
        self.assertEqual(self.detail()['selected_conversation']['contact_id'],'family2')
        self.assertNotEqual(self.service.detail(first)['messages'],self.service.detail(second)['messages'])

    def test_board_lists_each_contact_case_and_cross_thread_handoff_is_rejected(self):
        self.login()
        self.line_send('轉人工')
        family_thread=self.selected_threads['R001']
        self.post('/api/residents/R001/case/claim',{})
        self.post('/api/residents/R001/case/handoff',self.progress(to_user='nurse2'))
        request_id=self.detail()['workflow']['handoff']['id']
        self.line_send('轉人工',actor='resident')
        resident_thread=self.selected_threads['R001']
        self.post('/api/residents/R001/case/claim',{})
        board=self.client.get('/api/board').get_json()
        self.assertEqual({q['conversation_id'] for q in board['work_queue']},{family_thread,resident_thread})
        self.assertEqual(next(c for c in board['cards'] if c['id']=='R001')['pending_count'],2)
        self.login('nurse2')
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',{'request_id':request_id}).status_code,403)
        self.selected_threads['R001']=family_thread
        self.assertFalse(self.detail()['workflow']['handoff']['stale'])
        self.assertEqual(self.post('/api/residents/R001/case/accept_handoff',{'request_id':request_id}).status_code,200)
        self.post('/api/residents/R001/case/reply',{'text':'已接收此家屬案件'})
        self.assertFalse(any(m['text']=='已接收此家屬案件' for m in self.service.detail(resident_thread)['messages']))

    def test_cross_resident_conversation_read_and_action_are_rejected(self):
        self.login()
        self.line_send('轉人工')
        thread=self.selected_threads['R001']
        case_id=self.detail()['case']['id']
        self.assertEqual(self.client.get('/api/residents/R002',query_string={'conversation_id':thread}).status_code,403)
        result=self.post('/api/residents/R002/case/claim',{'conversation_id':thread,'case_id':case_id})
        self.assertEqual(result.status_code,403)
        self.assertEqual(self.detail()['case']['status'],'pending')
        self.login('caregiver')
        self.assertEqual(self.client.get('/api/residents/R003',query_string={'conversation_id':thread}).status_code,403)

    def test_stale_case_id_cannot_target_a_new_case(self):
        self.open_owned_case()
        old=self.detail()['case']['id']
        self.post('/api/residents/R001/case/resolve',{'note':'完成'})
        self.send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{'case_id':old}).status_code,409)
        raw=self.client.post('/api/residents/R001/case/claim',json={},
                             headers={'X-CSRF-Token':self.csrf})
        self.assertEqual(raw.status_code,409)
        self.assertEqual(self.detail()['case']['status'],'pending')

    def test_contact_revoke_blocks_reply_and_keeps_history(self):
        self.login()
        self.line_send('轉人工')
        self.post('/api/residents/R001/case/claim',{})
        before=len(self.detail()['messages'])
        self.login('admin')
        self.post('/api/bindings',dict(user_id='family',resident_id='R001',allowed=False))
        self.login('nurse')
        self.assertFalse(self.detail()['selected_conversation']['active'])
        self.assertIsNone(self.detail()['selected_conversation']['recipient'])
        self.assertEqual(self.post('/api/residents/R001/case/reply',{'text':'不得送出'}).status_code,403)
        self.assertEqual(len(self.detail()['messages']),before)
        self.assertEqual(self.post('/api/residents/R001/case/resolve',{'note':'配對已撤銷，結案保留紀錄'}).status_code,200)

    def test_contact_revoke_during_generation_cancels_old_result(self):
        self.login('nurse')
        self.service.save_ai_settings({'ai_enabled':True,'daily_call_limit':200})
        self.line_send('想了解喘息服務')
        self.login('admin')
        thread=self.selected_threads['R001']
        self.assertTrue(self.service.detail(thread)['generations'])
        original=self.provider.generate
        def revoke(config,payload):
            self.assertEqual(self.post('/api/bindings',dict(user_id='family',resident_id='R001',allowed=False)).status_code,200)
            return original(config,payload)
        self.provider.generate=revoke
        self.service.process_one()
        detail=self.service.detail(thread)
        self.assertEqual(detail['generations'][0]['status'],'cancelled')
        self.assertFalse(any(m['source']=='grounded_generation' for m in detail['messages']))
        self.post('/api/bindings',dict(user_id='family',resident_id='R001',allowed=True))
        self.assertFalse(self.service.process_one())
        self.assertEqual(self.service.detail(thread)['generations'][0]['status'],'cancelled')

    def test_message_source_must_match_selected_conversation(self):
        self.login()
        self.line_send('想了解喘息服務')
        family=self.selected_threads['R001']
        result=self.post('/api/residents/R001/message',dict(
            text='不能寫入另一個對話',channel='demo_line',line_actor='resident',conversation_id=family))
        self.assertEqual(result.status_code,409)
        self.assertFalse(any(m['text']=='不能寫入另一個對話' for m in self.detail()['messages']))

    def test_legacy_shared_records_are_not_assigned_to_contacts(self):
        self.login()
        self.send('舊版共用的虛構紀錄')
        before=self.service.detail(conversation('R001'))['messages']
        with self.store.db() as db:
            db.execute('DROP TABLE contact_conversations')
        restored=create_app(self.directory,provider=OfflineProvider())
        self.assertEqual(restored.extensions['care_service'].detail(conversation('R001'))['messages'],before)
        threads=restored.extensions['care_conversations'].list(self.store.user('nurse'),'R001')
        for thread in threads:
            if thread['kind']=='contact':
                self.assertEqual(restored.extensions['care_service'].detail(thread['id'])['messages'],[])
        backups=list((self.directory/'backups').glob('before-contact-conversations-*'))
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups[0]/'core.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages WHERE conversation_id=?',
                                        (conversation('R001'),)).fetchone()[0],len(before))
        create_app(self.directory,provider=OfflineProvider())
        self.assertEqual(len(list((self.directory/'backups').glob('before-contact-conversations-*'))),1)

    def test_live_transport_cannot_use_a_logical_thread_as_recipient(self):
        self.login()
        self.line_send('轉人工')
        thread=self.selected_threads['R001']
        with self.service.db() as db:
            db.execute("UPDATE conversations SET transport='line' WHERE id=?",(thread,))
        with self.assertRaises(PermissionError):
            self.service.deliver(thread,'不得對外送出','human','operator')
        self.assertEqual(self.service.transport.calls,[])

    def test_stale_view_cannot_close_or_reply_after_new_message(self):
        self.login();self.line_send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        seen=self.detail()['case']['seen_message_id']
        self.line_send('長輩剛剛倒地')
        for action,payload in [('resolve',{'note':'依舊畫面結案'}),('reply',{'text':'依舊畫面回覆'})]:
            for stale in [seen,None]:
                response=self.post('/api/residents/R001/case/'+action,payload|{'seen_message_id':stale})
                self.assertEqual(response.status_code,409,(action,stale,response.get_json()))
        case=self.detail()['case']
        self.assertEqual((case['status'],case['trigger_risk']),('claimed','高'))
        self.assertGreater(case['seen_message_id'],seen)
        self.assertEqual(self.post('/api/residents/R001/case/resolve',{'note':'已查看最新訊息後結案'}).status_code,200)

    def test_revoking_case_owner_returns_case_to_pending(self):
        self.login();self.line_send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        thread=self.selected_threads['R001']
        self.login('admin')
        self.assertEqual(self.post('/api/bindings',dict(user_id='nurse',resident_id='R001',allowed=False)).status_code,200)
        source=self.service.detail(thread)
        self.assertEqual((source['case']['status'],source['case']['operator_id'],source['state']),('pending',None,'awaiting_takeover'))
        with self.service.db() as db:
            db.execute('ATTACH DATABASE ? AS care',(str(self.app.extensions['care_store'].path),))
            actions=[r[0] for r in db.execute('SELECT action FROM care.case_activity WHERE case_id=?',(source['case']['id'],))]
        self.assertIn('owner_access_revoked',actions)
        self.login('nurse2')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.assertEqual(self.post('/api/residents/R001/case/reply',{'text':'虛構：由有權護理師接續'}).status_code,200)

    def test_logout_ends_a_copied_session_cookie(self):
        self.login('caregiver')
        cookie=self.client.get_cookie('care_console_session').value
        self.assertEqual(self.client.get('/api/board').status_code,200)
        self.assertEqual(self.post('/api/logout',{}).status_code,200)
        self.client.set_cookie('care_console_session',cookie)
        self.assertEqual(self.client.get('/api/board').status_code,401)

    def test_manual_reports_cannot_reserve_facility_import_ids(self):
        self.login('caregiver')
        self.assertEqual(self.post('/api/residents/R001/observation',self.row(source_record_id='HIS-0001')).status_code,200)
        self.login()
        ids=[o['source_record_id'] for o in self.detail()['observations']]
        self.assertNotIn('HIS-0001',ids)
        self.assertTrue(any(i.startswith('MANUAL-') for i in ids))
        result=self.imported(self.row(source_record_id='HIS-0001'))
        self.assertEqual(result.status_code,200,result.get_json())
        self.assertEqual(result.get_json()['inserted'],1)
        reserved=self.imported(self.row(source_record_id='manual-123'))
        self.assertEqual(reserved.status_code,400)
        self.assertIn('第 2 列',reserved.get_json()['error'])
        conflict=self.imported(self.row(source_record_id='TEST-NEW'),self.row(source_record_id='HIS-0001',care_note='內容不同'))
        self.assertEqual(conflict.status_code,400)
        self.assertIn('第 3 列',conflict.get_json()['error'])

    def age_jobs(self, thread, seconds=700):
        old=(datetime.now(timezone.utc)-timedelta(seconds=seconds)).isoformat(timespec='seconds')
        with self.service.db() as db:
            db.execute('UPDATE generations SET created_at=? WHERE conversation_id=?',(old,thread))

    def test_expired_queued_job_fails_visibly_without_calling_model(self):
        self.login('nurse')
        self.service.save_ai_settings({'ai_enabled':True,'daily_call_limit':200})
        self.line_send('想了解喘息服務')
        thread=self.selected_threads['R001']
        self.assertEqual(self.service.detail(thread)['generations'][0]['status'],'queued')
        self.age_jobs(thread)
        calls=[]
        self.provider.generate=lambda config,payload:calls.append(1)
        self.assertTrue(self.service.process_one())
        detail=self.service.detail(thread)
        self.assertEqual(calls,[])
        self.assertEqual(detail['generations'][0]['status'],'failed')
        self.assertEqual(detail['case']['origin'],'generation_failure')
        self.assertEqual(detail['messages'][-1]['source'],'generation_failure')
        self.assertFalse(any(m['source']=='grounded_generation' for m in detail['messages']))

    def test_job_expiring_during_model_call_is_not_sent(self):
        self.login('nurse')
        self.service.save_ai_settings({'ai_enabled':True,'daily_call_limit':200})
        self.line_send('想了解喘息服務')
        thread=self.selected_threads['R001']
        original=self.provider.generate
        def slow(config,payload):
            self.age_jobs(thread)
            return original(config,payload)
        self.provider.generate=slow
        self.service.process_one()
        detail=self.service.detail(thread)
        self.assertEqual(detail['generations'][0]['status'],'failed')
        self.assertEqual(detail['case']['origin'],'generation_failure')
        self.assertFalse(any(m['source']=='grounded_generation' for m in detail['messages']))

    def test_expired_draft_cannot_be_approved_and_is_closed(self):
        self.login('nurse')
        self.service.save_ai_settings({'ai_enabled':True,'daily_call_limit':200})
        self.line_send('我剛量血壓是165/100，目前沒有不舒服')
        thread=self.selected_threads['R001']
        self.service.process_one()
        drafts=[j for j in self.service.detail(thread)['generations'] if j['status']=='draft']
        self.assertTrue(drafts,self.service.detail(thread)['generations'])
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.age_jobs(thread)
        response=self.post('/api/residents/R001/case/approve',dict(job_id=drafts[0]['id'],text='虛構核准',note='虛構審閱'))
        self.assertEqual(response.status_code,400)
        self.assertIn('超過有效時間',response.get_json()['error'])
        job=next(j for j in self.service.detail(thread)['generations'] if j['id']==drafts[0]['id'])
        self.assertEqual(job['status'],'cancelled')
        self.assertFalse(any(m['source']=='reviewed_generation' for m in self.service.detail(thread)['messages']))

    def test_worker_closes_expired_drafts(self):
        self.login('nurse')
        self.service.save_ai_settings({'ai_enabled':True,'daily_call_limit':200})
        self.line_send('我剛量血壓是165/100，目前沒有不舒服')
        thread=self.selected_threads['R001']
        self.service.process_one()
        self.age_jobs(thread)
        self.service.process_one()
        self.assertFalse([j for j in self.service.detail(thread)['generations'] if j['status']=='draft'])
        self.assertEqual(self.detail()['drafts'][0]['status'],'cancelled')

    def test_line_protocol_errors_are_reported_as_uncertain_delivery(self):
        import http.client
        from service import LineTransport, DeliveryError
        class Settings:
            def snapshot(self):
                return {'line_enabled':True,'access_token':'test-token-not-real'}
        transport=LineTransport(Settings())
        for exc in [http.client.IncompleteRead(b''),http.client.BadStatusLine('x')]:
            with patch('urllib.request.urlopen',side_effect=exc):
                with self.assertRaises(DeliveryError):
                    transport.send('push','U-test','虛構訊息',retry_key='k')

if __name__=='__main__':unittest.main(verbosity=2)
