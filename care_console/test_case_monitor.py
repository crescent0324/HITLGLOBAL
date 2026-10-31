"""Black-box scope, read-only monitoring, history and upgrade regression tests."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import json
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from app import create_app
from integration import OfflineProvider
from care_store import stamp
from migrations import MONITOR_MIGRATION


class CaseMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)/'data'
        self.network = patch.object(socket,'create_connection',side_effect=AssertionError('External network forbidden'))
        self.network.start()
        self.app = create_app(self.directory,provider=OfflineProvider())
        self.app.config['TESTING'] = True
        self.store = self.app.extensions['care_store']
        self.service = self.app.extensions['care_service']
        self.clients = {}
        self.extra = []

    def tearDown(self):
        for app in [self.app,*self.extra]:
            app.extensions['care_service'].stop_worker()
        self.network.stop()
        self.tmp.cleanup()

    def client(self, uid):
        if uid not in self.clients:
            client = self.app.test_client()
            token = client.get('/api/session').get_json()['csrf']
            result = client.post('/api/login',json={'username':uid,'password':'CareDemo2026!'},headers={'X-CSRF-Token':token})
            self.assertEqual(result.status_code,200,result.get_json())
            self.clients[uid] = (client,result.get_json()['csrf'])
        return self.clients[uid][0]

    def post(self, uid, path, body):
        client = self.client(uid)
        return client.post(path,json=body,headers={'X-CSRF-Token':self.clients[uid][1]})

    def case(self, rid='R001', claimed=False, text='虛構：轉人工'):
        result = self.post('nurse',f'/api/residents/{rid}/message',{'text':text,'channel':'web'})
        self.assertEqual(result.status_code,200,result.get_json())
        cid = result.get_json()['conversation_id']
        source = self.client('nurse').get('/api/residents/'+rid,query_string={'conversation_id':cid}).get_json()
        case = {'case_id':source['case']['id'],'conversation_id':cid,'rid':rid}
        if claimed:
            self.assertEqual(self.action(case,'claim').status_code,200)
        return case

    def action(self, case, action, uid='nurse', **body):
        with self.app.extensions['care_service'].db() as db:
            seen = db.execute('SELECT COALESCE(MAX(id),0) FROM messages WHERE conversation_id=?',
                              (case['conversation_id'],)).fetchone()[0]
        return self.post(uid,f"/api/residents/{case['rid']}/case/{action}",
                         {'case_id':case['case_id'],'conversation_id':case['conversation_id'],'seen_message_id':seen,**body})

    def progress(self, case, revision=0, **changes):
        return self.action(case,'progress',revision=revision,summary='虛構已處理 '+str(revision),
                           next_action='虛構下一步 '+str(revision),waiting_for='虛構待確認',**changes)

    def monitor(self, **query):
        response = self.client('head_nurse').get('/api/case-monitor',query_string=query)
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()

    def timeline(self, case, **query):
        return self.client('head_nurse').get(f"/api/case-monitor/{case['case_id']}/timeline",query_string=query)

    def grant(self, uid, rid, allowed):
        result = self.post('admin','/api/bindings',{'user_id':uid,'resident_id':rid,'allowed':allowed})
        self.assertEqual(result.status_code,200,result.get_json())

    def restart(self):
        app = create_app(self.directory,provider=OfflineProvider())
        self.extra.append(app)
        return app

    def test_monitor_is_head_nurse_only_and_anonymous_is_rejected(self):
        case = self.case()
        self.assertEqual(self.app.test_client().get('/api/case-monitor').status_code,401)
        for uid in ['admin','nurse','caregiver']:
            for path in ['/api/case-monitor',f"/api/case-monitor/{case['case_id']}/timeline"]:
                response = self.client(uid).get(path)
                self.assertEqual(response.status_code,403,(uid,path))
                self.assertEqual(set(response.get_json()),{'error'})

    def test_background_reads_do_not_reissue_auth_cookie_after_logout_race(self):
        case=self.case()
        # An older background response must not restore a pre-logout cookie.
        for uid,path in [('head_nurse','/api/case-monitor'),('nurse','/api/board'),('admin','/api/bindings')]:
            client=self.client(uid)
            response=client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertNotIn('Set-Cookie',response.headers)
            self.assertNotIn('Set-Cookie',client.get('/api/session').headers)
            result=self.post(uid,'/api/logout',{})
            self.assertEqual(result.status_code,200)
            self.assertIn('Set-Cookie',result.headers)
            self.assertEqual(client.get(path).status_code,401)

    def test_it_cannot_read_or_write_clinical_content_or_download_backup(self):
        case = self.case(claimed=True,text='虛構祕密家屬原文：轉人工')
        self.progress(case)
        self.assertEqual(self.client('admin').get('/api/bindings').status_code,200)
        self.assertEqual(self.client('admin').get('/api/knowledge').status_code,200)
        for path in ['/api/board','/api/residents/R001','/api/beds','/api/template.csv','/api/case-monitor']:
            result = self.client('admin').get(path)
            self.assertEqual(result.status_code,403,path)
            self.assertNotIn('虛構祕密',result.get_data(as_text=True))
        for path in ['/api/residents/R001/message','/api/residents/R001/observation','/api/import','/api/backup']:
            self.assertEqual(self.post('admin',path,{}).status_code,403,path)
        self.assertEqual(self.action(case,'reply',uid='admin',text='不得代回覆').status_code,403)
        self.assertEqual(self.post('admin','/api/bindings',{'user_id':'admin','resident_id':'R001','allowed':True}).status_code,403)
        self.assertFalse(self.store.allowed(self.store.user('admin'),'R001'))
        for method in [self.store.observations,self.store.audit,self.store.authors,self.app.extensions['care_conversations'].list]:
            with self.assertRaises(PermissionError):
                method(self.store.user('admin'),'R001')

    def test_beds_follow_scope_changes_in_existing_nurse_sessions(self):
        for uid in ['nurse', 'nurse2']:
            with self.subTest(uid=uid):
                client = self.client(uid)
                account = self.store.user(uid)
                self.assertEqual(len(client.get('/api/beds').get_json()['beds']), 8)
                for number in range(2, 7):
                    self.grant(uid, f'R{number:03}', False)
                response = client.get('/api/beds', query_string={'user_id': 'nurse2', 'resident_id': 'R003'})
                self.assertEqual(response.status_code, 200)
                beds = response.get_json()['beds']
                self.assertEqual(beds, [
                    {'id': 'A101', 'ward': 'A 區', 'resident_id': 'R001'},
                    {'id': 'A107', 'ward': 'A 區', 'resident_id': None},
                    {'id': 'A108', 'ward': 'A 區', 'resident_id': None}])
                self.assertEqual(self.store.beds(account), beds)
                self.assertEqual(client.get('/api/residents/R003').status_code, 403)
                self.grant(uid, 'R001', False)
                empty_beds = beds[1:]
                self.assertEqual(client.get('/api/board').get_json()['cards'], [])
                self.assertEqual(client.get('/api/beds').get_json()['beds'], empty_beds)
                self.assertEqual(self.store.beds(account), empty_beds)
                self.grant(uid, 'R004', True)
                self.assertEqual(client.get('/api/beds').get_json()['beds'], [
                    {'id': 'A104', 'ward': 'A 區', 'resident_id': 'R004'}, *empty_beds])

    def test_scoped_beds_keep_empty_choices_and_move_validation(self):
        client = self.client('nurse')
        for number in range(2, 7):
            self.grant('nurse', f'R{number:03}', False)
        self.assertEqual(self.post('nurse', '/api/residents/R001/move', {'bed_id': 'A102'}).status_code, 400)
        self.assertEqual(self.post('nurse', '/api/residents/R002/move', {'bed_id': 'A108'}).status_code, 403)
        self.assertEqual(self.post('nurse', '/api/residents/R001/move', {'bed_id': 'A107'}).status_code, 200)
        self.assertEqual(client.get('/api/beds').get_json()['beds'], [
            {'id': 'A101', 'ward': 'A 區', 'resident_id': None},
            {'id': 'A107', 'ward': 'A 區', 'resident_id': 'R001'},
            {'id': 'A108', 'ward': 'A 區', 'resident_id': None}])
        self.assertEqual(client.get('/api/board').get_json()['cards'][0]['bed_id'], 'A107')
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT bed_id FROM placements WHERE resident_id='R002' AND ended_at IS NULL").fetchone()['bed_id'], 'A102')

    def test_beds_do_not_expose_inactive_resident_placements_as_empty(self):
        client = self.client('nurse')
        with self.store.db() as db:
            db.execute("UPDATE residents SET active=0 WHERE id='R002'")
        beds = client.get('/api/beds').get_json()['beds']
        self.assertEqual({b['id'] for b in beds}, {'A101', 'A103', 'A104', 'A105', 'A106', 'A107', 'A108'})
        self.assertEqual({b['id'] for b in beds if b['resident_id'] is None}, {'A107', 'A108'})
        self.assertNotIn('R002', {b['resident_id'] for b in beds})

    def test_bed_scope_filter_does_not_expand_other_roles(self):
        self.assertEqual(self.app.test_client().get('/api/beds').status_code, 401)
        for uid in ['admin', 'head_nurse', 'caregiver']:
            with self.subTest(uid=uid):
                self.assertEqual(self.client(uid).get('/api/beds').status_code, 403)
        for uid in ['admin', 'head_nurse', 'caregiver', 'family', 'resident']:
            with self.subTest(store_role=uid), self.assertRaises(PermissionError):
                self.store.beds(self.store.user(uid))

    def test_head_nurse_is_read_only_and_cannot_extend_own_scope(self):
        case = self.case(claimed=True)
        self.assertEqual(self.timeline(case).status_code,200)
        for action in ['claim','reply','progress','handoff','accept_handoff','cancel_handoff','approve','reject','resolve']:
            self.assertEqual(self.action(case,action,uid='head_nurse').status_code,403,action)
        for path in ['/api/residents/R001/observation','/api/residents/R001/move','/api/import','/api/backup','/api/bindings']:
            self.assertEqual(self.post('head_nurse',path,{}).status_code,403,path)
        self.assertEqual(self.client('head_nurse').get('/api/board').status_code,403)
        self.assertEqual(self.client('head_nurse').get('/api/residents/R001').status_code,403)
        self.assertEqual(self.post('head_nurse','/api/case-monitor',{}).status_code,405)

    def test_scope_is_applied_to_rows_statistics_owner_options_and_timeline(self):
        allowed = self.case('R001',claimed=True)
        hidden = self.case('R003',claimed=True,text='不可透露的第三位住民：轉人工')
        with patch.object(self.service,'detail',side_effect=AssertionError('Monitor must not fetch whole conversations')):
            data = self.monitor(status='all')
            self.assertEqual([c['id'] for c in data['cases']],[allowed['case_id']])
            self.assertEqual(data['stats']['total_cases'],1)
            response = self.timeline(hidden)
        self.assertEqual(response.status_code,404)
        self.assertNotIn('R003',json.dumps(data))
        self.assertNotIn('不可透露',json.dumps(data,ensure_ascii=False))

    def test_scope_and_role_revocation_affect_existing_sessions_and_internal_reader(self):
        case = self.case()
        self.monitor()
        stale_user = self.store.user('head_nurse')
        self.grant('head_nurse','R001',False)
        self.assertEqual(self.monitor()['cases'],[])
        self.assertEqual(self.timeline(case).status_code,404)
        self.restart()
        self.assertFalse(self.store.allowed(self.store.user('head_nurse'),'R001'))
        with self.store.db() as db:
            db.execute("UPDATE users SET role='admin' WHERE id='head_nurse'")
        self.assertEqual(self.client('head_nurse').get('/api/case-monitor').status_code,403)
        with self.assertRaises(PermissionError):
            from werkzeug.datastructures import MultiDict
            self.app.extensions['care_monitor'].list(stale_user,MultiDict())

    def test_overlap_statistics_and_unset_deadlines_are_not_invented(self):
        first = self.case('R001',claimed=True)
        self.case('R002',claimed=True)
        self.action(first,'resolve',note='虛構完成')
        pending = self.case('R001')
        self.action(pending,'claim')
        self.assertEqual(self.action(pending,'handoff',revision=0,summary='虛構交班',next_action='下一班確認',waiting_for='',to_user='nurse2').status_code,200)
        # Add a second contact on R001 to obtain a third independent open case.
        self.grant('family','R002',True)
        response=self.post('nurse','/api/residents/R002/message',{'text':'轉人工','channel':'demo_line','line_actor':'family'})
        self.assertEqual(response.status_code,200)
        with self.service.db() as db:
            db.execute("UPDATE cases SET created_at='2000-01-01T00:00:00+00:00' WHERE status!='closed'")
        data=self.monitor()
        self.assertEqual(data['stats']['pending_cases'],1)
        self.assertEqual(data['stats']['claimed_cases'],2)
        self.assertEqual(data['stats']['pending_handoffs'],1)
        self.assertEqual(data['stats']['open_cases'],3)
        self.assertEqual(data['stats']['deadline_unset'],3)
        self.assertIsNone(data['stats']['overdue_cases'])
        self.assertTrue(all(c['due_at'] is None and c['overdue'] is None and c['deadline_status']=='unset' for c in data['cases']))
        self.assertEqual(self.monitor(status='all')['stats']['closed_cases'],1)

    def test_filter_status_owner_and_timezone_aware_created_time(self):
        first=self.case('R001',claimed=True);second=self.case('R002')
        with self.service.db() as db:
            db.execute("UPDATE cases SET created_at='2026-10-20T01:00:00+00:00' WHERE id=?",(first['case_id'],))
            db.execute("UPDATE cases SET created_at='2026-10-21T01:00:00+00:00' WHERE id=?",(second['case_id'],))
        self.assertEqual([c['id'] for c in self.monitor(status='claimed',owner_id='nurse')['cases']],[first['case_id']])
        self.assertEqual([c['id'] for c in self.monitor(owner_id='__unassigned__')['cases']],[second['case_id']])
        data=self.monitor(**{'from':'2026-10-21T09:00:00+08:00','to':'2026-10-21T09:00:00+08:00'})
        self.assertEqual([c['id'] for c in data['cases']],[second['case_id']])
        self.assertEqual(self.monitor(owner_id="' OR 1=1 --")['cases'],[])

    def test_signed_pagination_cannot_change_scope_filter_or_viewer(self):
        self.case('R001',claimed=True);self.case('R002')
        first=self.monitor(limit='1');cursor=first['next_cursor']
        self.assertIsNotNone(cursor)
        second=self.monitor(limit='1',cursor=cursor)
        self.assertNotEqual(first['cases'][0]['id'],second['cases'][0]['id'])
        self.assertIsNone(second['next_cursor'])
        for query in [{'limit':'1','cursor':cursor+'x'},{'limit':'2','cursor':cursor},{'limit':'1','status':'closed','cursor':cursor}]:
            result=self.client('head_nurse').get('/api/case-monitor',query_string=query)
            self.assertIn(result.status_code,[400,409]);self.assertEqual(set(result.get_json()),{'error'})
        with self.store.db() as db:
            db.execute("INSERT INTO users SELECT 'head2','head2','另一位護理長','head_nurse',password_hash FROM users WHERE id='head_nurse'")
            db.execute("INSERT INTO access VALUES('head2','R001')")
            db.execute("INSERT INTO access VALUES('head2','R002')")
        self.assertEqual(self.client('head2').get('/api/case-monitor',query_string={'limit':'1','cursor':cursor}).status_code,409)
        self.grant('head_nurse','R001',False)
        self.assertEqual(self.client('head_nurse').get('/api/case-monitor',query_string={'limit':'1','cursor':cursor}).status_code,409)

    def test_invalid_filters_are_rejected_without_returning_cases(self):
        self.case()
        for query in [{'limit':'0'},{'limit':'51'},{'limit':'１'},{'status':'unknown'},
                      {'from':'2026-10-20T08:00:00'},{'from':'2026-10-21T00:00:00Z','to':'2026-10-20T00:00:00Z'},
                      {'owner_id':'x'*81},{'surprise':'1'},[('status','open'),('status','closed')]]:
            result=self.client('head_nurse').get('/api/case-monitor',query_string=query)
            self.assertEqual(result.status_code,400,query)
            self.assertEqual(set(result.get_json()),{'error'})

    def test_new_message_invalidates_cursor_and_handoff_without_transferring_owner(self):
        case=self.case(claimed=True)
        self.action(case,'handoff',revision=0,summary='虛構進度',next_action='確認',waiting_for='',to_user='nurse2')
        self.case('R002')
        first=self.monitor(limit='1');cursor=first['next_cursor']
        self.assertEqual(first['stats']['pending_handoffs'],1)
        with self.store.db() as db:
            request_id=db.execute('SELECT id FROM handoff_requests WHERE case_id=?',(case['case_id'],)).fetchone()[0]
        self.post('nurse','/api/residents/R001/message',{'text':'想了解日照','channel':'web'})
        data=self.monitor()
        self.assertEqual(data['stats']['pending_handoffs'],0)
        self.assertEqual(data['stats']['stale_handoffs'],1)
        item=next(c for c in data['cases'] if c['id']==case['case_id'])
        self.assertEqual(item['owner']['id'],'nurse');self.assertTrue(item['handoff']['stale'])
        self.assertEqual(self.action(case,'accept_handoff',uid='nurse2',request_id=request_id).status_code,409)
        self.assertEqual(self.client('head_nurse').get('/api/case-monitor',query_string={'limit':'1','cursor':cursor}).status_code,409)

    def test_revoked_nurse_scope_blocks_old_owner_and_invalid_handoff(self):
        case=self.case(claimed=True)
        self.action(case,'handoff',revision=0,summary='虛構進度',next_action='確認',waiting_for='',to_user='nurse2')
        with self.store.db() as db:
            request_id=db.execute('SELECT id FROM handoff_requests WHERE case_id=?',(case['case_id'],)).fetchone()[0]
        self.grant('nurse','R001',False)
        self.assertEqual(self.action(case,'reply',text='失權後不能回覆').status_code,403)
        # Revocation returns the case to pending and cancels the old owner's handoff, so the
        # stale handoff cannot be accepted and an authorized nurse can claim the case instead.
        self.assertEqual(self.action(case,'accept_handoff',uid='nurse2',request_id=request_id).status_code,403)
        item=self.monitor()['cases'][0]
        self.assertEqual(item['status'],'pending');self.assertIsNone(item['handoff'])
        self.assertEqual(self.action(case,'claim',uid='nurse2').status_code,200)
        self.restart()
        self.assertFalse(self.store.allowed(self.store.user('nurse'),'R001'))

    def test_timeline_retains_progress_revisions_and_pages_only_this_case(self):
        case=self.case(claimed=True)
        for revision in range(3):
            self.assertEqual(self.progress(case,revision).status_code,200)
        self.action(case,'reply',text='虛構回覆原文不預載至監控')
        self.action(case,'resolve',note='虛構結果')
        other=self.case(claimed=True)
        self.action(other,'progress',summary='另一案件不可混入',next_action='另一案件下一步',waiting_for='',revision=0)
        events=[];cursor=None
        while True:
            query={'limit':'2'}
            if cursor:query['cursor']=cursor
            response=self.timeline(case,**query)
            self.assertEqual(response.status_code,200,response.get_json())
            body=response.get_json();events.extend(body['events']);cursor=body['next_cursor']
            if not cursor:break
        revisions=[e['payload']['revision'] for e in events if e['action']=='case_progress_saved']
        self.assertEqual(sorted(revisions),[1,2,3])
        self.assertEqual(body['case']['close_note'],'虛構結果')
        serialized=json.dumps(events,ensure_ascii=False)
        self.assertNotIn('另一案件',serialized);self.assertNotIn('虛構回覆原文',serialized)
        self.assertTrue(any(e['action']=='case_resolve' for e in events))

    def test_monitor_reads_do_not_change_case_messages_drafts_or_audit(self):
        case=self.case(claimed=True)
        def snapshot():
            with self.service.db() as db:
                core={'core.'+table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in ['cases','messages','generations','audit']}
            with self.store.db() as db:
                core.update({'care.'+table:[tuple(r) for r in db.execute('SELECT * FROM '+table)] for table in ['case_notes','handoff_requests','case_activity','audit']})
            return core
        before=snapshot()
        self.monitor();self.timeline(case)
        self.assertEqual(snapshot(),before)

    def legacy_role_fixture(self, case):
        with self.service.db() as db:
            db.execute("UPDATE cases SET operator='admin',operator_id='admin' WHERE id=?",(case['case_id'],))
            db.execute('ALTER TABLE cases DROP COLUMN due_at')
        with self.store.db() as db:
            db.execute('DELETE FROM meta WHERE key=?',(MONITOR_MIGRATION,))
            db.execute("UPDATE users SET display_name='管理者體驗帳號' WHERE id='admin'")
            db.execute("DELETE FROM access WHERE user_id IN ('nurse','nurse2','head_nurse')")
            db.execute("DELETE FROM users WHERE id='head_nurse'")
            db.execute('DELETE FROM staff_role_migrations')
            db.execute('DROP TABLE case_activity')

    def test_upgrade_preserves_passwords_history_and_old_nurse_scope_once(self):
        case=self.case(claimed=True);self.progress(case)
        with self.store.db() as db:
            password=db.execute("SELECT password_hash FROM users WHERE id='admin'").fetchone()[0]
        self.legacy_role_fixture(case)
        restored=self.restart();service=restored.extensions['care_service'];store=restored.extensions['care_store']
        source=service.detail(case['conversation_id'])
        self.assertEqual(source['case']['status'],'pending');self.assertIsNone(source['case']['operator_id'])
        with store.db() as db:
            self.assertEqual(db.execute("SELECT password_hash FROM users WHERE id='admin'").fetchone()[0],password)
            self.assertEqual(db.execute('SELECT summary FROM case_notes WHERE case_id=?',(case['case_id'],)).fetchone()[0],'虛構已處理 0')
            self.assertEqual(db.execute("SELECT COUNT(*) FROM access WHERE user_id='nurse2'").fetchone()[0],6)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM access WHERE user_id='head_nurse'").fetchone()[0],2)
        backups=list((self.directory/'backups').glob('before-staff-scope-monitor-v2-*'))
        self.assertEqual(len(backups),1)
        with closing(sqlite3.connect(backups[0]/'core.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT operator_id FROM cases WHERE id=?',(case['case_id'],)).fetchone()[0],'admin')
            self.assertNotIn('due_at',{r[1] for r in db.execute('PRAGMA table_info(cases)')})
        self.assertFalse(any(p.name in {'session.key','config.local.json'} for p in backups[0].iterdir()))
        with store.db() as db:
            db.execute("DELETE FROM access WHERE user_id='nurse2' AND resident_id='R001'")
        again=self.restart()
        self.assertFalse(again.extensions['care_store'].allowed(store.user('nurse2'),'R001'))
        self.assertEqual(len(list((self.directory/'backups').glob('before-staff-scope-monitor-v2-*'))),1)

    def test_upgrade_failure_rolls_back_role_scope_deadline_and_marker(self):
        case=self.case(claimed=True);self.legacy_role_fixture(case)
        with patch('workflow.StaffWorkflow.activity',side_effect=RuntimeError('synthetic migration fault')):
            with self.assertRaises(RuntimeError):self.restart()
        with self.service.db() as db:
            self.assertNotIn('due_at',{r['name'] for r in db.execute('PRAGMA table_info(cases)')})
            self.assertEqual(db.execute('SELECT operator_id FROM cases WHERE id=?',(case['case_id'],)).fetchone()[0],'admin')
        with self.store.db() as db:
            self.assertIsNone(db.execute('SELECT 1 FROM meta WHERE key=?',(MONITOR_MIGRATION,)).fetchone())
            self.assertIsNone(db.execute("SELECT 1 FROM users WHERE id='head_nurse'").fetchone())
            self.assertEqual(db.execute("SELECT COUNT(*) FROM access WHERE user_id='nurse'").fetchone()[0],0)
        self.restart()

    def test_monitor_upgrade_snapshot_failure_aborts_before_mutation(self):
        case=self.case(claimed=True);self.legacy_role_fixture(case)
        with patch('app.backup_before_monitor_upgrade',side_effect=OSError('synthetic backup failure')):
            with self.assertRaises(OSError):self.restart()
        with self.service.db() as db:
            self.assertNotIn('due_at',{r['name'] for r in db.execute('PRAGMA table_info(cases)')})

    def test_upgrade_refuses_head_account_id_collision_without_privilege_promotion(self):
        case=self.case(claimed=True);self.legacy_role_fixture(case)
        with self.store.db() as db:
            db.execute("INSERT INTO users SELECT 'head_nurse','custom-contact','既有外部身分','family',password_hash FROM users WHERE id='family'")
        with self.assertRaises(ValueError):self.restart()
        with self.store.db() as db:
            row=db.execute("SELECT username,role FROM users WHERE id='head_nurse'").fetchone()
            self.assertEqual(tuple(row),('custom-contact','family'))
            self.assertIsNone(db.execute('SELECT 1 FROM meta WHERE key=?',(MONITOR_MIGRATION,)).fetchone())
        with self.service.db() as db:
            self.assertNotIn('due_at',{r['name'] for r in db.execute('PRAGMA table_info(cases)')})


if __name__=='__main__':
    unittest.main()
