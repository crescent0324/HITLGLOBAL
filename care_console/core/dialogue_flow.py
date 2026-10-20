"""Bounded service dialogue grammar. No clinical inference or factual generation.

Every accepted request consumes the entire normalized message. Topic recognition
alone cannot erase symptoms, personal circumstances, or a request for a person.
"""
import re
import unicodedata
from resource_followup import PIPELINE_VERSION as PREVIOUS_PIPELINE, CHOICES

VERSION = 'service-dialogue-0.1.3'
CONTEXT_VERSIONS = {VERSION, 'service-dialogue-0.1.2', 'service-dialogue-0.1.1'}
PIPELINE_VERSION = PREVIOUS_PIPELINE + '+' + VERSION
RULE = 'L16-SERVICE-DIALOGUE'
TTL_SECONDS = 600
MENU = '你想先了解哪一項？\n1. 長照服務有哪些\n2. 如何申請'
CONTINUE = '可以接著詢問申請方式，或提出其他長照服務問題。'

# The identifiers point only to the existing curated corpus.
TOPICS = {
    'services': ('長照服務', ['LTC-SERVICES'], ['長照', '長照服務', '長照資訊', '長照資源', '長照服務類別']),
    'respite': ('喘息服務', ['LTC-RESPITE'], ['喘息服務', '喘息', '短期替手', '短期照顧']),
    'home': ('居家服務', ['LTC-HOME'], ['居家服務', '居服', '到宅協助', '到宅沐浴']),
    'daycare': ('日間照顧', ['LTC-DAYCARE'], ['日間照顧', '日照', '日照中心']),
    'transport': ('就醫交通接送', ['LTC-TRANSPORT'], ['交通接送', '就醫接送', '交通車', '就醫交通']),
    'escort': ('陪同就醫', ['LTC-ESCORT'], ['陪同就醫', '陪診']),
    'community_transport': ('社區服務交通接送', ['LTC-COMMUNITY-TRANSPORT'], ['日照接送', '社區接送', '據點接送']),
    'caregiver': ('照顧者支持', ['LTC-CAREGIVER'], ['照顧者支持', '家庭照顧者支持', '支持團體', '照顧支持']),
    'community': ('社區關懷', ['LTC-COMMUNITY'], ['社區關懷', '關懷訪視', '電話問安']),
    'professional': ('長照專業服務', ['LTC-PROFESSIONAL'], ['專業服務', '長照專業服務']),
    'foreigncare': ('外籍看護休假替代照顧', ['LTC-FOREIGNCARE'], ['外籍看護休假替代照顧', '替代照顧']),
    'alarm': ('緊急救援系統', ['LTC-ALARM'], ['緊急救援系統', '求救設備']),
    'institution': ('住宿機構補助', ['LTC-INSTITUTION'], ['住宿機構補助', '機構費用補助']),
}
NEED_TOPIC = {
    'respite': 'respite', 'daily': 'home', 'bathing': 'home', 'daycare': 'daycare',
    'escort': 'transport', 'community_transport': 'community_transport',
    'caregiver': 'caregiver', 'community': 'community', 'professional': 'professional',
    'foreign_respite': 'foreigncare', 'alarm': 'alarm',
}
ACK = {'謝謝', '謝謝你', '謝啦', '感謝', '好', '好的', '好喔', '好哦', '好啊', '嗯',
       '嗯嗯', '了解', '了解了', '知道了', '收到', '好謝謝', '好的謝謝', '不用了', '先這樣'}
RESET = {'回到選單', '主選單', '重新開始', '其他服務', '換個問題', '換個話題'}
GREETINGS = {'你好', '您好', '嗨', '哈囉', 'hello', 'hi'}
UNRESOLVED_CONCERN = re.compile(r'(?:狀況|情況|身體).{0,5}(?:怪怪|不對勁|異常)')
DETAIL = {'有哪些', '有什麼', '哪些', '內容', '服務內容', '詳細內容', '詳細一點', '介紹一下',
          '是什麼', '是做什麼的', '怎麼說', '這個呢', '這項呢', '這項服務呢', '還有呢'}
APPLY = {'如何申請', '怎麼申請', '要怎麼申請', '我要怎麼申請', '怎麼辦理', '去哪裡申請',
         '去哪申請', '找誰申請', '要找誰', '申請方式', '想申請', '我要申請', '申請流程'}
LIMITED = {
    'cost': {'費用', '費用多少', '要多少錢', '多少錢', '補助多少', '有補助嗎', '補助金額'},
    'eligibility': {'申請資格', '資格', '需要什麼資格', '誰可以申請', '我可以申請嗎', '我符合資格嗎'},
    'availability': {'可以馬上安排嗎', '多久能安排', '什麼時候有人', '有名額嗎'},
}
ACTION_LABELS = {'detail': '服務內容', 'apply': '申請方式', 'ack': '簡短回應', 'menu': '其他服務',
                 'clarify': '釐清主題', 'repeat': '重述資料', 'cost': '費用待確認',
                 'eligibility': '資格待確認', 'availability': '服務安排待確認'}


def normalize(text):
    value = unicodedata.normalize('NFKC', text or '')
    value = re.sub(r'\s+', '', value).strip('?!！？。.,，～~')
    return value.lower()


