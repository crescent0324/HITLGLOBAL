"""Offline integration environment; substitutes never call external services."""
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import json
from candidate_runtime import RiskEngine,Governance,verify_candidate
from research import ResearchService
from service import now
from service_scope import assess_service_scope, VERSION as SCOPE_VERSION
from service_knowledge import ServiceKnowledge, VERSION as RETRIEVAL_VERSION
from service_intents import identify_need

class OfflineProvider:
 is_test_double=True
 requires_credentials=False
 def __init__(self):self.calls=[]
 def generate(self,config,payload):
  data=json.loads(payload['input']);self.calls.append(payload)
  text=('【離線替代服務草稿】這段固定測試文字用於確認人工審閱、修改及核准流程，尚未取得真實模型回答。'
        if data['mode']=='REVIEW' else '【離線替代服務輸出】這段固定測試文字用於確認低風險回覆與資料來源紀錄，尚未取得真實模型回答。')
  need=identify_need(data['question'])
  if data['mode']=='GENERAL' and need and need['route']=='general':
   text='【離線替代服務・固定資料摘要】\n'+need['intro']+'\n\n'+'\n\n'.join(s['summary'] for s in data['sources'])+'\n\n'+need['question']
  body={'answer':text,'source_ids':[s['id'] for s in data['sources']],'insufficient':False}
  return {'raw':json.dumps(body,ensure_ascii=False),'status':'completed','model':'offline-test-double',
          'response_id':None,'usage':None,'latency_ms':0,'test_double':True,'external_api_called':False}

class OfflineLineTransport:
 is_test_double=True
 delivery_status='simulated_line'
 def __init__(self):self.calls=[]
 def send(self,kind,recipient,text,reply_token=None,retry_key=None):
  self.calls.append({'kind':kind,'recipient':recipient,'text':text,'reply_token':reply_token,'retry_key':retry_key})

