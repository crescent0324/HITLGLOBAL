"""Synthetic snapshots: sensitivity, atomic publication, failure retention and restore."""
from contextlib import closing
from pathlib import Path
import hashlib
import json
import sqlite3
import tempfile
import unittest
import sys
from unittest.mock import patch
import zipfile
import backup_local
import migrations
sys.path.insert(0,str(Path(__file__).resolve().parent/'core'))
import conversations


class BackupHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        (self.directory/'core').mkdir()
        (self.directory/'environment.json').write_text(json.dumps({'mode':'synthetic_local_demo','schema':1}))
        (self.directory/'core/integration-environment.json').write_text('{"mode":"synthetic"}')
        (self.directory/'session.key').write_text('excluded-test-session-material')
        (self.directory/'core/config.local.json').write_text('{"secret":"excluded-test-configuration"}')
        with closing(sqlite3.connect(self.directory/'facility.sqlite3')) as db:
            db.executescript("CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE users(id TEXT,password_hash TEXT); INSERT INTO users VALUES('fake','scrypt:synthetic-hash'); CREATE TABLE notes(value TEXT); INSERT INTO notes VALUES('synthetic business data');")
        with closing(sqlite3.connect(self.directory/'core/research.sqlite3')) as db:
            db.execute('CREATE TABLE cases(id INTEGER PRIMARY KEY,status TEXT)')
            db.commit()

    def tearDown(self):
        self.tmp.cleanup()

    def fingerprint(self):
        return {str(p.relative_to(self.directory)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.directory.rglob('*') if p.is_file() and 'backups' not in p.parts}

    def assert_manifest(self, manifest):
        self.assertTrue(manifest['credentials_included'], 'password hashes are credential material')
        self.assertFalse(manifest['plaintext_passwords_included'])
        self.assertTrue(manifest['password_hashes_included'])
        self.assertFalse(manifest['session_keys_included'])
        self.assertFalse(manifest['api_configuration_included'])
        self.assertTrue(manifest['business_data_included'])
        self.assertEqual(manifest['status'],'complete')

    def test_offline_manifest_describes_hashes_and_business_data(self):
        path=backup_local.create_snapshot(self.directory)
        with zipfile.ZipFile(path) as archive:
            self.assert_manifest(json.loads(archive.read('manifest.json')))
            self.assertNotIn('session.key',archive.namelist())
            self.assertNotIn('config.local.json',archive.namelist())
            restored=self.directory/'restored.sqlite3'
            restored.write_bytes(archive.read('facility.sqlite3'))
        with closing(sqlite3.connect(restored)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT password_hash FROM users').fetchone()[0],'scrypt:synthetic-hash')

    def test_all_upgrade_snapshot_manifests_describe_sensitive_contents(self):
        for backup in [migrations.backup_before_owner_migration,migrations.backup_before_monitor_upgrade,conversations.backup_before_thread_schema]:
            backup(self.directory)
        completed=list((self.directory/'backups').glob('before-*'))
        self.assertEqual(len(completed),3)
        for path in completed:
            self.assert_manifest(json.loads((path/'manifest.json').read_text()))

    def test_failed_zip_is_never_published_as_a_completed_snapshot(self):
        before=self.fingerprint()
        with patch.object(zipfile.ZipFile,'write',side_effect=OSError('synthetic write failure')):
            with self.assertRaises(OSError):backup_local.create_snapshot(self.directory)
        self.assertEqual(list((self.directory/'backups').glob('care-demo-*.zip')),[])
        self.assertEqual(self.fingerprint(),before)
        incomplete=list((self.directory/'backups').glob('.incomplete-*'))
        self.assertEqual(len(incomplete),1,'failure evidence must remain distinguishable from completed backups')
        self.assertEqual(json.loads((incomplete[0]/'failure.json').read_text())['status'],'incomplete')

    def test_failed_upgrade_does_not_publish_partial_or_modify_old_backups(self):
        migrations.backup_before_owner_migration(self.directory)
        previous={str(p):p.read_bytes() for p in (self.directory/'backups').rglob('*') if p.is_file()}
        before=self.fingerprint()
        with patch.object(Path,'write_bytes',side_effect=OSError('synthetic marker copy failure')):
            with self.assertRaises(OSError):migrations.backup_before_monitor_upgrade(self.directory)
        self.assertEqual(list((self.directory/'backups').glob('before-staff-scope-monitor-v2-*')),[])
        self.assertEqual(self.fingerprint(),before)
        for name,content in previous.items():self.assertEqual(Path(name).read_bytes(),content)

    def test_corrupt_source_aborts_without_a_success_archive(self):
        (self.directory/'core/research.sqlite3').write_bytes(b'synthetic invalid sqlite')
        with self.assertRaises(sqlite3.DatabaseError):backup_local.create_snapshot(self.directory)
        self.assertEqual(list((self.directory/'backups').glob('care-demo-*.zip')),[])


if __name__=='__main__':
    unittest.main()
