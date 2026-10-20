"""Versioned service-information gate; never changes the classifier risk label."""
import re
import unicodedata
from dataclasses import asdict, dataclass
from service_intents import identify_need

VERSION = 'service-information-scope-0.5.0'
HEALTH = re.compile(r'血壓|血糖|心跳|體溫|吃藥|服藥|用藥|停藥|調藥|劑量|症狀|不舒服|胸|痛|喘不|喘到|呼吸|暈|無力|沒有力|倒下|叫不|叫都|昏|流血|嘔吐|發燒|麻木|嘴歪|說話不|吞嚥|抽搐|受傷|跌倒|癱|中風|心臟病|癲癇|糖尿病|高血壓|低血壓|急救|治療|診斷|腫|出血|窒息|發紫|沒反應')
SERVICE = re.compile(r'服務|資源|申請|補助|費用|替手|喘息|到宅|到府|居家|支持|團體|社工|照管|1966|銜接|有人.{0,12}(?:到家|協助|幫忙)')
REQUEST = re.compile(r'嗎|\?|如何|怎麼|能不能|可不可以|哪|想了解|想找|希望|請問|申請|尋求|需要.{0,12}(?:服務|資源|支持|替手|協助)')
# Explicit medical or hands-on instructions remain outside automatic service Q&A,
# including when a resource phrase is appended at the end of the message.
PROCEDURE = re.compile(r'(?:怎麼|如何|要不要|能不能|可不可以|是否|可以|應該|請教|教我).{0,14}(?:調藥|停藥|吃藥|服藥|餵藥|加藥|拔管|灌食|餵食|移位|抬抱|換藥|判讀|診斷|治療|清洗傷口|洗傷口)|(?:劑量|流量|灌食量).{0,10}(?:多少|調|加|減)|(?:我|他|她|家人).{0,10}(?:適合|能領|符合).{0,12}(?:補助|資格)|(?:保證|確定).{0,8}(?:能領|符合|補助)')
DIAGNOSIS = r'中風|腦中風|高血壓|糖尿病|心臟病|癲癇'
YEARS = r'(?:\d+|[零〇一二兩三四五六七八九十百多]+)(?:多)?年'
BACKGROUND = re.compile(
    rf'(?:{DIAGNOSIS})(?:住院)?後|(?:{DIAGNOSIS})(?:已有|已經|已|有)?{YEARS}(?:前)?'
    rf'|(?:{YEARS}前|去年|前年|曾經|以前|過去).{{0,4}}(?:{DIAGNOSIS})'
    rf'|(?:{DIAGNOSIS})(?:病史)|(?:病史|既往病史).{{0,4}}(?:{DIAGNOSIS})')
# These forms describe a person or a persistent care background. A service need
# and the classifier's resource rule are both still required before masking.
CARE_BACKGROUND = re.compile(
    r'中風(?:的(?:先生|太太|家人|爸爸|媽媽|父親|母親|公公|婆婆)|臥床|又失智)'
    r'|失智又中風|(?:有|患有|罹患)心臟病'
    r'|(?:車禍|腦傷)後(?:半邊)?(?:癱瘓|全癱)|半邊癱瘓'
    r'|跌倒後失能臥床')
ACUTE_BACKGROUND = re.compile(r'現在|今天|剛剛|剛才|突然|新發|這次')
NEW_CONCERN = re.compile(r'(?:今天|剛剛|突然|現在|最近).{0,15}(?:講話|說話|反應|精神|走路|呼吸).{0,8}(?:怪|變|異常|不一樣)|(?:講話|說話|反應|精神|走路|呼吸).{0,8}(?:突然|變得|變成|不一樣)')


@dataclass
class ScopeDecision:
    version: str
    allow_automatic: bool
    reason: str
    matched_service_terms: list
    background_spans: list
    unresolved_health_terms: list
    route: str = 'general'
    need: dict | None = None
    allow_entry_information: bool = False

    def to_dict(self):
        return asdict(self)


def assess_service_scope(text, result):
    value = unicodedata.normalize('NFKC', text or '')
    need = identify_need(value)
    intent = list(dict.fromkeys(SERVICE.findall(value)))
    def decision(allow, reason, backgrounds=None, unresolved=None, route='general', entry=False):
        return ScopeDecision(VERSION, allow, reason, intent, backgrounds or [], unresolved or [],route,need,entry)
    if result.risk != '低':
        return decision(False, '風險分級與接管規則優先，不開放一般自動回覆。',route='risk')
    if PROCEDURE.search(value):
        return decision(False, '包含個別處置、醫療判讀或個人補助資格認定請求，交人工確認。')
    if NEW_CONCERN.search(value):
        return decision(False, '有近期功能或狀態變化，需人工確認，不因附帶服務詢問而放行。')
    if need and need['route'] in {'medical','coordination','content_pending'}:
        route=need['route']
        reasons={'medical':'需要醫療銜接；只提供洽詢入口，個別安排由醫療團隊確認。',
                 'coordination':'需要照顧安排協調；提供入口並建立人工待辦。',
                 'content_pending':'尚缺合適的陪伴或互動資料，建立人工待辦，不生成活動建議。'}
        return decision(False,reasons[route],unresolved=list(dict.fromkeys(HEALTH.findall(value))),
                        route=route,entry=True)
    remaining = value
    backgrounds = []
    service_request = bool(need or (intent and REQUEST.search(value)))
    # Background exceptions require the frozen classifier's resource decision too.
    if service_request and 'L12-RESOURCE' in result.matched_rules:
        chars = list(value)
        for match in list(BACKGROUND.finditer(value))+list(CARE_BACKGROUND.finditer(value)):
            left = re.split(r'[,，。;；!?！？\n]', value[:match.start()])[-1]
            if ACUTE_BACKGROUND.search(left):
                continue
            backgrounds.append({'text': match.group(), 'start': match.start(), 'end': match.end()})
            chars[match.start():match.end()] = ' ' * len(match.group())
        remaining = ''.join(chars)
    unresolved = list(dict.fromkeys(HEALTH.findall(remaining)))
    if unresolved:
        return decision(False, '仍有未排除的健康敘述，需人工確認；未改動原風險標籤。', backgrounds, unresolved)
    if service_request:
        return decision(True, '服務資源詢問；既往病況僅作背景，回答限已提供的服務資料。', backgrounds,entry=True)
    # Retain harmless/no-source menus, without treating keywords as clinical proof.
    return decision(True, '未命中個別健康處理限制，仍須通過資料涵蓋檢查。')
