from pathlib import Path
import argparse
import os
import sys
from waitress import create_server
from app import create_app

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=9465)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).parent / 'runtime')
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    lock = (args.data_dir / 'process.lock').open('a+b')
    try:
        lock.seek(0)
        if lock.read(1) == b'':
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('This care demo data directory is already in use.')
    app = create_app(args.data_dir)
    service = app.extensions['care_service']
    server = create_server(app, host='127.0.0.1', port=args.port, threads=4)
    service.start_worker()
    print(f'Care console: http://127.0.0.1:{args.port}/', flush=True)
    print('Synthetic records; local-only; real LINE is not connected.', flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop_worker()
        server.close()
        lock.close()

if __name__ == '__main__':
    main()
