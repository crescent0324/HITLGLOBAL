"""Operational generation is versioned separately from the frozen thesis classifier."""
import json
import re
import threading
from datetime import datetime, timezone, timedelta

from service import Service, now
from generation import Knowledge, OpenAIProvider, ModelError, PROMPT_VERSION, REPLY_FORMAT_VERSION, payload_for, validate_reply

SCOPE_VERSION = 'service-information-scope-0.2'
# This limits generation scope; it does NOT relabel the frozen risk prediction.
PERSONAL_HEALTH = re.compile(r'血壓|血糖|心跳|體溫|吃藥|服藥|用藥|停藥|調藥|劑量|症狀|不舒服|胸|痛|喘不|喘到|呼吸|暈|無力|沒有力|倒下|叫不|叫都|昏|流血|嘔吐|發燒|麻木|嘴歪|說話不|吞嚥|抽搐|受傷|跌倒|癱|中風|心臟病|癲癇|糖尿病|高血壓|低血壓|急救|治療|診斷')
MENU = '可以詢問長照服務申請方式、服務類別與喘息服務。目前的服務資料尚未涵蓋你的問題，沒有產生模型回覆。若需院內工作人員協助，請傳送「轉人工」。'
UNAVAILABLE = '模型回覆目前未啟用，尚未產生 AI 回答。可以傳送「轉人工」聯絡院內工作人員；本帳號不保證即時有人回覆。'
WAIT_REVIEW = '訊息已列入人工確認清單。系統不會自行解讀你的數值或症狀，也不提供診斷、調藥或治療決策。目前尚不代表已有人接手。'


