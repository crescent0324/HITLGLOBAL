"""Live-capable service; deterministic summaries require no model call."""
from pathlib import Path
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from integration import IntegratedService, SCOPE_VERSION, RETRIEVAL_VERSION
from research import ResearchService
from service import now
from generation import validate_reply, ModelError
from candidate_runtime import RiskEngine, Governance, verify_candidate
from service_scope import assess_service_scope
from service_knowledge import ServiceKnowledge
from service_intents import identify_need
from resource_query import ResourceQueryEngine, is_general_resource_query, SOURCE_IDS, VERSION as RESOURCE_VERSION
from resource_followup import choice_for, TOPICS, MENU_QUESTION, TTL_SECONDS, RULE as FOLLOWUP_RULE, VERSION as FOLLOWUP_VERSION, PIPELINE_VERSION
import dialogue_flow as dialogue
from model_context import ModelContextMixin, VERSION as MODEL_CONTEXT_VERSION
PIPELINE_VERSION = dialogue.PIPELINE_VERSION


class LiveKnowledge(ServiceKnowledge):
    def explain(self, text):
        if is_general_resource_query(text):
            available = {s['id'] for s in self.data['sources']}
            return [dict(id=sid, score=100-i, matched_keywords=[],
                         matched_topics=['一般長照資訊查詢'], intent=RESOURCE_VERSION)
                    for i, sid in enumerate(SOURCE_IDS) if sid in available]
        rows = super().explain(text)
        # Pair a daycare introduction with the existing general application
        # source, without changing the risk or dialogue intent classifiers.
        if rows and rows[0]['id'] == 'LTC-DAYCARE' and not any(r['id'] == 'LTC-APPLY' for r in rows):
            rows = rows[:2] + [dict(id='LTC-APPLY', score=0, matched_keywords=[],
                                   matched_topics=['日照一般申請入口'], intent='daycare-entry-0.1.0')]
        return rows


