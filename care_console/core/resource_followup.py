"""Exact replies to a recent, recorded two-option resource menu only."""
import re
import unicodedata
from resource_query import PIPELINE_VERSION as BASE_PIPELINE_VERSION

VERSION = 'resource-followup-0.1.0'
PIPELINE_VERSION = BASE_PIPELINE_VERSION + '+' + VERSION
RULE = 'L15-RESOURCE-FOLLOWUP'
TTL_SECONDS = 600
MENU_QUESTION = '你想先了解哪一項？\n1. 長照服務有哪些\n2. 如何申請'
TOPICS = {
    'services': {'label': '長照服務類別', 'canonical': '想了解長照服務有哪些。',
                 'sources': ['LTC-SERVICES'], 'intro': '以下接續說明長照服務的類別。'},
    'apply': {'label': '長照申請方式', 'canonical': '想了解長照服務如何申請。',
              'sources': ['LTC-APPLY'], 'intro': '以下接續說明長照服務的申請入口與流程。'},
}
CHOICES = {
    'services': {'有哪些', '有什麼', '哪些', '服務有哪些', '有哪些服務', '服務', '服務項目',
                 '想了解服務', '第一個', '第一項', '1', '一'},
    'apply': {'如何申請', '怎麼申請', '要怎麼申請', '申請方式', '想申請', '我要申請',
              '第二個', '第二項', '2', '二'},
}


def choice_for(text):
    value = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text or ''))
    value = value.strip('?!！？。.,，')
    return next((key for key, choices in CHOICES.items() if value in choices), None)