def strip_prefix(value):
    # These are discourse markers only, not arbitrary text preceding a keyword.
    return re.sub(r'^(?:那麼|那|另外|還有)?[,，]?(?:請問|我想了解|想了解|我想問|想問|我想知道|想知道|可以介紹|能介紹|介紹一下)?[,，]?', '', value, count=1)


def parse_request(text):
    value = normalize(text)
    if value in ACK or value in {'ok', 'ok謝謝'} or re.fullmatch(r'(?:好|好的)[,，](?:謝謝|感謝)(?:你)?', value):
        return dict(action='ack', topic=None, explicit=False)
    if value in RESET or value in GREETINGS:
        return dict(action='menu', topic='services', explicit=True)
    value = strip_prefix(value)
    if value in {'再說一次', '再講一次', '重複一次', '可以再說一次嗎', '可以說詳細一點嗎'}:
        return dict(action='repeat', topic=None, explicit=False)
    # Numbered choices are valid only against a recorded numbered menu.
    for action, choices in CHOICES.items():
        if value in choices and (value.isdigit() or value in {'一', '二', '第一個', '第一項', '第二個', '第二項'}):
            return dict(action='choice', choice=action, topic=None, explicit=False)
    aliases = sorted(((alias, key) for key, spec in TOPICS.items() for alias in spec[2]), key=lambda x: -len(x[0]))
    for alias, topic in aliases:
        # Consume the whole request. Do not infer application intent from a
        # keyword inside a symptom, personal eligibility, or mixed request.
        application_prefix = r'(?:(?:我|我們)?(?:想要|想|要|希望)?|如何|怎麼|要怎麼|該怎麼)(?:申請|辦理)'
        if re.fullmatch(application_prefix + re.escape(alias), value):
            return dict(action='apply', topic=topic, explicit=True)
        if not value.startswith(alias):
            continue
        suffix = value[len(alias):]
        if suffix.startswith('的'):
            suffix = suffix[1:]
        if suffix == '呢' and not re.search(r'介紹|了解|知道', normalize(text)):
            return dict(action='followup', topic=topic, explicit=True)
        if suffix in {'', '呢', '是什麼', '是什麼呢', '介紹', '介紹一下', '內容', '內容有哪些', '有什麼', '有哪些', '服務內容'}:
            return dict(action='detail', topic=topic, explicit=True)
        if suffix in APPLY:
            return dict(action='apply', topic=topic, explicit=True)
        for action, phrases in LIMITED.items():
            if suffix in phrases:
                return dict(action=action, topic=topic, explicit=True)
    if value in APPLY or value in CHOICES['apply']:
        return dict(action='apply', topic=None, explicit=False)
    if value in {'這個呢', '這項呢', '這項服務呢'}:
        return dict(action='followup', topic=None, explicit=False)
    if value in DETAIL or value in CHOICES['services']:
        return dict(action='detail', topic=None, explicit=False)
    for action, phrases in LIMITED.items():
        if value in phrases:
            return dict(action=action, topic=None, explicit=False)
    return None


def resolve(request, context):
    """Resolve only an unambiguous, verified immediately preceding topic."""
    if not request:
        return None
    out = dict(request)
    topic = out.get('topic')
    previous = context.get('topic') if context else None
    previous_focus = context.get('focus_action') if context else None
    inherited = out['action'] in {'followup', 'repeat'} and previous_focus == 'apply'
    if out['action'] == 'followup':
        out['action'] = 'apply' if inherited else 'detail'
    elif out['action'] == 'repeat' and inherited:
        out['action'] = 'apply'
    if out['action'] == 'choice':
        if context and context.get('numbered_menu'):
            topic = 'services'
            out['action'] = 'detail' if out['choice'] == 'services' else 'apply'
        else:
            out['action'] = 'clarify'
    elif out['action'] in {'ack', 'repeat', 'detail', 'apply', 'cost', 'eligibility', 'availability'}:
        topic = topic or previous
    if not topic and out['action'] == 'apply':
        topic = 'services'  # Explicit general application question has its own source.
    if not topic and out['action'] not in {'ack', 'menu'}:
        out['action'] = 'clarify'
    out['topic'] = topic
    out['context_used'] = bool(context and previous and (not request.get('explicit') or inherited))
    out['inherited_action'] = inherited
    out['focus_action'] = (out['action'] if out['action'] in {'detail', 'apply'} else
                           previous_focus if out['action'] == 'ack' else None)
    return out


def sources_for(decision):
    if decision['action'] in {'ack', 'clarify'}:
        return []
    if decision['action'] == 'apply':
        return ['LTC-APPLY']
    topic = decision.get('topic')
    if topic == 'daycare' and decision['action'] in {'detail', 'repeat'}:
        return ['LTC-DAYCARE', 'LTC-APPLY']
    return list(TOPICS[topic][1]) if topic in TOPICS else []


def topic_from_sources(sources, need=None):
    if need and need['key'] in NEED_TOPIC:
        return NEED_TOPIC[need['key']]
    informative = set(sources) - {'LTC-APPLY'}
    exact = [key for key, spec in TOPICS.items() if informative == set(spec[1])]
    return exact[0] if len(exact) == 1 else None


def prompt_for(topic):
    return MENU if topic == 'services' else CONTINUE
