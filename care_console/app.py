"""Local, synthetic-data nursing-home experience environment."""
from datetime import timedelta
from pathlib import Path
from functools import wraps
import io
import json
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, session, render_template, Response, g
from werkzeug.exceptions import HTTPException

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / 'core'))
from integration import OfflineLineTransport
from care_store import CareStore, ROLES, STAFF, CLINICAL_STAFF, ASSESSORS, CSV_FIELDS, stamp
from workflow import StaffWorkflow
from migrations import (backup_before_owner_migration, backup_before_monitor_upgrade, migrate_monitor_access,
                        backup_before_monitor_indexes, migrate_monitor_indexes)
from case_monitor import CaseMonitor
from conversations import ConversationDirectory, ScopedLiveService, internal_conversation, backup_before_thread_schema
from werkzeug.exceptions import Conflict

def conversation(rid):
    return internal_conversation(rid)

def create_app(data_dir=None, provider=None):
    directory = Path(data_dir or BASE / 'runtime')
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / 'environment.json'
    expected = {'mode': 'synthetic_local_demo', 'schema': 1}
    if marker.exists():
        if json.loads(marker.read_text(encoding='utf-8')) != expected:
            raise ValueError('資料目錄不屬於此體驗環境。')
    elif (directory / 'facility.sqlite3').exists() or (directory / 'core/research.sqlite3').exists():
        raise ValueError('資料目錄已有紀錄，請使用本體驗版目錄或先核對備份。')
    else:
        marker.write_text(json.dumps(expected), encoding='utf-8')
    key_path = directory / 'session.key'
    if not key_path.exists():
        key_path.write_text(secrets.token_hex(32), encoding='utf-8')
    backup_before_thread_schema(directory)
    backup_before_owner_migration(directory)
    backup_before_monitor_upgrade(directory)
    backup_before_monitor_indexes(directory)
    store = CareStore(directory)
    conversations = ConversationDirectory(store)
    service = ScopedLiveService(directory / 'core', conversations, transport=OfflineLineTransport(), provider=provider)
    workflow = StaffWorkflow(store, service)
    migrate_monitor_access(workflow)
    migrate_monitor_indexes(workflow)
    monitor = CaseMonitor(workflow, key_path.read_text(encoding='utf-8'))
    for resident in store.residents(store.user('nurse')):
        for thread in conversations.list(store.user('nurse'), resident['id']):
            service.enroll(thread['id'], 'simulation')
    app = Flask(__name__)
    app.config.update(SECRET_KEY=key_path.read_text(encoding='utf-8'), MAX_CONTENT_LENGTH=2 * 1024 * 1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_NAME='care_console_session', PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
                      SESSION_REFRESH_EACH_REQUEST=False)
    app.extensions.update(care_service=service, care_store=store, care_workflow=workflow,
                          care_conversations=conversations, care_monitor=monitor)
    failures = {}
    failure_lock = threading.Lock()

    with store.db() as db:
        # Server-side record of each web login, so logout ends the session even if a copy
        # of the signed cookie is kept.
        db.execute('''CREATE TABLE IF NOT EXISTS web_sessions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,ended_at TEXT)''')
    session_lifetime = app.config['PERMANENT_SESSION_LIFETIME']

    def session_valid():
        sid, uid = session.get('sid'), session.get('uid')
        if not isinstance(sid, str) or not uid:
            return False
        with store.db() as db:
            row = db.execute('SELECT user_id,created_at,ended_at FROM web_sessions WHERE id=?', (sid,)).fetchone()
        if not row or row['user_id'] != uid or row['ended_at']:
            return False
        return datetime.now(timezone.utc) - datetime.fromisoformat(row['created_at']) <= session_lifetime

    def user():
        if 'care_user' not in g:
            account = store.user(session.get('uid')) if session_valid() else None
            g.care_user = account if account and account['role'] in STAFF else None
        return g.care_user

    def json_body():
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ValueError('請提供有效的資料。')
        return data

    def roles(*allowed):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                current = user()
                if not current:
                    return jsonify(error='請先登入。'), 401
                if allowed and current['role'] not in allowed:
                    raise PermissionError('此操作需要相應的工作人員權限。')
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    @app.before_request
    def protect():
        # The demo password and synthetic records are intentionally local-only.
        if request.host.split(':')[0] not in {'127.0.0.1', 'localhost'} or request.remote_addr not in {'127.0.0.1', '::1'}:
            return jsonify(error='此體驗環境僅供本機使用，未開放遠端部署。'), 403
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/'):
                return jsonify(error='請求來源不符。'), 403
            token = session.get('csrf')
            if not token or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), token):
                return jsonify(error='請重新整理後再操作。'), 403
        if request.path.startswith('/api/') and request.path not in {'/api/session', '/api/login'} and not user():
            return jsonify(error='請先登入。'), 401

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
             'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @app.errorhandler(PermissionError)
    def denied(exc):
        return jsonify(error=str(exc)), 403

    @app.errorhandler(Exception)
    def unexpected(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        app.logger.exception('Care console operation failed')
        return jsonify(error='操作未完成，請查看伺服器紀錄。'), 500

    @app.get('/')
    def home():
        return render_template('index.html')

    @app.get('/health')
    def health():
        return jsonify(ok=True, environment='synthetic_local_demo')

    @app.get('/api/session')
    def current_session():
        if session.get('uid') and not user():
            session.clear()
        session.setdefault('csrf', secrets.token_hex(32))
        return jsonify(user=user(), csrf=session['csrf'], roles={k:v for k,v in ROLES.items() if k in STAFF}, environment='synthetic_local_demo')

    @app.post('/api/login')
    def login():
        data = json_body()
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(username) > 80 or len(password) > 200:
            raise ValueError('登入資料格式不符。')
        key = request.remote_addr
        with failure_lock:
            attempts = [t for t in failures.get(key, []) if time.monotonic() - t < 60]
            failures[key] = attempts
            if len(attempts) >= 8:
                return jsonify(error='登入失敗次數過多，請稍候一分鐘。'), 429
        account = store.authenticate(username.strip(), password)
        if not account:
            with failure_lock:
                failures[key].append(time.monotonic())
            return jsonify(error='帳號或密碼不符。'), 401
        if account['role'] not in STAFF:
            session.pop('uid', None)
            return jsonify(error='此協作台僅供院內工作人員使用；家屬與住民請使用 LINE。'), 403
        with failure_lock:
            failures.pop(key, None)
        session.clear()
        sid = secrets.token_hex(32)
        with store.db() as db:
            db.execute('INSERT INTO web_sessions(id,user_id,created_at) VALUES(?,?,?)', (sid, account['id'], stamp()))
        session.update(uid=account['id'], sid=sid, csrf=secrets.token_hex(32))
        session.permanent = True
        g.pop('care_user', None)
        return jsonify(user=account, csrf=session['csrf'])

    @app.post('/api/logout')
    def logout():
        if isinstance(session.get('sid'), str):
            with store.db() as db:
                db.execute('UPDATE web_sessions SET ended_at=? WHERE id=? AND ended_at IS NULL', (stamp(), session['sid']))
        session.clear()
        g.pop('care_user', None)
        return jsonify(ok=True)

    @app.get('/api/board')
    @roles(*CLINICAL_STAFF)
    def board():
        current = user()
        cards = []
        queue = []
        for resident in store.residents(current):
            observations = store.observations(current, resident['id'], 1)
            resident_queue = []
            if current['role'] in ASSESSORS:
                with service.lock:
                    for thread in conversations.list(current, resident['id']):
                        service.enroll(thread['id'], 'simulation')
                        source = service.detail(thread['id'])
                        if source['case']:
                            item = workflow.queue_item(current, resident, source)
                            item.update(conversation_id=thread['id'], contact_label=thread['label'],
                                        contact_active=thread['active'], conversation_kind=thread['kind'])
                            resident_queue.append(item)
            resident_queue = workflow.sort_queue(resident_queue)
            queue.extend(resident_queue)
            first = resident_queue[0] if resident_queue else None
            card = resident | {'latest': observations[0] if observations else None,
                               'assessment': store.latest_assessment(current, resident['id'])}
            if current['role'] in ASSESSORS:
                card.update({'state': first['state'] if first else 'automatic',
                         'pending_case': bool(resident_queue), 'pending_count': len(resident_queue),
                         'case_operator': first['operator'] if first else None,
                         'risk': first['message_risk'] if first else None})
            cards.append(card)
        return jsonify(cards=cards, work_queue=workflow.sort_queue(queue), synchronized_at=stamp(), mode='模擬院內資料／本機體驗',
                       ai_enabled=service.settings.public()['ai_enabled'],
                       line_mode='本機流程模擬，未連接真實 LINE',
                       user=current, line_link=store.demo_link(current))

    @app.get('/api/residents/<rid>')
    @roles(*CLINICAL_STAFF)
    def detail(rid):
        current = user()
        store.require(current, rid)
        resident = next(r for r in store.residents(current) if r['id'] == rid)
        if current['role'] not in ASSESSORS:
            if 'conversation_id' in request.args:
                raise PermissionError('照服員無權存取服務對話；請以照護紀錄回報觀察。')
            return jsonify(resident=resident, observations=store.observations(current, rid), role=current['role'])
        with service.lock:
            threads = conversations.list(current, rid)
            selected = conversations.describe(current, rid, request.args.get('conversation_id'))
            service.enroll(selected['id'], 'simulation')
            source = service.detail(selected['id'])
            seen_message_id = None
            if source['case']:
                with service.db() as db:
                    seen_message_id = workflow.latest_message(db, source['case'])
        authors = store.authors(current, rid)
        messages = [dict(m) | {'author': authors.get(m['event_id'], {}).get('display_name'),
                              'input_channel': authors.get(m['event_id'], {}).get('channel')}
                    for m in source['messages']]
        case = source['case']
        case_view = {k: case[k] for k in ('id', 'status', 'trigger_risk', 'origin', 'operator', 'created_at')} if case else None
        if case_view:
            case_view.update(workflow.identity(case))
            # The client echoes this back so replies and closures are based on the latest messages.
            case_view['seen_message_id'] = seen_message_id
        drafts = []
        if current['role'] in ASSESSORS:
            drafts = [{k: j.get(k) for k in ('id', 'status', 'mode', 'response_text', 'error', 'created_at')}
                      for j in source['generations']]
        return jsonify(resident=resident, observations=store.observations(current, rid),
                       conversations=threads, selected_conversation=selected,
                       messages=messages, case=case_view, state=source['state'], drafts=drafts,
                       workflow=workflow.view(current,rid,source),
                       line_contacts=store.line_contacts(current,rid) if current['role'] in ASSESSORS else [],
                       audit=store.audit(current, rid), role=current['role'])

    @app.post('/api/residents/<rid>/message')
    @roles(*ASSESSORS)
    def message(rid):
        current = user()
        store.require(current, rid)
        data = json_body()
        text = data.get('text')
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise ValueError('訊息須為 1 至 2000 字。')
        channel = data.get('channel', 'web')
        if channel not in {'web', 'demo_line'}:
            raise ValueError('回報通道無效。')
        actor = current
        if channel == 'demo_line':
            if current['role'] not in ASSESSORS:
                raise PermissionError('LINE 訊息模擬僅限管理者或護理師。')
            actor_id = data.get('line_actor')
            if not isinstance(actor_id, str):
                raise ValueError('請指定已配對的家屬或住民模擬 LINE 身分。')
            actor = store.user(actor_id)
            if not actor or actor['role'] not in {'family', 'resident'} or not store.demo_link(actor):
                raise ValueError('請指定已配對的家屬或住民模擬 LINE 身分。')
            store.require(actor, rid)
        event = 'care-' + secrets.token_hex(16)
        with service.lock:
            if channel == 'demo_line':
                thread_id = conversations.contact_thread(current, rid, actor['id'])
            else:
                thread_id = conversation(rid)
            if 'conversation_id' in data and data['conversation_id'] != thread_id:
                raise Conflict('測試訊息來源與目前對話不符，請重新選擇對話。')
            store.record_author(actor, rid, event, channel)
            service.enroll(thread_id, 'simulation')
            result = service.receive(thread_id, text.strip(), event)
            active_case = service.detail(thread_id)['case']
            if active_case:
                with workflow.transaction() as db:
                    if not db.execute('SELECT 1 FROM care.case_activity WHERE case_id=?', (active_case['id'],)).fetchone():
                        workflow.activity(db,active_case['id'],None,'case_opened',{'origin':active_case['origin']})
                    workflow.activity(db,active_case['id'],actor,'message_received',{'event_id':event,'simulated_by':current['id']})
            with store.db() as db:
                store.log(db, current, 'line_message_simulated' if channel=='demo_line' else 'message_submitted',
                          rid, 'channel=' + channel + '; input_identity=' + actor['id'] + '; conversation=' + thread_id)
        return jsonify(result=result, actual_line_sent=False, conversation_id=thread_id)

    @app.post('/api/residents/<rid>/observation')
    @roles(*CLINICAL_STAFF)
    def observation(rid):
        current, data = user(), json_body()
        if current['role'] not in ASSESSORS:
            # Caregiver reports get a server-generated id, so they cannot occupy an id that a
            # later facility import needs.
            data.pop('source_record_id', None)
        with service.lock:
            added = store.add_observation(current, rid, data)
        return jsonify(added=added)

    @app.post('/api/residents/<rid>/case/<action>')
    @roles(*ASSESSORS)
    def case_action(rid, action):
        current = user()
        store.require(current, rid)
        data = json_body()
        with service.lock:
            selected = conversations.describe(current, rid, data.get('conversation_id'))
            thread_id = selected['id']
            case = service.detail(thread_id)['case']
            if not case:
                raise ValueError('目前沒有待處理案件。')
            if type(data.get('case_id')) is not int or data['case_id'] != case['id']:
                raise Conflict('案件已變更，請更新紀錄後再操作。')
            if action in {'reply', 'approve'} and not selected['active']:
                raise PermissionError('聯絡人配對已撤銷，不能回覆或核准草稿。')
            if action in {'reply', 'resolve'}:
                # New messages (including a risk escalation) join the same open case, so the
                # case id alone cannot tell whether the staff member has seen them.
                with service.db() as db:
                    latest = workflow.latest_message(db, case)
                if type(data.get('seen_message_id')) is not int or data['seen_message_id'] != latest:
                    raise Conflict('此對話有新訊息尚未查看，請按「更新紀錄」確認最新內容後再操作。')
            if action == 'claim':
                workflow.claim(current, rid, case['id'], thread_id)
            elif action == 'accept_handoff':
                workflow.accept(current, rid, data.get('request_id'), thread_id)
            else:
                workflow.require_owner(current, case)
                if action == 'reply':
                    text = data.get('text')
                    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
                        raise ValueError('請填寫 1 至 2000 字的人工回覆。')
                    result = service.human_reply(case['id'], text.strip())
                    author_event = 'care-human-' + secrets.token_hex(16)
                    with service.db() as db:
                        db.execute('UPDATE messages SET event_id=? WHERE id=?', (author_event, result['message_id']))
                    store.record_author(current, rid, author_event, 'staff')
                elif action == 'resolve':
                    note = data.get('note')
                    if not isinstance(note, str) or not note.strip() or len(note) > 1000:
                        raise ValueError('請填寫 1 至 1000 字的處理結果。')
                    workflow.resolve(current, rid, note.strip(), thread_id)
                elif action == 'progress':
                    workflow.save_note(current, rid, data, thread_id)
                elif action == 'handoff':
                    workflow.propose(current, rid, data, thread_id)
                elif action == 'cancel_handoff':
                    workflow.cancel(current, rid, thread_id)
                elif action in {'approve', 'reject'}:
                    job_id = data.get('job_id')
                    jobs = service.detail(thread_id)['generations']
                    if type(job_id) is not int or not any(j['id'] == job_id for j in jobs):
                        raise PermissionError('草稿與目前聯絡人對話不符。')
                    note = data.get('note', '')
                    text = data.get('text', '')
                    if not isinstance(note, str) or not note.strip() or len(note) > 1000:
                        raise ValueError('請填寫審閱紀錄。')
                    if action == 'approve' and (not isinstance(text, str) or not text.strip() or len(text) > 2000):
                        raise ValueError('請填寫核准回覆。')
                    service.review_draft(job_id, text, note, reject=action == 'reject')
                else:
                    raise ValueError('案件操作無效。')
            if action in {'reply','approve','reject'}:
                workflow.record_activity(current,case['id'],'case_'+action,{'job_id':data.get('job_id')})
            with store.db() as db:
                store.log(db, current, 'case_' + action, rid,
                          'case=' + str(case['id']) + '; conversation=' + thread_id)
        return jsonify(ok=True)

    @app.post('/api/residents/<rid>/move')
    @roles(*ASSESSORS)
    def move(rid):
        with service.lock:
            store.move(user(), rid, json_body().get('bed_id'))
        return jsonify(ok=True)

    @app.get('/api/knowledge')
    @roles()
    def knowledge():
        return jsonify(sources=service.knowledge.data['sources'], institution_policy='尚未提供正式機構資料。')

    @app.get('/api/beds')
    @roles(*ASSESSORS)
    def beds():
        return jsonify(beds=store.beds(user()))

    @app.get('/api/template.csv')
    @roles(*ASSESSORS)
    def csv_template():
        text = ','.join(CSV_FIELDS) + '\r\n' + ','.join([
            'R001', 'IMPORT-DEMO-001', stamp(), '36.7', '76', '97', '128', '78', '尚未評估', '虛構院內匯入範例']) + '\r\n'
        return Response('\ufeff' + text, mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="care-demo-template.csv"'})

    @app.post('/api/import')
    @roles(*ASSESSORS)
    def import_data():
        data = json_body()
        if data.get('synthetic_confirmed') is not True or not isinstance(data.get('csv'), str):
            raise ValueError('請確認匯入內容均為虛構測試資料。')
        with service.lock:
            return jsonify(store.import_csv(user(), data['csv']))

    @app.get('/api/bindings')
    @roles('admin')
    def bindings():
        return jsonify(store.bindings(user()))

    @app.get('/api/case-monitor')
    @roles('head_nurse')
    def case_monitor():
        return jsonify(monitor.list(user(),request.args))

    @app.get('/api/case-monitor/<int:case_id>/timeline')
    @roles('head_nurse')
    def case_timeline(case_id):
        return jsonify(monitor.timeline(user(),case_id,request.args))

    @app.post('/api/bindings')
    @roles('admin')
    def binding():
        data = json_body()
        if type(data.get('allowed')) is not bool:
            raise ValueError('請提供授權狀態。')
        with service.lock:
            store.grant(user(), data.get('user_id'), data.get('resident_id'), data['allowed'])
            if not data['allowed']:
                workflow.release_revoked_owner(user(), data['user_id'], data['resident_id'])
                with store.db() as db:
                    threads = db.execute('SELECT id FROM contact_conversations WHERE resident_id=? AND contact_id=?',
                                         (data['resident_id'],data['user_id'])).fetchall()
                with service.db() as db:
                    for thread in threads:
                        service.cancel_jobs(db,thread['id'],'聯絡人配對已撤銷，既有生成工作失效。')
        return jsonify(ok=True)

    @app.post('/api/backup')
    @roles()
    def backup():
        raise PermissionError('完整資料庫含臨床內容，已停止網頁下載；請停止服務後使用本機 backup_local.py 維護工具。')

    return app