class IntegratedService(ResearchService):
 integration_mode='offline'
 scope_version=SCOPE_VERSION
 def __init__(self,data_dir,transport=None,provider=None):
  if provider is not None and not getattr(provider,'is_test_double',False):
   raise ValueError('離線整合環境僅接受明確標記的模型替代服務。')
  if transport is not None and not getattr(transport,'is_test_double',False):
   raise ValueError('離線整合環境僅接受明確標記的LINE替代服務。')
  directory=Path(data_dir);directory.mkdir(parents=True,exist_ok=True)
  marker=directory/'integration-environment.json'
  expected={'mode':'offline-caregiver-v05','schema':1}
  if marker.exists():
   if json.loads(marker.read_text(encoding='utf-8'))!=expected:raise ValueError('此資料夾不屬於本版離線整合環境。')
  elif (directory/'config.local.json').exists() or (directory/'research.sqlite3').exists():
   raise ValueError('此資料夾已有其他系統資料，請使用新的獨立資料夾。')
  else:marker.write_text(json.dumps(expected),encoding='utf-8')
  self.classifier_metadata=verify_candidate()
  super().__init__(directory,transport if transport is not None else OfflineLineTransport(),
                   provider if provider is not None else OfflineProvider(),RiskEngine(),Governance())
  self.knowledge=ServiceKnowledge()
  self.settings.save({'channel_secret':'','access_token':'','line_enabled':False,'openai_key':'',
                      'ai_enabled':True,'model':'offline-test-double','daily_call_limit':200})
  self.initialize_caregiver_tables()

 def initialize_caregiver_tables(self):
  with self.db() as db:
   db.execute('''CREATE TABLE IF NOT EXISTS classification_records (
    event_id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,classifier_version TEXT NOT NULL,
    classifier_hashes TEXT NOT NULL,result_json TEXT NOT NULL,governance_json TEXT NOT NULL,
    created_at TEXT NOT NULL)''')
   self.log(db,None,'integration_started',f'classifier={self.classifier_metadata["version"]}; mode={self.integration_mode}; clinical_review=pending')
   db.execute('''CREATE TABLE IF NOT EXISTS service_decisions (
    event_id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,scope_version TEXT NOT NULL,
    decision_json TEXT NOT NULL,retrieval_json TEXT NOT NULL,knowledge_hash TEXT NOT NULL,
    final_state TEXT,reply_source TEXT,created_at TEXT NOT NULL)''')
   db.execute('''CREATE TABLE IF NOT EXISTS service_requests (
    event_id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,case_id INTEGER NOT NULL,
    need_json TEXT NOT NULL,sources_json TEXT NOT NULL,knowledge_hash TEXT NOT NULL,created_at TEXT NOT NULL)''')
   db.execute('''CREATE TABLE IF NOT EXISTS service_followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,case_id INTEGER NOT NULL,conversation_id TEXT NOT NULL,
    status TEXT NOT NULL,recipient TEXT NOT NULL,note TEXT NOT NULL,operator TEXT NOT NULL,created_at TEXT NOT NULL)''')

 def record_classification(self,db,participant,event_id,result,plan):
  db.execute('INSERT INTO classification_records VALUES(?,?,?,?,?,?,?)',
    (event_id,participant,self.classifier_metadata['version'],json.dumps(self.classifier_metadata['sha256']),
     json.dumps(asdict(result),ensure_ascii=False),json.dumps(asdict(plan),ensure_ascii=False),now()))

 def manual_requested(self,text,result):
  return super().manual_requested(text,result) or 'M12-REQUEST' in result.matched_rules

 def choose_reply(self,participant,text,event_id,result,plan,state,answer,source):
  scope=assess_service_scope(text,result).to_dict()
  entry_sources=[]
  if result.risk=='高' and state=='human_active' and answer:
   answer=answer.replace('目前尚未確認有人受理。','目前由院內工作人員接手。')
  # Never route around current high risk, an explicit human request, or an open
  # human case. Entry information is fixed curated text, never a model output.
  if result.risk=='低' and state=='automatic' and scope['allow_entry_information'] and scope['route'] in {'medical','coordination','content_pending'}:
   need=scope['need'];entry_sources=self.knowledge.retrieve(text)
   origin={'medical':'medical_referral','coordination':'service_coordination','content_pending':'content_pending'}[scope['route']]
   answer,source,state=self.open_service_request(participant,event_id,need,entry_sources,origin)
  else:
   answer,source,state=super().choose_reply(participant,text,event_id,result,plan,state,answer,source)
   if result.risk=='低' and source=='no_source_notice' and any(r in result.matched_rules for r in ('L12-RESOURCE','L12-SUPPORT')):
    need=dict(key='uncovered',label='資料待補與需求整理',route='content_pending',
              intro='目前資料還沒有涵蓋你提出的照顧需求，已列入人工待辦。',question='最希望先獲得哪一項協助？',sources=[])
    answer,source,state=self.open_service_request(participant,event_id,need,[],'content_pending')
   elif source=='scope_notice':
    answer='這則訊息還有需要確認的健康或個別處理內容，已列入院內工作人員的待辦，目前尚未接手。系統不會據此提供醫療處置或核定個人資格；本帳號不保證即時有人回覆。'
   elif source=='review_notice':
    with self.db() as db:
     case=db.execute("SELECT * FROM cases WHERE conversation_id=? AND status!='closed'",(participant,)).fetchone()
    if case and case['origin'] in {'service_coordination','medical_referral','content_pending'}:
     answer='補充需求已記錄，仍在等待院內工作人員接手。尚未替你聯絡外部單位；可先使用前面提供的洽詢入口。'
  if source=='generation_notice' and self.integration_mode=='offline':
   answer=('訊息已列入人工確認清單，目前尚不代表已有人接手。正在建立離線測試草稿，供操作人員審閱。'
           if state=='awaiting_review' else '正在建立離線測試回覆，完成後會顯示在本機對話中。')
  retrieval=self.knowledge.explain(text) if source=='generation_notice' or entry_sources else []
  with self.db() as db:
   db.execute('INSERT INTO service_decisions VALUES(?,?,?,?,?,?,?,?,?)',
    (event_id,participant,SCOPE_VERSION,json.dumps(scope,ensure_ascii=False),json.dumps(retrieval,ensure_ascii=False),
     self.knowledge.sha256,state,source,now()))
  return answer,source,state

 def open_service_request(self,participant,event_id,need,sources,origin):
  with self.db() as db:
   case=self._open_case(db,participant,'低',origin)
   db.execute('INSERT INTO service_requests VALUES(?,?,?,?,?,?,?)',
    (event_id,participant,case['id'],json.dumps(need,ensure_ascii=False),json.dumps(sources,ensure_ascii=False),self.knowledge.sha256,now()))
   self.log(db,participant,'service_help_requested',f'event={event_id}; need={need["key"]}; origin={origin}; external_contact=not_contacted')
  notice='已列入院內工作人員的待辦，目前尚未接手，也尚未替你聯絡外部單位。本帳號不保證即時有人回覆。'
  answer=need['intro']+'\n\n'+notice
  if sources:
   answer+='\n\n可先洽詢的資料：\n'+'\n\n'.join(s['summary']+'\n'+s['url'] for s in sources)
  answer+='\n\n'+need['question']
  return answer,origin+'_notice',self.operating_state(case)

 def record_service_followup(self,case_id,status,recipient,note):
  if status not in {'not_contacted','contacted','confirmed','unavailable'}:
   raise ValueError('服務聯繫狀態無效。')
  if not recipient.strip() or not note.strip():
   raise ValueError('請填寫聯繫對象與紀錄。')
  with self.lock,self.db() as db:
   case=db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
   if not case or case['status']!='claimed':raise ValueError('請先接手事件，再記錄服務聯繫。')
   db.execute('INSERT INTO service_followups(case_id,conversation_id,status,recipient,note,operator,created_at) VALUES(?,?,?,?,?,?,?)',
    (case_id,case['conversation_id'],status,recipient.strip(),note.strip(),case['operator'],now()))
   self.log(db,case['conversation_id'],'service_followup_recorded',f'case={case_id}; status={status}; operator_record_only=true')

 def should_review_low(self,text,result):
  return not assess_service_scope(text,result).allow_automatic

 @staticmethod
 def pending_age(case):
  if case and case['status']=='pending':
   case['wait_seconds']=max(0,int((datetime.now(timezone.utc)-datetime.fromisoformat(case['created_at'])).total_seconds()))
   case['accepted']=False
  elif case:case['accepted']=case['status']=='claimed'

 def overview(self):
  out=super().overview()
  for case in out['cases']:self.pending_age(case)
  out.update(integration_mode='offline',classifier=self.classifier_metadata,clinical_review='pending',
             reply_provider='離線替代服務（固定測試輸出）',external_services_enabled=False,
             scope_version=SCOPE_VERSION,retrieval_version=RETRIEVAL_VERSION)
  return out

 def detail(self,participant):
  out=super().detail(participant);self.pending_age(out['case'])
  with self.db() as db:
   out['classification_records']=[dict(r) for r in db.execute('SELECT * FROM classification_records WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100',(participant,))]
   out['service_decisions']=[dict(r) for r in db.execute('SELECT * FROM service_decisions WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100',(participant,))]
   out['service_requests']=[dict(r) for r in db.execute('SELECT * FROM service_requests WHERE conversation_id=? ORDER BY rowid DESC LIMIT 100',(participant,))]
   out['service_followups']=[dict(r) for r in db.execute('SELECT * FROM service_followups WHERE conversation_id=? ORDER BY id DESC LIMIT 100',(participant,))]
  return out
