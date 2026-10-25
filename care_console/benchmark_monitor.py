"""Reproducible, offline synthetic benchmark. Run each dataset/stage in a fresh process."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import statistics
import sys
import time
import tracemalloc
from unittest.mock import patch


def memory():
    if os.name != 'nt':
        import resource
        return {'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    class Counters(ctypes.Structure):
        _fields_=[('cb',ctypes.c_ulong),('faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in
            ['peak_rss','rss','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private']]
    counters=Counters();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=ctypes.c_void_p
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_ulong]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {'process_peak_rss_bytes':counters.peak_rss,'process_rss_bytes':counters.rss,'private_bytes':counters.private}


def seed(app,count):
    workflow=app.extensions['care_workflow']
    now='2026-10-24T00:00:00+00:00'
    with workflow.transaction() as db:
        db.execute('BEGIN IMMEDIATE')
        password_hash=db.execute("SELECT password_hash FROM care.users WHERE id='family'").fetchone()[0]
        for group in range((count+4)//5):
            rid=f'R{group%6+1:03}';uid=f'bench-contact-{group:05}';cid=f'bench-thread-{group:05}'
            db.execute('INSERT INTO care.users VALUES(?,?,?,?,?)',(uid,uid,'虛構聯絡人 '+str(group),'family',password_hash))
            db.execute('INSERT INTO care.contact_conversations VALUES(?,?,?,?)',(cid,rid,uid,now))
            db.execute('INSERT INTO care.access VALUES(?,?)',(uid,rid))
            db.execute('INSERT INTO care.line_links VALUES(?,?,?,?)',(uid,'demo-'+uid,'admin',now))
            for j in range(4):
                db.execute('INSERT INTO messages(conversation_id,actor,text,source,delivery,created_at) VALUES(?,?,?,?,?,?)',
                           (cid,'user','完全虛構效能測試訊息','simulation','simulated',now))
            message=db.execute('SELECT last_insert_rowid()').fetchone()[0]
            for offset in range(min(5,count-group*5)):
                status='closed' if offset<4 else ('claimed' if group%2==0 else 'pending')
                owner=None if status=='pending' else 'nurse'
                case=db.execute('''INSERT INTO cases(conversation_id,status,trigger_risk,origin,created_at,
                    claimed_at,closed_at,operator,close_note,operator_id) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                    (cid,status,'中','user_request',now,now if owner else None,now if status=='closed' else None,
                     '虛構護理師' if owner else None,'虛構完成' if status=='closed' else None,owner)).lastrowid
                db.execute('INSERT INTO care.case_notes VALUES(?,?,?,?,?,?,?,?)',
                    (case,rid,'虛構處理內容'*32,'虛構下一步'*16,'虛構待確認',1,'nurse',now))
                for revision in range(3):
                    db.execute('INSERT INTO care.case_activity(case_id,actor,action,payload,created_at) VALUES(?,?,?,?,?)',
                        (case,'nurse','case_progress_saved',json.dumps({'revision':revision+1,'summary':'虛構內容'*16}),now))
                if status=='claimed' and group%4==0:
                    db.execute('INSERT INTO care.handoff_requests(case_id,resident_id,from_user,to_user,summary,next_action,waiting_for,message_id,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (case,rid,'nurse','nurse2','虛構交班','虛構下一步','',message-(1 if group%8 else 0),'pending',now))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage',choices=['before','after'],required=True)
    parser.add_argument('--prepare',type=int,choices=[100,1000,10000])
    args=parser.parse_args()
    sys.path.insert(0,str(args.source.resolve()))
    from app import create_app
    from integration import OfflineProvider
    from werkzeug.datastructures import MultiDict
    with patch.object(socket,'create_connection',side_effect=AssertionError('External network forbidden')):
        start=time.perf_counter()
        app=create_app(args.data_dir,provider=OfflineProvider())
        startup=time.perf_counter()-start
        if args.prepare:
            seed(app,args.prepare)
        monitor=app.extensions['care_monitor'];workflow=app.extensions['care_workflow']
        user=app.extensions['care_store'].user('head_nurse')
        query,values=monitor.query(user,monitor.parameters(MultiDict({'status':'all','limit':'10'})))
        first=monitor.list(user,MultiDict({'status':'all','limit':'10'}))
        cursor=first['next_cursor'];case_id=first['cases'][0]['id']
        with workflow.transaction() as db:
            count=db.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
            distribution=[dict(r) for r in db.execute('SELECT status,COUNT(*) AS count FROM cases GROUP BY status')]
            plans={name:[dict(r) for r in db.execute('EXPLAIN QUERY PLAN '+sql,params)] for name,sql,params in [
                ('scoped_rows',query,values),
                ('keyset_page','SELECT * FROM ('+query+') WHERE id<? ORDER BY id DESC LIMIT 11',values+[case_id]),
                ('timeline','SELECT * FROM care.case_activity WHERE case_id=? AND id<? ORDER BY id DESC LIMIT 21',[case_id,2**60])
            ]}
        def statistics_only():
            with workflow.transaction() as db:
                monitor.scope(db,user)
                if hasattr(monitor,'statistics'):
                    return monitor.statistics(db,query,values)
                # Exact pre-change statistics inputs and DTO conversion, with no pagination work.
                items=[monitor.item(dict(r)) for r in db.execute(query,values)]
                return {'total_cases':len(items),'pending_cases':sum(i['status']=='pending' for i in items),
                        'claimed_cases':sum(i['status']=='claimed' for i in items),'closed_cases':sum(i['status']=='closed' for i in items),
                        'pending_handoffs':sum(bool(i['handoff'] and i['handoff']['valid']) for i in items),
                        'stale_handoffs':sum(bool(i['handoff'] and not i['handoff']['valid']) for i in items)}
        operations={
            'list_with_statistics':lambda:monitor.list(user,MultiDict({'status':'all','limit':'10'})),
            'statistics_only':statistics_only,
            'next_page_with_statistics':lambda:monitor.list(user,MultiDict({'status':'all','limit':'10','cursor':cursor})),
            'single_case_timeline':lambda:monitor.timeline(user,case_id,MultiDict({'limit':'2'})),
        }
        results={}
        for name,operation in operations.items():
            durations=[]
            for sample in range(3):
                start=time.perf_counter();result=operation();durations.append((time.perf_counter()-start)*1000)
            tracemalloc.start();operation();current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            results[name]={'samples_ms':durations,'median_ms':statistics.median(durations),
                           'python_peak_bytes_separate_run':peak,'python_retained_bytes_separate_run':current}
            print(args.stage,count,name,round(results[name]['median_ms'],3),'ms',flush=True)
        invariant={'ids':[c['id'] for c in first['cases']],'stats':first['stats'],'owners':first['owners'],
                   'scope':first['scope_resident_ids'],'page2':[c['id'] for c in operations['next_page_with_statistics']()['cases']],
                   'timeline':operations['single_case_timeline']()['events']}
        report={'stage':args.stage,'case_count':count,'distribution':distribution,'authorized_residents':['R001','R002'],
                'authorized_cases':first['stats']['total_cases'],'dataset':'five cases per contact thread, six residents in rotation; 80% closed, 10% claimed, 10% pending; 3 events/case; 4 messages/thread; half pending handoffs intentionally stale',
                'environment':{'python':sys.version,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'processor':platform.processor(),'cpu_count':os.cpu_count()},
                'startup_seconds_excluded_from_timings':startup,'results':results,'query_plans':plans,'memory':memory(),
                'memory_note':'tracemalloc measures Python allocations in a separate fourth run; process peak RSS includes startup and all operations, not a per-operation increment. Timings use three warm-cache sequential samples without tracemalloc.',
                'invariant_sha256':hashlib.sha256(json.dumps(invariant,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                'network_calls':0,'real_line_sends':0}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        app.extensions['care_service'].stop_worker()


if __name__=='__main__':
    main()
