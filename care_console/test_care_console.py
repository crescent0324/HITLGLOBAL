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

    def tearDown(self):
        self.service.stop_worker()
        self.network.stop()
        self.tmp.cleanup()

    def login(self, name='nurse'):
        response = self.post('/api/login', {'username': name, 'password': 'CareDemo2026!'})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.csrf = response.get_json()['csrf']

    def post(self, path, data):
        return self.client.post(path, json=data, headers={'X-CSRF-Token':self.csrf})

    def detail(self, rid='R001'):
        response=self.client.get('/api/residents/'+rid)
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

    def line_send(self, text, rid='R001', actor='family'):
        self.send(text,rid,'demo_line',actor)

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
        for role, count in [('admin',6),('nurse',6),('caregiver',2)]:
            self.login(role)
            body=self.client.get('/api/board').get_json()
            self.assertEqual(len(body['cards']),count)
            self.assertFalse(body['ai_enabled'])
            self.assertEqual(body['line_link']['user_id'],role)

    def test_family_and_resident_cannot_log_in_to_web(self):
        for role in ['family','resident']:
            self.assertEqual(self.post('/api/login',dict(username=role,password='CareDemo2026!')).status_code,403)
            self.assertEqual(self.client.get('/api/board').status_code,401)
            self.assertEqual(self.client.get('/api/residents/R001').status_code,401)
            self.assertEqual(self.post('/api/residents/R001/message',dict(text='測試')).status_code,401)
        self.assertEqual(set(self.client.get('/api/session').get_json()['roles']),{'admin','nurse','caregiver'})

    def test_caregiver_observation_cannot_set_assessment(self):
        self.login('caregiver')
        self.assertEqual(self.post('/api/residents/R001/observation',self.row(care_status='一般照護')).status_code,403)
        self.assertEqual(self.post('/api/residents/R001/observation',self.row()).status_code,200)
        self.assertEqual(self.detail()['observations'][0]['care_status'],'尚未評估')
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

    def test_shared_resident_conversation_keeps_manual_state(self):
        self.login('nurse');self.line_send('轉人工')
        self.assertEqual(self.post('/api/residents/R001/case/claim',{}).status_code,200)
        self.line_send('想了解日照',actor='resident')
        data=self.detail();self.assertEqual(data['state'],'human_active')
        self.assertEqual(data['messages'][-1]['actor'],'user')
        self.assertEqual(data['messages'][-1]['text'],'想了解日照')
        self.assertEqual(data['drafts'],[])
        self.assertEqual(data['messages'][-1]['author'],'住民體驗帳號')
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
        self.login('admin');self.send('轉人工')
        response=self.post('/api/backup',{})
        self.assertEqual(response.status_code,200)
        dest=Path(self.tmp.name)/'restored';dest.mkdir()
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(set(archive.namelist()),{'facility.sqlite3','core.sqlite3','manifest.json','environment.json','core-environment.json'})
            archive.extract('facility.sqlite3',dest);archive.extract('environment.json',dest)
            (dest/'core').mkdir();(dest/'core/research.sqlite3').write_bytes(archive.read('core.sqlite3'))
            (dest/'core/integration-environment.json').write_bytes(archive.read('core-environment.json'))
        response.close()
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
        self.assertEqual([q['id'] for q in queue],['R001'])
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
        self.line_send('補充：請確認明天的洽詢方式')
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
        self.assertEqual(self.detail()['line_contacts'],[])
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

if __name__=='__main__':unittest.main(verbosity=2)
