"""Offline database backup for the OS data-directory custodian, outside portal roles."""
from contextlib import closing
from pathlib import Path
import argparse
import json
import os
import secrets
import sqlite3
import tempfile
import zipfile
from care_store import stamp


def create_snapshot(directory):
    """Caller must hold the running service lock or the exclusive process lock."""
    directory = Path(directory)
    marker = directory / 'environment.json'
    if json.loads(marker.read_text(encoding='utf-8')) != {'mode':'synthetic_local_demo','schema':1}:
        raise ValueError('僅接受本機虛構體驗環境。')
    sources = [('facility.sqlite3',directory/'facility.sqlite3'),('core.sqlite3',directory/'core/research.sqlite3')]
    if not all(source.is_file() for _,source in sources):
        raise ValueError('既有資料庫不完整；不建立或重灌資料。')
    destination = directory / 'backups'
    destination.mkdir(exist_ok=True)
    path = destination / ('care-demo-'+stamp().replace(':','').replace('+','_')+'-'+secrets.token_hex(4)+'.zip')
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        copies = []
        for name,source in sources:
            target = Path(temporary)/name
            with closing(sqlite3.connect(source)) as src,closing(sqlite3.connect(target)) as dst:
                src.backup(dst)
            copies.append((name,target))
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,target in copies:
                archive.write(target,name)
            archive.write(marker,'environment.json')
            archive.write(directory/'core/integration-environment.json','core-environment.json')
            archive.writestr('manifest.json',json.dumps({'mode':'synthetic_local_demo','created_at':stamp(),'method':'offline_local_maintenance'}))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    args = parser.parse_args()
    if not (args.data_dir/'facility.sqlite3').is_file():
        raise SystemExit('找不到既有體驗資料庫。')
    with (args.data_dir/'process.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0');lock.flush()
        lock.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            raise SystemExit('資料目錄使用中，請先停止原服務。') from None
        print(create_snapshot(args.data_dir))


if __name__=='__main__':
    main()