class LiveService(ModelContextMixin, IntegratedService):
    integration_mode = 'live_acceptance'

    def __init__(self, data_dir, transport=None, provider=None):
        directory = Path(data_dir)
        directory.mkdir(parents=True, exist_ok=True)
        marker = directory / 'integration-environment.json'
        expected = {'mode': 'live-acceptance-v06', 'schema': 1}
        if marker.exists():
            if json.loads(marker.read_text(encoding='utf-8')) != expected:
                raise ValueError('請使用本版獨立資料夾，不能混用舊版紀錄。')
        elif any((directory / n).exists() for n in ('config.local.json', 'research.sqlite3')):
            raise ValueError('資料夾已有其他系統資料，請另用新的資料夾。')
        else:
            marker.write_text(json.dumps(expected), encoding='utf-8')
        self.classifier_metadata = verify_candidate()
        self.classifier_metadata['base_version'] = self.classifier_metadata['version']
        self.classifier_metadata['version'] = PIPELINE_VERSION
        self.classifier_metadata['sha256']['resource_query.py'] = hashlib.sha256(
            Path(__file__).with_name('resource_query.py').read_bytes()).hexdigest()
        self.classifier_metadata['sha256']['resource_followup.py'] = hashlib.sha256(
            Path(__file__).with_name('resource_followup.py').read_bytes()).hexdigest()
        self.classifier_metadata['sha256']['dialogue_flow.py'] = hashlib.sha256(
            Path(__file__).with_name('dialogue_flow.py').read_bytes()).hexdigest()
        ResearchService.__init__(self, directory, transport, provider, ResourceQueryEngine(), Governance())
        self.knowledge = LiveKnowledge()
        self.initialize_caregiver_tables()
        with self.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS webhook_receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_count INTEGER NOT NULL,
                received_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS recognition_records (
                event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                version TEXT NOT NULL, changed INTEGER NOT NULL,
                base_result_json TEXT NOT NULL, effective_result_json TEXT NOT NULL,
                created_at TEXT NOT NULL)''')

            db.execute('''CREATE TABLE IF NOT EXISTS followup_prompts (
                event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                version TEXT NOT NULL, knowledge_hash TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS context_decisions (
                event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                version TEXT NOT NULL, applied INTEGER NOT NULL, topic TEXT,
                reason TEXT NOT NULL, prompt_event_id TEXT, prompt_message_id INTEGER,
                raw_result_json TEXT NOT NULL, canonical_query TEXT, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS dialogue_turns (
                event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, topic TEXT,
                numbered_menu INTEGER NOT NULL, version TEXT NOT NULL,
                knowledge_hash TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS dialogue_decisions (
                event_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                decision_json TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS generation_contexts (
                generation_id INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
                conversation_id TEXT NOT NULL, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def dialogue_context(self, participant):
        with self.db() as db:
            case = db.execute("SELECT id FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
            latest = db.execute('SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1', (participant,)).fetchone()
            context = db.execute('SELECT * FROM dialogue_turns WHERE event_id=? AND conversation_id=?',
                                 (latest['event_id'], participant)).fetchone() if latest else None
            decision = db.execute('SELECT decision_json FROM dialogue_decisions WHERE event_id=? AND conversation_id=?',
                                  (latest['event_id'], participant)).fetchone() if context else None
        if case:
            return None, 'open_case'
        if not context or latest['actor'] != 'auto' or latest['source'] not in {'curated_summary', 'dialogue_notice', 'grounded_generation'}:
            return None, 'no_current_topic'
        if context['version'] not in dialogue.CONTEXT_VERSIONS or context['knowledge_hash'] != self.knowledge.sha256:
            return None, 'topic_version_changed'
        if latest['delivery'] not in {'simulated', 'simulated_line', 'api_accepted'}:
            return None, 'topic_delivery_unconfirmed'
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(context['created_at'])).total_seconds()
        if not 0 <= age <= dialogue.TTL_SECONDS:
            return None, 'topic_expired'
        resolved = (json.loads(decision['decision_json']).get('resolved') or {}) if decision else {}
        return dict(context) | {'message_id': latest['id'], 'focus_action': resolved.get('focus_action')}, 'recent_topic'

    def classify_message(self, participant, text):
        raw = self.engine.classify(text)
        request = dialogue.parse_request(text)
        previous, context_status = self.dialogue_context(participant)
        resolved = dialogue.resolve(request, previous)
        trace = dict(applied=False, topic=choice_for(text), reason=context_status,
                     prompt_event_id=None, prompt_message_id=None, raw_result=asdict(raw), canonical_query=None)
        record = dict(version=dialogue.VERSION, applied=False, request=request,
                      context_status=context_status, previous_event_id=previous['event_id'] if previous else None,
                      previous_message_id=previous['message_id'] if previous else None,
                      raw_result=asdict(raw), resolved=resolved)
        eligible = raw.matched_rules in (['M12-UNKNOWN'], ['L12-RESOURCE'], ['L12-SUPPORT'], ['L12-GREETING'], ['L14-GENERAL-RESOURCE'])
        # Preserve the existing optional generation path for standalone questions
        # already understood by the classifier. Context/control replies are fixed.
        if (resolved and not previous and self.settings.snapshot()['ai_enabled'] and raw.risk == '低'
                and resolved['action'] in {'detail', 'apply'}):
            eligible = False
        # Complete-message grammar, current risk, and case status all have to pass.
        if resolved and eligible and context_status != 'open_case' and not self.manual_requested(text, raw):
            record['applied'] = True
            label = dialogue.TOPICS.get(resolved['topic'], ('尚待釐清的服務',))[0]
            canonical = label + '：' + dialogue.ACTION_LABELS[resolved['action']]
            menu_choice = bool(previous and previous['numbered_menu'] and choice_for(text)
                               and resolved['action'] in {'detail', 'apply'})
            rule = FOLLOWUP_RULE if menu_choice else dialogue.RULE
            if menu_choice:
                topic = choice_for(text)
                trace.update(applied=True, topic=topic, reason='exact_recent_menu_choice',
                             prompt_event_id=previous['event_id'], prompt_message_id=previous['message_id'],
                             canonical_query=TOPICS[topic]['canonical'])
            raw = replace(raw, risk='低', hitl='人類監督', review_required=False,
                          matched_rules=[rule], version=PIPELINE_VERSION,
                          rationale='限定服務對話：'+canonical+'；不判定健康狀況或個人資格。')
        raw.context_trace = trace
        raw.dialogue_trace = record
        return raw

    def record_classification(self, db, participant, event_id, result, plan):
        super().record_classification(db, participant, event_id, result, plan)
        base = asdict(RiskEngine().classify(result.normalized_text))
        effective = asdict(result)
        db.execute('INSERT INTO recognition_records VALUES(?,?,?,?,?,?,?)',
                   (event_id, participant, PIPELINE_VERSION, int(base != effective),
                    json.dumps(base, ensure_ascii=False), json.dumps(effective, ensure_ascii=False), now()))
        trace = getattr(result, 'context_trace', None)
        if trace:
            db.execute('INSERT INTO context_decisions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (event_id, participant, FOLLOWUP_VERSION, int(trace['applied']), trace['topic'], trace['reason'],
                        trace['prompt_event_id'], trace['prompt_message_id'], json.dumps(trace['raw_result'], ensure_ascii=False),
                        trace['canonical_query'], now()))
        record = getattr(result, 'dialogue_trace', None)
        if record:
            db.execute('INSERT INTO dialogue_decisions VALUES(?,?,?,?)',
                       (event_id, participant, json.dumps(record, ensure_ascii=False), now()))

    def remember_dialogue(self, db, participant, event_id, topic, numbered_menu=False):
        db.execute('INSERT INTO dialogue_turns VALUES(?,?,?,?,?,?,?)',
                   (event_id, participant, topic, int(numbered_menu), dialogue.VERSION, self.knowledge.sha256, now()))
        if numbered_menu:
            db.execute('INSERT INTO followup_prompts VALUES(?,?,?,?,?)',
                       (event_id, participant, FOLLOWUP_VERSION, self.knowledge.sha256, now()))

    def dialogue_reply(self, participant, event_id, resolved, scope):
        action, topic = resolved['action'], resolved.get('topic')
        label = dialogue.TOPICS.get(topic, ('長照服務',))[0]
        by_id = {s['id']: s for s in self.knowledge.data['sources']}
        ids = dialogue.sources_for(resolved)
        sources = [by_id[sid] for sid in ids if sid in by_id]
        retrieval = [dict(id=s['id'], score=100-i, matched_keywords=[],
                          matched_topics=[label], intent=dialogue.VERSION) for i,s in enumerate(sources)]
        state, source = 'automatic', 'dialogue_notice'
        numbered = action in {'menu', 'clarify'} or topic == 'services'
        if action in {'cost', 'eligibility', 'availability'}:
            limit = {'cost': '費用與補助金額', 'eligibility': '申請資格', 'availability': '名額與可安排時間'}[action]
            need = dict(key='dialogue_'+action, label=label+'／'+limit, route='coordination',
                        intro='你接著詢問'+label+'的'+limit+'。目前資料不足以確認這一項，已保留前面的服務主題供人工查看。',
                        question='可補充希望確認的事項，操作人員接手後再協助整理。', sources=ids)
            answer, source, state = self.open_service_request(participant, event_id, need, sources, 'service_coordination')
        elif action == 'ack':
            answer = '收到。' if dialogue.normalize(resolved.get('text', '')) in {'不用了', '先這樣'} else '不客氣。'
            answer += ('若還想了解'+label+'，可以接著問；也可以換一項服務。' if topic else '有其他長照服務問題，也可以繼續問。')
            # Do not pretend that an acknowledgement itself displayed a menu.
            numbered = False
        elif action == 'clarify':
            answer = '目前無法確定你指的是哪一項服務。可以直接說服務名稱，例如喘息服務、居家服務或日間照顧。\n\n'+dialogue.MENU
            topic = 'services'
        elif sources and len(sources) == len(ids):
            if action == 'apply':
                intro = '關於'+label+'，以下提供一般長照申請入口；個別服務安排仍由受理單位確認。'
            elif action == 'repeat':
                intro = '目前已查核的'+label+'資料如下；尚未補入其他細節。'
            else:
                intro = '以下是'+label+'的既有資料摘要。'
            body = '【服務資料摘要・未使用模型生成】\n'+intro+'\n\n'+'\n\n'.join(s['summary'] for s in sources)
            body += '\n\n'+dialogue.prompt_for(topic)
            try:
                answer = validate_reply({'answer':body, 'source_ids':ids, 'insufficient':False}, sources, 'GENERAL')
                source = 'curated_summary'
            except ModelError:
                answer, source, state = self._missing_content(participant, event_id)
        else:
            answer, source, state = self._missing_content(participant, event_id)
        with self.db() as db:
            db.execute('INSERT INTO service_decisions VALUES(?,?,?,?,?,?,?,?,?)',
                       (event_id, participant, SCOPE_VERSION, json.dumps(scope, ensure_ascii=False),
                        json.dumps(retrieval, ensure_ascii=False), self.knowledge.sha256, state, source, now()))
            if state == 'automatic':
                self.remember_dialogue(db, participant, event_id, topic, numbered)
            self.log(db, participant, 'service_dialogue_reply', f'event={event_id}; action={action}; topic={topic}; source={source}; model_called=false')
        return answer, source, state

    def dialogue_scope(self, text, result):
        scope = assess_service_scope(text, result).to_dict()
        record = getattr(result, 'dialogue_trace', {})
        resolved = record.get('resolved') or {}
        if dialogue.UNRESOLVED_CONCERN.search(text):
            scope.update(allow_automatic=False,
                         reason='訊息提到狀況或身體異常而尚未釐清，附帶服務詢問不解除人工確認。')
        if (record.get('applied') and resolved.get('explicit') and resolved.get('topic') == 'alarm'
                and scope['route'] == 'general' and scope['unresolved_health_terms'] == ['急救']):
            # Full-message grammar establishes the service name 緊急救援系統.
            # A symptom or any unconsumed clause cannot reach this exception.
            scope.update(allow_automatic=True, unresolved_health_terms=[],
                         reason='完整問句僅詢問緊急救援系統服務；急救二字出現在服務名稱中，未描述正在發生的事故。')
        return scope

    def should_review_low(self, text, result):
        return not self.dialogue_scope(text, result)['allow_automatic']

    def choose_reply(self, participant, text, event_id, result, plan, state, answer, source):
        scope = self.dialogue_scope(text, result)
        config = self.settings.snapshot()
        record = getattr(result, 'dialogue_trace', {})
        model_dialogue = bool(config['ai_enabled'] and record.get('applied')
                              and record['resolved']['action'] in {'detail','apply','repeat'})
        if record.get('applied') and result.risk == '低' and state == 'automatic' and scope['allow_automatic'] and not model_dialogue:
            return self.dialogue_reply(participant, event_id, record['resolved'] | {'text':text}, scope)
        context = getattr(result, 'context_trace', {})
        followup = TOPICS[context['topic']] if context.get('applied') else None
        # Current risk, open cases and entry-information routes take precedence.
        if result.risk == '低' and state == 'automatic' and scope['allow_automatic'] and not config['ai_enabled']:
            retrieval = ([dict(id=sid, score=100-i, matched_keywords=[], matched_topics=[followup['label']], intent=FOLLOWUP_VERSION)
                          for i, sid in enumerate(followup['sources'])] if followup else self.knowledge.explain(text))
            by_id = {s['id']: s for s in self.knowledge.data['sources']}
            sources = [by_id[r['id']] for r in retrieval if r['id'] in by_id]
            menu = bool(followup or is_general_resource_query(text))
            if sources:
                need = identify_need(text)
                topic = 'services' if menu else dialogue.topic_from_sources([s['id'] for s in sources], need)
                if followup:
                    need = {'intro': followup['intro'], 'question': MENU_QUESTION}
                elif menu:
                    need = {'intro': '可以先從長照服務類別與申請方式了解。以下是既有官方資料的摘要。',
                            'question': MENU_QUESTION}
                intro = need['intro'] if need else '以下為這項服務的已查核資料，實際安排仍需洽承辦單位確認。'
                question = '\n\n' + dialogue.prompt_for(topic)
                body = '【服務資料摘要・未使用模型生成】\n' + intro + '\n\n'
                body += '\n\n'.join(s['summary'] for s in sources) + question
                try:
                    answer = validate_reply({'answer': body, 'source_ids': [s['id'] for s in sources], 'insufficient': False}, sources, 'GENERAL')
                    source = 'curated_summary'
                except ModelError:
                    answer, source, state = self._missing_content(participant, event_id)
            else:
                answer, source, state = self._missing_content(participant, event_id)
            with self.db() as db:
                db.execute('INSERT INTO service_decisions VALUES(?,?,?,?,?,?,?,?,?)',
                    (event_id, participant, SCOPE_VERSION, json.dumps(scope, ensure_ascii=False),
                     json.dumps(retrieval, ensure_ascii=False), self.knowledge.sha256,
                     state, source, now()))
                if source == 'curated_summary':
                    self.remember_dialogue(db, participant, event_id, topic, menu)
                self.log(db, participant, 'curated_service_decision', f'event={event_id}; source={source}; model_called=false')
            return answer, source, state
        answer, source, state = super().choose_reply(participant, text, event_id, result, plan, state, answer, source)
        with self.db() as db:
            db.execute('UPDATE service_decisions SET decision_json=? WHERE event_id=?',
                       (json.dumps(scope, ensure_ascii=False), event_id))
            context_row=db.execute('SELECT metadata_json FROM generation_contexts WHERE event_id=?',(event_id,)).fetchone()
            if context_row:
                meta=json.loads(context_row['metadata_json'])
                retrieval=[dict(id=sid,score=100-i,matched_keywords=[],matched_topics=[meta['topic'] or '前文與本次問題'],intent=MODEL_CONTEXT_VERSION)
                           for i,sid in enumerate(meta['source_ids'])]
                db.execute('UPDATE service_decisions SET retrieval_json=? WHERE event_id=?',
                           (json.dumps(retrieval,ensure_ascii=False),event_id))
        # A resource question never closes an existing case. Explain the ongoing
        # state instead of presenting another generic medical-review message.
        if result.risk == '低' and state != 'automatic' and scope['allow_automatic']:
            with self.db() as db:
                case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
                if case:
                    status = ('這段對話目前由研究操作人員處理，你的新訊息已記錄。'
                              if case['status'] == 'claimed' else
                              '你的新訊息已記錄在同一件待辦，目前仍在等待研究操作人員接手。')
                    answer = status + '先前的事件尚未結案，一般自動回覆仍暫停；由操作人員確認處理完成並結案後恢復。'
                    source = 'case_status_notice'
                    db.execute('UPDATE service_decisions SET reply_source=? WHERE event_id=?', (source, event_id))
        return answer, source, state

    def detail(self, participant):
        out = super().detail(participant)
        with self.db() as db:
            out['recognition_records'] = [dict(row) for row in db.execute(
                'SELECT * FROM recognition_records WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100', (participant,))]
            out['context_decisions'] = [dict(row) for row in db.execute(
                'SELECT * FROM context_decisions WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100', (participant,))]
            out['dialogue_decisions'] = [dict(row) for row in db.execute(
                'SELECT * FROM dialogue_decisions WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100', (participant,))]
            out['generation_contexts'] = [dict(row) for row in db.execute(
                'SELECT * FROM generation_contexts WHERE conversation_id=? ORDER BY generation_id DESC LIMIT 30',(participant,))]
        case = out['case']
        latest = out['events'][0] if out['events'] else None
        if not case:
            guidance = '目前沒有未結案事件。後續訊息會重新分級；低風險且資料適用時可自動回覆。'
        else:
            guidance = (f'最新訊息為低風險；事件 #{case["id"]} 仍未結案，因此持續人工處理。'
                        if latest and latest['risk'] == '低' else
                        f'事件 #{case["id"]} 尚未結案。' + (latest['rationale'] if latest else ''))
            guidance += ('請先接手，再確認需求與回覆；處理完成後填寫紀錄並結案。'
                         if case['status'] == 'pending' else
                         '送出人工回覆後，仍須填寫結案紀錄並按「結案並恢復自動處理」。')
        out['conversation_guidance'] = guidance
        return out

    def _missing_content(self, participant, event_id):
        need = dict(key='uncovered', label='資料待補與需求整理', route='content_pending',
            intro='目前資料尚未涵蓋這項需求，已列入研究操作人員的待辦。',
            question='最希望先獲得哪一項協助？', sources=[])
        return self.open_service_request(participant, event_id, need, [], 'content_pending')

    def record_webhook_receipt(self, event_count):
        with self.db() as db:
            db.execute('INSERT INTO webhook_receipts(event_count,received_at) VALUES(?,?)', (event_count, now()))

    def legacy_line_path(self):
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'HITLLineResearchV02/config.local.json'

    def import_legacy_line(self):
        # Invoked by the local operator button; never runs at startup.
        with self.lock:
            current = self.settings.snapshot()
            if current['line_enabled'] or current['channel_secret'] or current['access_token']:
                raise ValueError('本版已有 LINE 設定；請使用設定欄位更新，避免覆蓋。')
            try:
                old = json.loads(self.legacy_line_path().read_text(encoding='utf-8'))
                changes = {name: old[name] for name in ('channel_secret', 'access_token')}
            except (OSError, ValueError, KeyError, TypeError):
                raise ValueError('未找到可用的舊版 LINE 設定，請在本機欄位填入。') from None
            if any(not isinstance(v,str) or not v or len(v)>4096 or not v.isascii() or any(c.isspace() for c in v) for v in changes.values()):
                raise ValueError('舊版 LINE 設定不完整，請在本機欄位填入。')
            self.settings.save(changes | {'line_enabled':False})
            with self.db() as db:
                self.log(db,None,'legacy_line_imported','LINE credentials copied locally; LINE remains disabled; OpenAI credentials not copied')
        return self.settings.public()

    def overview(self):
        out = ResearchService.overview(self)
        for case in out['cases']:
            self.pending_age(case)
        with self.db() as db:
            total = db.execute('SELECT COUNT(*) FROM webhook_receipts').fetchone()[0]
            empty = db.execute('SELECT COUNT(*) FROM webhook_receipts WHERE event_count=0').fetchone()[0]
            summaries = db.execute("SELECT COUNT(*) FROM messages WHERE source='curated_summary'").fetchone()[0]
        out.update(version='line-live-acceptance-0.6.7', integration_mode=self.integration_mode,
            classifier=self.classifier_metadata, clinical_review='pending',
            reply_provider='OpenAI（啟用後）／已查核固定摘要（模型關閉時）',
            external_services_enabled=bool(out['settings']['ready'] or out['settings']['ai_enabled']),
            scope_version=SCOPE_VERSION, retrieval_version=RETRIEVAL_VERSION + '+' + RESOURCE_VERSION + '+' + FOLLOWUP_VERSION + '+' + dialogue.VERSION,
            model_context_version=MODEL_CONTEXT_VERSION,
            readiness={'signed_webhooks':total, 'verification_requests':empty,
                       'legacy_line_available':self.legacy_line_path().is_file(),
                       'curated_summaries':summaries, 'phone_receipt_status':'pending_manual_confirmation',
                       'note':'通過簽章檢查不等於手機已收到；請逐項記錄實機驗收。'})
        return out
