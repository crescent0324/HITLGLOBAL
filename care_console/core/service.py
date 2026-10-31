"""LINE research prototype. Frozen classifications and operational case state are separate."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib import request, error

from frozen.risk_engine_v1_1_tw import RiskEngineV11TW
from frozen.hitl_governance_v1 import HITLGovernanceV1

VERSION = "line-caregiver-0.5.0"
RANK = {"低": 0, "中": 1, "高": 2}
HUMAN_COMMANDS = {"轉人工", "人工協助", "找人工"}
WELCOME = "這是論文研究展示帳號，沒有醫療人員值班。請只使用虛構測試訊息，不提供診斷或治療。請向研究者取得加入碼，再傳送「加入 加入碼」。"
LOW_REPLY = "已收到你的訊息。目前使用固定範本回覆。需要院內工作人員協助時，請傳送「轉人工」。系統接收訊息不代表已確認健康狀況。"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class DeliveryError(Exception):
    """Sanitized delivery error; never contains access tokens or message contents."""


class Settings:
    def __init__(self, directory: Path):
        self.path = directory / "config.local.json"
        directory.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.data = {"channel_secret": "", "access_token": "", "line_enabled": False,
                     "join_code": secrets.token_hex(4).upper(), "session_secret": secrets.token_hex(32),
                     "openai_key": "", "model": "gpt-5-mini", "ai_enabled": False, "daily_call_limit": 30,
                     "config_revision": 0}
        if self.path.exists():
            self.data.update(json.loads(self.path.read_text(encoding="utf-8")))
        else:
            self.save({})

    def snapshot(self):
        with self.lock:
            return self.data.copy()

    def save(self, changes):
        with self.lock:
            updated = self.data | changes
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)
            self.data = updated

    def public(self):
        data = self.snapshot()
        return {"has_secret": bool(data["channel_secret"]), "has_token": bool(data["access_token"]),
                "line_enabled": data["line_enabled"], "join_code": data["join_code"],
                "ready": bool(data["channel_secret"] and data["access_token"] and data["line_enabled"]),
                "has_openai_key": bool(data["openai_key"]), "model": data["model"],
                "ai_enabled": data["ai_enabled"], "daily_call_limit": data["daily_call_limit"]}


class LineTransport:
    def __init__(self, settings):
        self.settings = settings

    def send(self, kind, recipient, text, reply_token=None, retry_key=None):
        config = self.settings.snapshot()
        if not config["line_enabled"] or not config["access_token"]:
            raise DeliveryError("LINE 尚未啟用或未設定存取權杖。")
        payload = {"messages": [{"type": "text", "text": text[:4500]}]}
        if kind == "reply":
            if not reply_token:
                raise DeliveryError("缺少可用的 LINE reply token。")
            payload["replyToken"] = reply_token
        else:
            payload["to"] = recipient
        headers = {"Authorization": "Bearer " + config["access_token"], "Content-Type": "application/json"}
        if kind == "push" and retry_key:
            headers["X-Line-Retry-Key"] = retry_key
        req = request.Request("https://api.line.me/v2/bot/message/" + kind,
                              data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=8) as response:
                response.read()
        except error.HTTPError as exc:
            if kind == "push" and exc.code == 409 and exc.headers.get("x-line-accepted-request-id"):
                return
            raise DeliveryError(f"LINE API 回傳 HTTP {exc.code}；尚未確認收件者收到訊息。") from None
        except (error.URLError, TimeoutError, OSError):
            raise DeliveryError("LINE API 連線失敗或逾時，送出結果不確定；請先核對 LINE 對話。") from None


class Service:
    def __init__(self, data_dir, transport=None, engine=None, governance=None):
        self.directory = Path(data_dir)
        self.settings = Settings(self.directory)
        self.database = self.directory / "research.sqlite3"
        self.transport = transport or LineTransport(self.settings)
        self.engine = engine if engine is not None else RiskEngineV11TW()
        self.governance = governance if governance is not None else HITLGovernanceV1()
        # Serializes state transitions and delivery in this single-process prototype.
        self.lock = threading.RLock()
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY, transport TEXT NOT NULL, label TEXT NOT NULL,
                    last_risk TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, text TEXT NOT NULL,
                    risk TEXT NOT NULL, planned_hitl TEXT NOT NULL, planned_mode TEXT NOT NULL,
                    rules TEXT NOT NULL, rationale TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                    status TEXT NOT NULL, trigger_risk TEXT NOT NULL, origin TEXT NOT NULL,
                    created_at TEXT NOT NULL, claimed_at TEXT, closed_at TEXT,
                    operator TEXT, close_note TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_case ON cases(conversation_id)
                    WHERE status != 'closed';
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                    event_id TEXT, actor TEXT NOT NULL, text TEXT NOT NULL,
                    source TEXT NOT NULL, delivery TEXT NOT NULL, error TEXT,
                    retry_key TEXT, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT,
                    action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS controls (id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def log(self, db, participant, action, detail):
        db.execute("INSERT INTO audit(conversation_id,action,detail,created_at) VALUES(?,?,?,?)",
                   (participant, action, detail, now()))

    def enroll(self, participant, channel):
        stamp = now()
        label = ("本機測試 " if channel == "simulation" else "LINE 測試者 ") + hashlib.sha256(participant.encode()).hexdigest()[:6]
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO conversations(id,transport,label,created_at,updated_at) VALUES(?,?,?,?,?)",
                       (participant, channel, label, stamp, stamp))

    def enrolled(self, participant):
        with self.db() as db:
            return db.execute("SELECT 1 FROM conversations WHERE id=?", (participant,)).fetchone() is not None

    def _open_case(self, db, participant, risk, origin):
        case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
        if not case:
            db.execute("INSERT INTO cases(conversation_id,status,trigger_risk,origin,created_at) VALUES(?,?,?,?,?)",
                       (participant, "pending", risk, origin, now()))
            self.log(db, participant, "case_opened", f"risk={risk}; origin={origin}")
        elif RANK[risk] > RANK[case["trigger_risk"]]:
            db.execute("UPDATE cases SET trigger_risk=? WHERE id=?", (risk, case["id"]))
            self.log(db, participant, "case_escalated", f"case={case['id']}; risk={risk}")
        return db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()

    @staticmethod
    def operating_state(case):
        if case is None:
            return "automatic"
        if case["status"] == "claimed":
            return "human_active"
        if case["trigger_risk"] == "高" or case["origin"] == "user_request":
            return "awaiting_takeover"
        return "awaiting_review"

    def receive(self, participant, text, event_id, channel="simulation", reply_token=None):
        with self.lock:
            if not self.enrolled(participant):
                raise ValueError("測試者尚未加入。")
            with self.db() as db:
                previous = db.execute("SELECT id FROM events WHERE id=?", (event_id,)).fetchone()
            if previous:
                return {"duplicate": True, "event_id": event_id}
            result = self.classify_message(participant, text)
            plan = self.governance.apply(result)
            stamp = now()
            with self.db() as db:
                db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)",
                           (event_id, participant, text, result.risk, plan.hitl_state, plan.response_mode,
                            json.dumps(result.matched_rules, ensure_ascii=False), result.rationale, stamp))
                self.record_classification(db, participant, event_id, result, plan)
                db.execute("INSERT INTO messages(conversation_id,event_id,actor,text,source,delivery,created_at) VALUES(?,?,?,?,?,?,?)",
                           (participant, event_id, "user", text, channel, "received", stamp))
                db.execute("UPDATE conversations SET last_risk=?, updated_at=? WHERE id=?", (result.risk, stamp, participant))
                case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
                manual_requested = self.manual_requested(text, result)
                if result.risk in {"中", "高"} or manual_requested:
                    case = self._open_case(db, participant, result.risk, "user_request" if manual_requested else "risk")
                    if manual_requested and case["origin"] != "user_request":
                        db.execute("UPDATE cases SET origin='user_request' WHERE id=?", (case["id"],))
                        case = db.execute("SELECT * FROM cases WHERE id=?", (case["id"],)).fetchone()
                state = self.operating_state(case)
                self.log(db, participant, "message_classified", f"event={event_id}; risk={result.risk}; state={state}")
                self.on_incoming(db, participant, event_id)

            # State gates run before any general response. The present version has no LLM provider.
            if result.risk == "高":
                notice = "院內工作人員已接手。" if state == "human_active" else "已建立待接手事件，尚不代表有人接手。"
                answer = plan.fixed_message + "\n" + notice + "本帳號不保證即時有人回覆。"
                source = "fixed_safety"
            elif state == "human_active":
                answer, source = None, None
            elif state == "awaiting_takeover":
                answer = "訊息已記錄，正在等待院內工作人員接手，一般自動回覆已暫停。本帳號不保證即時有人回覆；請勿等待本帳號提供緊急協助。"
                source = "waiting_notice"
            elif state == "awaiting_review":
                answer = ("你提供的資訊需要進一步確認。此版本僅使用固定範本，不提供診斷、調藥或治療決策。"
                          "\n訊息已列入院內工作人員的待確認清單，目前尚未接手。你也可以傳送「轉人工」。")
                source = "restricted_template"
            else:
                answer, source = LOW_REPLY, "general_template"
            answer, source, state = self.choose_reply(participant, text, event_id, result, plan, state, answer, source)
            delivery = None
            if answer:
                delivery = self.deliver(participant, answer, "auto", source, event_id=event_id, reply_token=reply_token)
            return {"event_id": event_id, "risk": result.risk, "planned_hitl": plan.hitl_state,
                    "planned_mode": plan.response_mode, "rules": result.matched_rules,
                    "state": state, "reply": answer, "reply_source": source, "delivery": delivery}

    def classify_message(self, participant, text):
        return self.engine.classify(text)

    def on_incoming(self, db, participant, event_id):
        pass

    def record_classification(self, db, participant, event_id, result, plan):
        pass

    def manual_requested(self, text, result):
        return text.strip() in HUMAN_COMMANDS

    def choose_reply(self, participant, text, event_id, result, plan, state, answer, source):
        return answer, source, state

    def deliver(self, participant, text, actor, source, event_id=None, reply_token=None):
        with self.db() as db:
            conversation = db.execute("SELECT * FROM conversations WHERE id=?", (participant,)).fetchone()
            retry_key = str(uuid.uuid4())
            cursor = db.execute("INSERT INTO messages(conversation_id,event_id,actor,text,source,delivery,retry_key,created_at) VALUES(?,?,?,?,?,?,?,?)",
                                (participant, event_id, actor, text, source, "sending", retry_key, now()))
            message_id = cursor.lastrowid
        status, problem = "simulated", None
        if conversation["transport"] == "line":
            try:
                self.transport.send("reply" if actor == "auto" and reply_token else "push", participant, text,
                                    reply_token=reply_token, retry_key=retry_key)
                status = getattr(self.transport, 'delivery_status', 'api_accepted')
            except DeliveryError as exc:
                status, problem = "failed_or_uncertain", str(exc)
        with self.db() as db:
            db.execute("UPDATE messages SET delivery=?,error=? WHERE id=?", (status, problem, message_id))
            self.log(db, participant, "message_outgoing", f"message={message_id}; actor={actor}; delivery={status}")
        return {"status": status, "error": problem, "message_id": message_id}

    def claim(self, case_id, operator):
        with self.lock, self.db() as db:
            case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if not case or case["status"] != "pending":
                raise ValueError("此事件目前無法接手。")
            db.execute("UPDATE cases SET status='claimed',claimed_at=?,operator=? WHERE id=?", (now(), operator, case_id))
            self.log(db, case["conversation_id"], "case_claimed", f"case={case_id}; operator={operator}")

    def human_reply(self, case_id, text):
        with self.lock:
            with self.db() as db:
                case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if not case or case["status"] != "claimed":
                raise ValueError("請先接手事件，再回覆。")
            return self.deliver(case["conversation_id"], text, "human", "operator")

    def resolve(self, case_id, note):
        with self.lock, self.db() as db:
            case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
            if not case or case["status"] != "claimed":
                raise ValueError("只有已接手事件可以結案。")
            db.execute("UPDATE cases SET status='closed',closed_at=?,close_note=? WHERE id=?", (now(), note, case_id))
            self.log(db, case["conversation_id"], "case_closed_automation_resumed", f"case={case_id}; note={note}")

    def overview(self):
        with self.db() as db:
            conversations = [dict(x) for x in db.execute("SELECT * FROM conversations ORDER BY updated_at DESC LIMIT 100")]
            cases = [dict(x) for x in db.execute("SELECT cases.*,conversations.label,conversations.transport FROM cases JOIN conversations ON conversations.id=cases.conversation_id ORDER BY CASE cases.status WHEN 'pending' THEN 0 WHEN 'claimed' THEN 1 ELSE 2 END, CASE trigger_risk WHEN '高' THEN 0 WHEN '中' THEN 1 ELSE 2 END, cases.id DESC LIMIT 100")]
            counts = {"events": db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                      "pending": db.execute("SELECT COUNT(*) FROM cases WHERE status='pending'").fetchone()[0],
                      "claimed": db.execute("SELECT COUNT(*) FROM cases WHERE status='claimed'").fetchone()[0],
                      "delivery_issues": db.execute("SELECT COUNT(*) FROM messages WHERE delivery IN ('failed_or_uncertain','sending')").fetchone()[0]}
        return {"conversations": conversations, "cases": cases, "counts": counts, "settings": self.settings.public(),
                "version": VERSION, "reply_provider": "固定範本（尚未串接 LLM）"}

    def detail(self, participant):
        with self.db() as db:
            conversation = db.execute("SELECT * FROM conversations WHERE id=?", (participant,)).fetchone()
            if not conversation:
                raise ValueError("找不到對話。")
            case = db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'", (participant,)).fetchone()
            events = [dict(x) for x in db.execute("SELECT * FROM events WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100", (participant,))]
            messages = [dict(x) for x in db.execute("SELECT * FROM (SELECT * FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 200) ORDER BY id", (participant,))]
            audit = [dict(x) for x in db.execute("SELECT * FROM audit WHERE conversation_id=? ORDER BY id DESC LIMIT 40", (participant,))]
        return {"conversation": dict(conversation), "case": dict(case) if case else None, "state": self.operating_state(case),
                "messages": messages, "events": events, "audit": audit}


def signature_valid(body, signature, secret):
    if not secret or not signature:
        return False
    expected = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode("ascii")
    try:
        return hmac.compare_digest(expected, signature)
    except TypeError:
        return False