class ResearchService(Service):
    def __init__(self, data_dir, transport=None, provider=None, engine=None, governance=None):
        super().__init__(data_dir, transport, engine, governance)
        self.provider = provider or OpenAIProvider()
        self.knowledge = Knowledge()
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.worker = None
        self.worker_problem = None
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                    conversation_id TEXT NOT NULL, risk TEXT NOT NULL, mode TEXT NOT NULL,
                    status TEXT NOT NULL, payload TEXT NOT NULL, sources TEXT NOT NULL,
                    model TEXT NOT NULL, config_revision INTEGER NOT NULL,
                    prompt_version TEXT NOT NULL, knowledge_version TEXT NOT NULL,
                    knowledge_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    report TEXT, response_text TEXT, error TEXT, operator TEXT, review_note TEXT, message_id INTEGER);
                CREATE TABLE IF NOT EXISTS model_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, generation_id INTEGER NOT NULL,
                    day TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')

    def cancel_jobs(self, db, participant, reason, only_auto=False):
        clause = " AND mode='GENERAL'" if only_auto else ''
        changed = db.execute("UPDATE generations SET status='cancelled',error=?,updated_at=? WHERE conversation_id=? AND status IN ('queued','running','draft')" + clause,
                             (reason, now(), participant)).rowcount
        if changed:
            self.log(db, participant, 'generation_cancelled', reason)

    def on_incoming(self, db, participant, event_id):
        self.cancel_jobs(db, participant, '有新訊息，舊草稿及未完成回覆不再適用。')

    def choose_reply(self, participant, text, event_id, result, plan, state, answer, source):
        if result.risk == '高' or state in {'human_active', 'awaiting_takeover'}:
            return answer, source, state
        if result.risk == '低' and state == 'automatic' and self.should_review_low(text, result):
            with self.db() as db:
                case = self._open_case(db, participant, result.risk, 'scope_review')
                self.log(db, participant, 'generation_scope_restricted', f'event={event_id}; policy={getattr(self,"scope_version",SCOPE_VERSION)}; frozen_risk={result.risk}')
            return '此訊息涉及健康狀況，超出本版自動長照服務問答範圍，已列入人工確認。規則分級不代表已確認健康狀況；本帳號不保證即時有人回覆。', 'scope_notice', self.operating_state(case)
        if state == 'awaiting_review' and result.risk == '低':
            return WAIT_REVIEW, 'review_notice', state
        if state == 'awaiting_review':
            with self.db() as db:
                case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
            if case and case['origin'] != 'risk':
                return WAIT_REVIEW, 'review_notice', state
        config = self.settings.snapshot()
        if not config['ai_enabled'] or (getattr(self.provider, 'requires_credentials', True) and not config['openai_key']):
            return (WAIT_REVIEW if result.risk == '中' else UNAVAILABLE), 'ai_unavailable', state
        mode = 'REVIEW' if result.risk == '中' else 'GENERAL'
        generation_request = self.generation_request(participant, text, event_id, result, mode, config)
        sources = generation_request['sources']
        if result.risk == '低' and not sources:
            with self.db() as db:
                self.log(db, participant, 'generation_not_called', f'event={event_id}; reason=no_source')
            return MENU, 'no_source_notice', state
        payload = generation_request['payload']
        with self.db() as db:
            cursor = db.execute('''INSERT INTO generations(event_id,conversation_id,risk,mode,status,payload,sources,model,
                       config_revision,prompt_version,knowledge_version,knowledge_hash,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (event_id, participant, result.risk, mode, 'queued', json.dumps(payload, ensure_ascii=False),
                        json.dumps(sources, ensure_ascii=False), config['model'], config['config_revision'],
                        generation_request['prompt_version'], self.knowledge.data['version'], self.knowledge.sha256, now(), now()))
            self.record_generation_context(db, cursor.lastrowid, participant, event_id, generation_request)
            self.log(db, participant, 'generation_queued', f'event={event_id}; mode={mode}; prompt={generation_request["prompt_version"]}')
        self.wake.set()
        return (WAIT_REVIEW + '\n系統正在準備供操作人員審閱的草稿。' if mode == 'REVIEW' else '正在依長照服務資料整理回覆，完成後會另送一則訊息。'), 'generation_notice', state

    def generation_request(self, participant, text, event_id, result, mode, config):
        sources = self.knowledge.retrieve(text)
        return {'sources': sources, 'payload': payload_for(text, mode, sources, config['model']),
                'prompt_version': PROMPT_VERSION, 'context': None}

    def record_generation_context(self, db, job_id, participant, event_id, request):
        pass

    def should_review_low(self, text, result):
        return bool(PERSONAL_HEALTH.search(text))

    def _eligible(self, db, job):
        latest = db.execute('SELECT id FROM events WHERE conversation_id=? ORDER BY rowid DESC LIMIT 1', (job['conversation_id'],)).fetchone()
        if not latest or latest['id'] != job['event_id']:
            return False
        case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (job['conversation_id'],)).fetchone()
        if job['mode'] == 'GENERAL':
            return case is None
        return bool(case and case['trigger_risk'] == '中' and case['origin'] == 'risk')

    def _fail(self, db, job, message):
        db.execute("UPDATE generations SET status='failed',error=?,updated_at=? WHERE id=?", (message, now(), job['id']))
        self._open_case(db, job['conversation_id'], job['risk'], 'generation_failure')
        self.log(db, job['conversation_id'], 'generation_failed', f"job={job['id']}; {message}")

    def process_one(self):
        with self.lock:
            config = self.settings.snapshot()
            with self.db() as db:
                row = db.execute("SELECT * FROM generations WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
                if not row:
                    return False
                job = dict(row)
                if not self._eligible(db, job) or job['config_revision'] != config['config_revision'] or not config['ai_enabled']:
                    db.execute("UPDATE generations SET status='cancelled',error=?,updated_at=? WHERE id=?", ('權限、設定或對話已變更。', now(), job['id']))
                    return True
                day = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
                count = db.execute('SELECT COUNT(*) FROM model_calls WHERE day=?', (day,)).fetchone()[0]
                if count >= config['daily_call_limit']:
                    self._fail(db, job, '已達本機每日模型呼叫上限，未呼叫 OpenAI。')
                    limited = True
                else:
                    db.execute('INSERT INTO model_calls(generation_id,day,created_at) VALUES(?,?,?)', (job['id'], day, now()))
                    db.execute("UPDATE generations SET status='running',updated_at=? WHERE id=?", (now(), job['id']))
                    limited = False
            if limited:
                self.deliver(job['conversation_id'], '已達本機測試呼叫上限，未產生模型回答。訊息已交由院內工作人員確認。', 'auto', 'generation_failure', event_id=job['event_id'])
                return True
        # No state lock during model networking. High risk and human actions remain available.
        report, formatted, problem = None, None, None
        try:
            report = self.provider.generate(config, json.loads(job['payload']))
            if report['status'] != 'completed':
                raise ModelError('模型未完成或拒絕回覆，未送出草稿。')
            try:
                parsed = json.loads(report['raw'])
            except (ValueError, TypeError):
                raise ModelError('模型未提供有效的結構化回覆，已停止送出。') from None
            formatted = validate_reply(parsed, json.loads(job['sources']), job['mode'])
            report['reply_format_version'] = REPLY_FORMAT_VERSION
        except ModelError as exc:
            problem = str(exc)
        except Exception:
            problem = '模型處理發生非預期錯誤，已停止送出；請檢查操作紀錄。'
        with self.lock:
            with self.db() as db:
                current = db.execute('SELECT * FROM generations WHERE id=?', (job['id'],)).fetchone()
                db.execute('UPDATE generations SET report=?,updated_at=? WHERE id=?', (json.dumps(report, ensure_ascii=False) if report else None, now(), job['id']))
                config_now = self.settings.snapshot()
                if current['status'] != 'running' or not self._eligible(db, job) or not config_now['ai_enabled'] or config_now['config_revision'] != job['config_revision']:
                    cancel_note = ('處理期間權限或對話變更，離線替代服務結果未送出。' if getattr(self, 'integration_mode', None) == 'offline'
                                   else '生成期間權限或對話變更，結果未送出；已發出的 API 請求可能計費。')
                    db.execute("UPDATE generations SET status='cancelled',error=?,updated_at=? WHERE id=?", (cancel_note, now(), job['id']))
                    return True
                if problem:
                    self._fail(db, job, problem)
                else:
                    db.execute('UPDATE generations SET status=?,response_text=?,updated_at=? WHERE id=?',
                               ('draft' if job['mode'] == 'REVIEW' else 'sending', formatted, now(), job['id']))
                    self.log(db, job['conversation_id'], 'generation_completed', f"job={job['id']}; mode={job['mode']}")
            if problem:
                self.deliver(job['conversation_id'], '這次模型回覆未通過處理或檢查，尚未送出回答。訊息已列入人工確認清單。', 'auto', 'generation_failure', event_id=job['event_id'])
            elif job['mode'] == 'GENERAL':
                delivery = self.deliver(job['conversation_id'], formatted, 'auto', 'grounded_generation', event_id=job['event_id'])
                with self.db() as db:
                    db.execute('UPDATE generations SET status=?,message_id=?,updated_at=? WHERE id=?',
                               ('sent' if delivery['status'] in {'simulated', 'simulated_line', 'api_accepted'} else 'delivery_issue', delivery['message_id'], now(), job['id']))
            return True

    def save_ai_settings(self, changes):
        with self.lock:
            revision = self.settings.snapshot()['config_revision'] + 1
            self.settings.save(changes | {'config_revision': revision})
            with self.db() as db:
                for row in db.execute("SELECT DISTINCT conversation_id FROM generations WHERE status IN ('queued','running','draft')").fetchall():
                    self.cancel_jobs(db, row['conversation_id'], '模型設定變更，舊任務已取消。請重新傳送測試訊息。')
                self.log(db, None, 'ai_settings_updated', f'revision={revision}; key_not_logged')

    def claim(self, case_id, operator):
        with self.lock:
            super().claim(case_id, operator)
            with self.db() as db:
                case = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                self.cancel_jobs(db, case['conversation_id'], '人工接手，自動生成作業停止。', only_auto=True)

    def resolve(self, case_id, note):
        with self.lock:
            super().resolve(case_id, note)
            with self.db() as db:
                case = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                self.cancel_jobs(db, case['conversation_id'], '事件已結案，舊草稿不再適用。')

    def human_reply(self, case_id, text):
        with self.lock:
            result = super().human_reply(case_id, text)
            with self.db() as db:
                case = db.execute('SELECT * FROM cases WHERE id=?', (case_id,)).fetchone()
                self.cancel_jobs(db, case['conversation_id'], '人工已回覆，先前草稿不再使用。')
            return result

    def review_draft(self, job_id, text, note, reject=False):
        with self.lock:
            with self.db() as db:
                job = db.execute('SELECT * FROM generations WHERE id=?', (job_id,)).fetchone()
                if not job or job['status'] != 'draft' or not self._eligible(db, job):
                    raise ValueError('草稿已失效、已處理，或目前不能送出。')
                case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status='claimed'", (job['conversation_id'],)).fetchone()
                if not case:
                    raise ValueError('請先接手事件，再審閱草稿。')
                db.execute('UPDATE generations SET status=?,operator=?,review_note=?,updated_at=? WHERE id=?',
                           ('rejected' if reject else 'sending', case['operator'], note, now(), job_id))
                self.log(db, job['conversation_id'], 'draft_rejected' if reject else 'draft_approved', f'job={job_id}; operator={case["operator"]}; note={note}')
            if reject:
                return {'status': 'rejected'}
            delivery = self.deliver(job['conversation_id'], text, 'human', 'reviewed_generation', event_id=job['event_id'])
            with self.db() as db:
                db.execute('UPDATE generations SET status=?,message_id=?,updated_at=? WHERE id=?',
                           ('approved' if delivery['status'] in {'simulated', 'simulated_line', 'api_accepted'} else 'delivery_issue', delivery['message_id'], now(), job_id))
            return delivery

    def start_worker(self):
        # Called once after binding ports and acquiring the process data lock.
        with self.lock, self.db() as db:
            jobs = db.execute("SELECT * FROM generations WHERE status IN ('queued','running','sending','draft')").fetchall()
            for job in jobs:
                self._fail(db, job, '程式曾中斷，任務結果需人工核對；未自動重試或重送。')
            db.execute("UPDATE messages SET delivery='failed_or_uncertain',error='程式中斷，送出結果需核對。' WHERE delivery='sending'")
        def loop():
            while not self.stopping.is_set():
                try:
                    if self.process_one():
                        continue
                    self.worker_problem = None
                except Exception:
                    self.worker_problem = '背景處理發生錯誤；請檢查資料夾及操作紀錄。'
                self.wake.wait(1)
                self.wake.clear()
        self.worker = threading.Thread(target=loop, daemon=True, name='bounded-generation')
        self.worker.start()

    def stop_worker(self):
        self.stopping.set()
        self.wake.set()

    def overview(self):
        result = super().overview()
        with self.db() as db:
            counts = dict(db.execute('SELECT status,COUNT(*) FROM generations GROUP BY status').fetchall())
            day = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            calls = db.execute('SELECT COUNT(*) FROM model_calls WHERE day=?', (day,)).fetchone()[0]
        result.update(reply_provider='OpenAI Responses（需啟用並完成實測）', generation_counts=counts,
                      model_calls_today=calls, knowledge=self.knowledge.data,
                      worker_running=bool(self.worker and self.worker.is_alive()), worker_problem=self.worker_problem,
                      data_directory=str(self.directory.resolve()), scope_version=SCOPE_VERSION)
        return result

    def detail(self, participant):
        result = super().detail(participant)
        with self.db() as db:
            result['generations'] = [dict(row) for row in db.execute('SELECT * FROM generations WHERE conversation_id=? ORDER BY id DESC LIMIT 30', (participant,))]
        return result
