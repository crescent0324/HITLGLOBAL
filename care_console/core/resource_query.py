"""Bounded resource-query extension; frozen risk rules run first.

Only a whole message matching the information-query grammar can replace the
unknown fallback. Extra clauses, personal conditions and context references do
not qualify. This is lexical coverage, not semantic or clinical validation.
"""
from dataclasses import replace
import re
import unicodedata
from candidate_runtime import RiskEngine

VERSION = 'resource-query-0.1.0'
PIPELINE_VERSION = '1.2.3-dev.1+' + VERSION
RULE = 'L14-GENERAL-RESOURCE'
SOURCE_IDS = ('LTC-SERVICES', 'LTC-APPLY')
SUBJECT = r'(?:長照|長期照顧)(?:的)?(?:相關)?(?:服務資訊|服務資料|服務項目|服務內容|資訊|資料|介紹|資源|服務)'
WHERE = r'(?:哪邊|哪裡|什麼地方|何處)'
PREFIX = r'(?:(?:你好|您好|哈囉)[,，]*)?(?:(?:請問|請教|想請問|我想問|想問一下)[,，]*)?'
SUFFIX = r'(?:嗎|呢|啊|呀|喔|哦)?[?？!！。.,，]*(?:謝謝[!！。.]*)?'
FORMS = (
    rf'{WHERE}(?:有|能|可以)?(?:找到|查到|查詢|看到|看|了解|瞭解)?{SUBJECT}(?:可以|能)?(?:看|查|查詢|參考|了解|瞭解)?',
    rf'{SUBJECT}(?:要|能|可以|該)?(?:去|在|到)?{WHERE}(?:找|看|查|查詢|了解|瞭解)(?:得到)?',
    rf'(?:我)?(?:想|想要|需要)(?:了解|瞭解|查詢|查|看看|看|找|知道)(?:一下)?{SUBJECT}',
    rf'(?:能不能|可不可以|可以|能|請)(?:給我|提供|介紹|說明)(?:一下|一些|一點)?{SUBJECT}(?:給我)?',
    rf'{SUBJECT}(?:有哪些|有什麼|是什麼|怎麼查|怎麼找|在哪邊(?:看|查)?|在哪裡(?:看|查)?)',
    SUBJECT,
)
QUERY = re.compile(PREFIX + '(?:' + '|'.join(FORMS) + ')' + SUFFIX)


def is_general_resource_query(text):
    value = re.sub(r'\s+', '', unicodedata.normalize('NFKC', text or ''))
    return bool(QUERY.fullmatch(value))


class ResourceQueryEngine(RiskEngine):
    def classify(self, message):
        base = super().classify(message)
        if base.risk == '中' and base.matched_rules == ['M12-UNKNOWN'] and is_general_resource_query(message):
            return replace(base, risk='低', hitl='人類監督', review_required=False,
                           matched_rules=[RULE], version=PIPELINE_VERSION,
                           rationale='整則訊息符合一般長照資訊查詢句型；回覆限既有服務資料，仍受未結案事件限制。')
        return base
