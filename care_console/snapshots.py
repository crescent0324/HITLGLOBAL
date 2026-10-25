"""Sensitive local snapshots: validate copies, then atomically publish a completed name."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
from care_store import stamp


def manifest(purpose, files):
    return {'format_version':2,'status':'complete','purpose':purpose,'created_at':stamp(),
            'mode':'synthetic_local_demo','credentials_included':True,
            'plaintext_passwords_included':False,'password_hashes_included':True,
            'session_keys_included':False,'api_configuration_included':False,
            'business_data_included':True,'files':files,
            'sensitivity_note':'Password hashes and business records are sensitive. Plaintext flag describes application password storage, not an inspection of arbitrary free text.'}


def staging(directory, prefix):
    root=Path(directory)/'backups';root.mkdir(parents=True,exist_ok=True)
    name=prefix+'-'+secrets.token_hex(8)
    temporary=root/('.incomplete-'+name)
    temporary.mkdir()
    return temporary,root/name


def failed(temporary, error):
    # Preserve newly created partial files for the custodian; never remove old snapshots.
    try:
        (temporary/'manifest.json').write_text(json.dumps({'status':'incomplete','format_version':2}),encoding='utf-8')
        (temporary/'failure.json').write_text(json.dumps({'status':'incomplete','error_type':type(error).__name__,
            'created_at':stamp(),'restore_allowed':False}),encoding='utf-8')
    except OSError:
        pass  # The .incomplete- name remains authoritative even when the disk cannot accept diagnostics.


def copy_sources(directory, temporary, core_marker_name='integration-environment.json', require_core=False):
    directory=Path(directory)
    sources=[('facility.sqlite3',directory/'facility.sqlite3'),('core.sqlite3',directory/'core/research.sqlite3')]
    if not sources[0][1].is_file() or (require_core and not sources[1][1].is_file()):
        raise ValueError('既有資料庫不完整；不建立或重灌資料。')
    for name,source in sources:
        if not source.is_file():
            continue
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(temporary/name)) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise sqlite3.DatabaseError('Snapshot integrity check failed')
    for source,name in [(directory/'environment.json','environment.json'),
                        (directory/'core/integration-environment.json',core_marker_name)]:
        if source.is_file():
            (temporary/name).write_bytes(source.read_bytes())
        elif require_core:
            raise ValueError('缺少體驗環境識別檔；備份未完成。')
    return {p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(temporary.iterdir()) if p.is_file()}


def upgrade_snapshot(directory, prefix, purpose):
    temporary,target=staging(directory,prefix)
    try:
        files=copy_sources(directory,temporary)
        (temporary/'manifest.json').write_text(json.dumps(manifest(purpose,files),ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.rename(target)
        return target
    except Exception as error:
        failed(temporary,error)
        raise
