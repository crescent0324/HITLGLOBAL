"""Cursor expiry/mutations, streaming fingerprint parity and indexed schema safety."""
import json
import unittest
from unittest.mock import patch
from werkzeug.datastructures import MultiDict
import test_case_monitor as fixtures


class MonitorHardeningTests(unittest.TestCase):
    setUp=fixtures.CaseMonitorTests.setUp
    tearDown=fixtures.CaseMonitorTests.tearDown
    client=fixtures.CaseMonitorTests.client
    post=fixtures.CaseMonitorTests.post
    case=fixtures.CaseMonitorTests.case
    action=fixtures.CaseMonitorTests.action
    progress=fixtures.CaseMonitorTests.progress
    monitor=fixtures.CaseMonitorTests.monitor
    timeline=fixtures.CaseMonitorTests.timeline
    grant=fixtures.CaseMonitorTests.grant
    restart=fixtures.CaseMonitorTests.restart

    def cursor_pair(self):
        first=self.case('R001',claimed=True);self.case('R002')
        return first,self.monitor(limit='1')['next_cursor']

    def old_page(self,cursor):
        return self.client('head_nurse').get('/api/case-monitor',query_string={'limit':'1','cursor':cursor})

    def test_natural_expiry_is_409_and_tampering_is_400(self):
        case,cursor=self.cursor_pair()
        tokens=self.app.extensions['care_monitor'].tokens
        payload=tokens.loads(cursor)
        with patch('itsdangerous.timed.TimestampSigner.get_timestamp',return_value=1):
            expired=tokens.dumps(payload)
        self.assertEqual(self.old_page(expired).status_code,409)
        self.assertEqual(self.old_page(cursor+'tampered').status_code,400)

    def test_new_case_and_status_changes_invalidate_old_page(self):
        first,cursor=self.cursor_pair()
        self.assertEqual(self.action(first,'resolve',note='虛構完成').status_code,200)
        self.assertEqual(self.old_page(cursor).status_code,409)
        cursor=self.monitor(status='all',limit='1')['next_cursor']
        self.case('R001')
        result=self.client('head_nurse').get('/api/case-monitor',query_string={'status':'all','limit':'1','cursor':cursor})
        self.assertEqual(result.status_code,409)

    def test_handoff_acceptance_and_owner_revocation_invalidate_old_page(self):
        first,cursor=self.cursor_pair()
        result=self.action(first,'handoff',revision=0,summary='虛構進度',next_action='虛構下一步',waiting_for='',to_user='nurse2')
        self.assertEqual(result.status_code,200)
        cursor=self.monitor(limit='1')['next_cursor']
        with self.store.db() as db:
            request=db.execute('SELECT id FROM handoff_requests WHERE case_id=?',(first['case_id'],)).fetchone()[0]
        self.assertEqual(self.action(first,'accept_handoff',uid='nurse2',request_id=request).status_code,200)
        self.assertEqual(self.old_page(cursor).status_code,409)
        cursor=self.monitor(limit='1')['next_cursor']
        self.grant('nurse2','R001',False)
        self.assertEqual(self.old_page(cursor).status_code,409)

    def test_scope_shrink_retry_returns_only_current_authorized_cases(self):
        first,cursor=self.cursor_pair();self.grant('head_nurse','R001',False)
        self.assertEqual(self.old_page(cursor).status_code,409)
        current=self.monitor(limit='1')
        self.assertEqual(current['scope_resident_ids'],['R002'])
        self.assertTrue(all(c['resident']['id']=='R002' for c in current['cases']))
        self.assertEqual(self.timeline(first).status_code,404)

    def test_sql_statistics_match_original_dto_semantics(self):
        self.cursor_pair()
        monitor=self.app.extensions['care_monitor'];user=self.store.user('head_nurse')
        for status in ['all','open','pending','claimed','closed']:
            filters=monitor.parameters(MultiDict({'status':status}))
            with self.app.extensions['care_workflow'].transaction() as db:
                query,values=monitor.query(user,filters)
                items=[monitor.item(dict(r)) for r in db.execute(query,values)]
            stats=self.monitor(status=status)['stats']
            self.assertEqual(stats['total_cases'],len(items))
            for key in ['pending','claimed','closed']:
                self.assertEqual(stats[key+'_cases'],sum(c['status']==key for c in items))
            self.assertEqual(stats['pending_handoffs'],sum(bool(c['handoff'] and c['handoff']['valid']) for c in items))
            self.assertEqual(stats['stale_handoffs'],sum(bool(c['handoff'] and not c['handoff']['valid']) for c in items))

    def test_streamed_fingerprint_is_byte_equivalent_to_full_list_hash(self):
        self.cursor_pair();monitor=self.app.extensions['care_monitor'];user=self.store.user('head_nurse')
        with self.app.extensions['care_workflow'].transaction() as db:
            query,values=monitor.query(user,monitor.parameters(MultiDict({'status':'all'})))
            expected=monitor.digest([dict(r) for r in db.execute(query,values)])
            self.assertEqual(monitor.fingerprint(db.execute(query,values)),expected)

    def test_indexes_exist_and_restart_does_not_reseed_or_repeat_upgrade(self):
        self.cursor_pair()
        with self.service.db() as db:
            indexes={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            count=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
        self.assertTrue({'monitor_cases_by_thread','monitor_messages_by_thread'}<=indexes)
        before=list((self.directory/'backups').glob('before-case-monitor-indexes-v3-*'))
        self.restart()
        self.assertEqual(list((self.directory/'backups').glob('before-case-monitor-indexes-v3-*')),before)
        with self.service.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM cases').fetchone()[0],count)

    def test_index_upgrade_backup_failure_preserves_existing_schema(self):
        from migrations import MONITOR_INDEX_MIGRATION
        self.case()
        with self.app.extensions['care_workflow'].transaction() as db:
            db.execute('DELETE FROM care.meta WHERE key=?',(MONITOR_INDEX_MIGRATION,))
            db.execute('DROP INDEX monitor_cases_by_thread')
            db.execute('DROP INDEX monitor_messages_by_thread')
        with patch('app.backup_before_monitor_indexes',side_effect=OSError('synthetic index backup failure')):
            with self.assertRaisesRegex(OSError,'synthetic index backup failure'):self.restart()
        with self.service.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'monitor_%_by_thread'").fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM cases').fetchone()[0],1)


if __name__=='__main__':
    unittest.main()
