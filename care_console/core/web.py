import json
import secrets
import uuid
import re
from urllib.parse import urlsplit
from flask import Flask, abort, jsonify, request, session, render_template, Response
from service import WELCOME, DeliveryError, signature_valid, now
from generation import ModelError


def field(data, name, limit=4500):
    if not isinstance(data, dict):
        raise ValueError('請提供有效的資料物件。')
    value = data.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.encode('utf-16-le')) // 2 > limit:
        raise ValueError(f'{name} 不可空白，且不得超過 {limit} 字元。')
    return value.strip()


def create_admin(service):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=service.settings.snapshot()['session_secret'], MAX_CONTENT_LENGTH=65536,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_NAME='hitl_v06_session')

    @app.before_request
    def protect():
        if request.remote_addr not in {'127.0.0.1', '::1'} or urlsplit(request.url).hostname not in {'127.0.0.1', 'localhost', '::1'}:
            abort(403)
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/'):
                abort(403)
            if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.get('csrf', 'missing')):
                abort(403)
            if getattr(service,'integration_mode',None)=='offline' and request.path in {'/api/settings','/api/ai-settings','/api/ai-check'}:
                raise ValueError('本版固定使用離線替代服務，不接受真實金鑰或外部串接設定。')

    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        return response

    @app.errorhandler(ValueError)
    def invalid(exc):
        return jsonify(error=str(exc)), 400

    @app.get('/')
    def home():
        return render_template('index.html')

    @app.get('/api/status')
    def status():
        session.setdefault('csrf', secrets.token_hex(32))
        return jsonify(service.overview() | {'csrf': session['csrf']})

    @app.get('/api/conversations/<participant>')
    def detail(participant):
        return jsonify(service.detail(participant))

    @app.post('/api/settings')
    def settings():
        data = request.get_json()
        if not isinstance(data, dict) or not isinstance(data.get('line_enabled'), bool):
            raise ValueError('請提供啟用狀態。')
        changes = {'line_enabled': data['line_enabled']}
        for name in ('channel_secret', 'access_token'):
            if data.get(name):
                changes[name] = field(data, name, 4096)
        merged = service.settings.snapshot() | changes
        if merged['line_enabled'] and not (merged['channel_secret'] and merged['access_token']):
            raise ValueError('請先填入兩項 LINE 設定。')
        service.settings.save(changes)
        return jsonify(service.settings.public())

    @app.post('/api/demo')
    def demo():
        data = request.get_json()
        text = field(data, 'text')
        participant = data.get('participant') or 'demo-' + uuid.uuid4().hex
        if not isinstance(participant, str) or not participant.startswith('demo-') or len(participant) > 80:
            raise ValueError('本機測試對話識別碼錯誤。')
        if service.enrolled(participant) and service.detail(participant)['conversation']['transport'] != 'simulation':
            raise ValueError('僅能使用本機測試對話。')
        service.enroll(participant, 'simulation')
        return jsonify(service.receive(participant, text, 'demo-event-' + uuid.uuid4().hex) | {'participant': participant})

    @app.post('/api/import-line')
    def import_line():
        if not hasattr(service, 'import_legacy_line'):
            raise ValueError('此版本不提供舊版設定帶入。')
        return jsonify(service.import_legacy_line())

    @app.post('/api/ai-settings')
    def ai_settings():
        data = request.get_json()
        if not isinstance(data, dict) or not isinstance(data.get('ai_enabled'), bool):
            raise ValueError('請提供模型啟用狀態。')
        model = field(data, 'model', 120)
        if not re.fullmatch(r'[a-zA-Z0-9._:-]+', model):
            raise ValueError('模型名稱格式不符。')
        limit = data.get('daily_call_limit')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('每日呼叫上限請填 1 至 200 次的整數。')
        changes = {'ai_enabled': data['ai_enabled'], 'model': model, 'daily_call_limit': limit}
        if data.get('openai_key'):
            key = field(data, 'openai_key', 4096)
            if any(c.isspace() for c in key) or not key.isascii():
                raise ValueError('API 金鑰不可含空白或非英文數字符號。')
            changes['openai_key'] = key
        if changes['ai_enabled'] and not (changes.get('openai_key') or service.settings.snapshot()['openai_key']):
            raise ValueError('請先儲存 OpenAI API 金鑰。')
        service.save_ai_settings(changes)
        return jsonify(service.settings.public())

    @app.post('/api/ai-check')
    def ai_check():
        try:
            result = service.provider.check_access(service.settings.snapshot())
        except ModelError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(result)

    @app.post('/api/generations/<int:job_id>/<action>')
    def review(job_id, action):
        if action not in {'approve', 'reject'}:
            abort(404)
        data = request.get_json()
        note = field(data, 'note', 1000)
        text = field(data, 'text') if action == 'approve' else ''
        return jsonify(service.review_draft(job_id, text, note, reject=action == 'reject'))

    @app.post('/api/cases/<int:case_id>/<action>')
    def case_action(case_id, action):
        data = request.get_json()
        if action == 'claim':
            service.claim(case_id, field(data, 'operator', 80))
        elif action == 'reply':
            return jsonify(service.human_reply(case_id, field(data, 'text')))
        elif action == 'resolve':
            service.resolve(case_id, field(data, 'note', 1000))
        elif action == 'followup' and hasattr(service,'record_service_followup'):
            service.record_service_followup(case_id,field(data,'status',30),field(data,'recipient',150),field(data,'note',1000))
        else:
            abort(404)
        return jsonify(ok=True)

    @app.get('/api/export')
    def export():
        with service.db() as db:
            data = {name: [dict(row) for row in db.execute('SELECT * FROM ' + name)]
                    for name in ('conversations', 'events', 'cases', 'messages', 'audit')}
            if hasattr(service, 'knowledge'):
                data.update({name: [dict(row) for row in db.execute('SELECT * FROM ' + name)] for name in ('generations', 'model_calls')})
        data['version'] = service.overview()['version']
        if hasattr(service,'classifier_metadata'):
            with service.db() as db:
                data['classification_records']=[dict(row) for row in db.execute('SELECT * FROM classification_records')]
                data['service_decisions']=[dict(row) for row in db.execute('SELECT * FROM service_decisions')]
                if hasattr(service,'record_service_followup'):
                    for table in ('service_requests','service_followups'):
                        data[table]=[dict(row) for row in db.execute('SELECT * FROM '+table)]
            if hasattr(service,'record_webhook_receipt'):
                with service.db() as db:
                    data['webhook_receipts']=[dict(row) for row in db.execute('SELECT * FROM webhook_receipts')]
                    data['recognition_records']=[dict(row) for row in db.execute('SELECT * FROM recognition_records')]
                    for table in ('followup_prompts','context_decisions','dialogue_turns','dialogue_decisions','generation_contexts'):
                        data[table]=[dict(row) for row in db.execute('SELECT * FROM '+table)]
            data['classifier']=service.classifier_metadata
            data['integration_mode']=service.integration_mode
        return Response(json.dumps(data, ensure_ascii=False, indent=2), mimetype='application/json',
                        headers={'Content-Disposition': 'attachment; filename="hitl-prototype-records.json"'})
    return app


