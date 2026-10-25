"""Offline database backup for the OS data-directory custodian, outside portal roles."""
from pathlib import Path
import argparse
import json
import os
import zipfile
from care_store import stamp
from snapshots import staging, copy_sources, manifest, failed


def create_snapshot(directory):
    """Caller must hold the running service lock or the exclusive process lock."""
    directory = Path(directory)
    marker = directory / 'environment.json'
    if json.loads(marker.read_text(encoding='utf-8')) != {'mode':'synthetic_local_demo','schema':1}:
        raise ValueError('僅接受本機虛構體驗環境。')
    sources = [('facility.sqlite3',directory/'facility.sqlite3'),('core.sqlite3',directory/'core/research.sqlite3')]
    if not all(source.is_file() for _,source in sources):
        raise ValueError('既有資料庫不完整；不建立或重灌資料。')
    temporary,target=staging(directory,'care-demo-'+stamp().replace(':','').replace('+','_'))
    path=target.with_suffix('.zip')
    try:
        files=copy_sources(directory,temporary,core_marker_name='core-environment.json',require_core=True)
        metadata=manifest('offline_local_maintenance',files)
        metadata['method']='offline_local_maintenance'
        archive_path=temporary/'snapshot.partial'
        with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_DEFLATED) as archive:
            for name in files:
                archive.write(temporary/name,name)
            archive.writestr('manifest.json',json.dumps(metadata,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError('備份壓縮檔驗證失敗。')
        archive_path.rename(path)
    except Exception as error:
        failed(temporary,error)
        raise
    # Only this call's transient copies are removed after a valid archive is published.
    # If cleanup fails, preserve the leftovers and still return the completed archive.
    try:
        for name in files:
            (temporary/name).unlink()
        temporary.rmdir()
    except OSError:
        pass
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