def create_webhook(service):
    app = Flask('line_webhook', static_folder=None)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

    @app.get('/health')
    def health():
        return jsonify(ok=True)

    @app.post('/webhook')
    def webhook():
        config = service.settings.snapshot()
        if not config['line_enabled']:
            return jsonify(error='LINE disabled'), 503
        raw = request.get_data()
        if not signature_valid(raw, request.headers.get('X-Line-Signature'), config['channel_secret']):
            abort(403)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            abort(400)
        if not isinstance(data, dict) or not isinstance(data.get('events'), list):
            abort(400)
        # Validate complete batch before side effects.
        for event in data['events']:
            if not isinstance(event, dict) or not isinstance(event.get('source', {}), dict):
                abort(400)
            if event.get('type') == 'message':
                message = event.get('message')
                if not isinstance(message, dict):
                    abort(400)
                if message.get('type') == 'text' and (not isinstance(message.get('text'), str) or len(message['text']) > 20000):
                    abort(400)
            if not isinstance(event.get('webhookEventId'), str) or not event['webhookEventId']:
                abort(400)
        for event in data['events']:
            source = event.get('source', {})
            participant = source.get('userId')
            if source.get('type') != 'user' or not isinstance(participant, str) or not participant:
                continue
            if event.get('type') not in {'follow', 'message'}:
                continue
            message = event.get('message', {})
            text = message.get('text', '') if message.get('type') == 'text' else ''
            eid = event['webhookEventId']
            token = event.get('replyToken')
            with service.lock:
                with service.db() as db:
                    if db.execute('SELECT 1 FROM controls WHERE id=?', (eid,)).fetchone():
                        continue
                if event['type'] == 'message' and text and service.enrolled(participant):
                    service.receive(participant, text, eid, channel='line', reply_token=token)
                    continue
                with service.db() as db:
                    db.execute('INSERT INTO controls VALUES(?,?)', (eid, now()))
                if text.strip() == '加入 ' + config['join_code']:
                    service.enroll(participant, 'line')
                    answer = '已加入研究展示。請只使用虛構測試訊息；可傳送「轉人工」測試接管。本帳號沒有醫療人員值班。'
                elif service.enrolled(participant) and event['type'] == 'message':
                    answer = '研究原型目前只處理文字訊息；圖片、語音與貼圖尚未進行風險分級。'
                else:
                    answer = WELCOME
                if service.enrolled(participant):
                    service.deliver(participant, answer, 'auto', 'system_notice', event_id=eid, reply_token=token)
                elif token:
                    try:
                        service.transport.send('reply', participant, answer, reply_token=token)
                    except DeliveryError:
                        # No message content, join code, credentials, or user ID in public logs.
                        app.logger.warning('Unenrolled welcome delivery failed or uncertain.')
        if hasattr(service, 'record_webhook_receipt'):
            service.record_webhook_receipt(len(data['events']))
        return jsonify(ok=True)
    return app
