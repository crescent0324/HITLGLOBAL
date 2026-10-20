"""Offline development candidate. Operational HITL routing, not clinical triage.

Only message text is accepted. No case IDs or reference labels are features.
See 修訂規格.md for provenance and limitations. Not used by the LINE application.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

VERSION = '1.2.3-dev.1'
ACTION = {'低': '人類監督', '中': '人工介入', '高': '人工接管'}
CURRENT = r'現在|目前|今天|昨天|剛才|剛剛|此刻|正在|這次|最近'
# Sudden events can occur in remote histories, e.g. "三年前突然跌倒".
REMOTE = r'多年[前]?|去年|前年|以前|曾經|過去|小時候|上次|(?:\d+|[零〇一二兩三四五六七八九十百]+)年前'
INFO = r'什麼是|是什麼意思|如何辨識|怎麼辨識|有哪些症狀|常見症狀|定義|請解釋|課程|衛教資料|如果|假設|萬一'
PERSON_CURRENT = r'(?:我|他|她|家人|長輩|爸爸|媽媽|爺爺|奶奶).{0,8}(?:現在|目前|今天|剛剛|正在)|(?:現在|目前|今天|剛剛|正在).{0,8}(?:我|他|她|家人|長輩)'
CLINICAL = r'藥|鼻胃管|胃造口|氣切|導尿管|呼吸器|血氧|氧氣|傷口|壓瘡|褥瘡|壓傷|灌食|吞嚥|進食|飲食|營養|蛋白|補品|復健|復能|移位|抬抱|走路|站立|關節|洗腎|腎臟|血糖|血壓|排便|便祕|便秘|清潔'
PROCEDURE = r'(?:怎麼|如何|多少|能不能|可不可以|要不要|是否|可以).{0,16}(?:吃|喝|餵|餵食|灌|拔|換|調|停|訓練|練習|活動|走|站|扶|抬|抱|移位|照顧|照護|清潔|清洗|處理|安排|增加|減少)|(?:劑量|流量|壓力|份量|餵食量|灌食量).{0,12}(?:多少|調|改|加|減)|(?:藥|管|氧氣).{0,16}(?:停掉|拔掉|自己調|自行調|改成)|(?:適合|合適|改成|要怎麼|該怎麼|怎麼做|怎麼安排|怎麼處理|怎麼選)'
RESOURCE = r'服務|資源|窗口|申請|喘息|替手|支持|社工|據點|接送|陪同就醫|照顧分工|照顧計畫|照顧人手|照顧者團體|互助|分擔|生活物資|無障礙|有誰|找誰|問誰|向誰|向哪|哪裡|哪個|有人.{0,6}(?:協助|幫忙)|有人能協助|醫療人員.{0,12}(?:到家|看診)|到家.{0,8}(?:醫療|看診|協助)|認識其他家屬'
RESOURCE_QUERY = r'(?:申請|詢問|聯絡|窗口|找誰|問誰|向誰|向哪|哪裡|找.{0,6}(?:資源|服務|替手|人手|專業人員))|(?:有沒有|有哪些|想了解|了解).{0,25}(?:服务|服務|資源|窗口|協助|支持)|(?:服務|資源).{0,15}(?:安排|搭配|詢問|整合)|(?:誰|人員).{0,15}(?:幫忙|協助|規劃|照顧)|到家.{0,8}(?:看診|幫忙)'


@dataclass
class Evidence:
    rule: str
    text: str
    start: int
    end: int
    status: str = 'asserted'


@dataclass
class RiskResult:
    risk: str
    hitl: str
    matched_rules: list[str]
    normalized_text: str
    sbp: int | None = None
    dbp: int | None = None
    rationale: str = ''
    version: str = VERSION
    review_required: bool = False
    evidence: list[Evidence] = field(default_factory=list)
    suppressed_evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Clause:
    text: str
    start: int
    historical: bool
    educational: bool


class RiskEngineV12TW:
    def normalize(self, text: str) -> str:
        text = unicodedata.normalize('NFKC', text or '')
        for old, new in {'发': '發', '意识': '意識', '没': '沒', '昏迷不醒': '昏迷', '愈來愈': '越來越'}.items():
            text = text.replace(old, new)
        return re.sub(r'\s+', ' ', text).strip()

    def _clauses(self, text: str) -> list[Clause]:
        historical = False
        educational = False
        clauses = []
        spans = []
        for m in re.finditer(r'[^,，。;；!?！？\n]+', text):
            starts = [0] + [t.start() for t in re.finditer(CURRENT, m.group())
                            if t.start() > 0 and re.search(REMOTE, m.group()[:t.start()])]
            ends = starts[1:] + [len(m.group())]
            spans.extend((m.start() + start, m.group()[start:end]) for start, end in zip(starts, ends))
        for offset, value in spans:
            # A new explicit present-time marker resets remote-history context.
            time_hits = list(re.finditer(f'{REMOTE}|{CURRENT}', value))
            if time_hits:
                historical = bool(re.fullmatch(REMOTE, time_hits[-1].group()))
            if re.search(INFO, value):
                educational = True
            if re.search(PERSON_CURRENT, value) and not re.search(r'假設|如果|萬一', value):
                educational = False
            if not re.search(INFO, value) and re.search(r'(?:家人|長輩|爸爸|媽媽|爺爺|奶奶|他|她).{0,6}(?:昏迷|臉|嘴唇|喘|呼吸|叫不(?:太)?醒|沒有呼吸|抽搐|口吐白沫)', value):
                educational = False
            clauses.append(Clause(value, offset, historical, educational))
        return clauses

    @staticmethod
    def _negated(clause: str, start: int) -> bool:
        left = clause[:start]
        left = re.split(r'但是|可是|不過|然而|但|卻', left)[-1]
        # Negation can cover coordinated symptom lists, but not unrelated clauses.
        direct = r'(?:沒有|並未|並無|未見|不會|不再|否認|不是|無)(?:出現|感到|發生|明顯|任何|持續|再)?(?:什麼)?$'
        if re.search(direct, left):
            return True
        return bool(re.search(r'(?:沒有|否認|並無|未見)(?:胸痛|胸悶|頭暈|昏迷|呼吸困難)(?:(?:或|與|和|及|、)(?:胸痛|胸悶|頭暈|昏迷|呼吸困難))*(?:或|與|和|及|、)$', left))

    def classify(self, message: str) -> RiskResult:
        if not isinstance(message, str):
            raise TypeError('message must be a string')
        text = self.normalize(message)
        clauses = self._clauses(text)
        suppressed: list[Evidence] = []

        def hits(pattern: str, rule: str, historical_ok: bool = False) -> list[Evidence]:
            out = []
            for c in clauses:
                for m in re.finditer(pattern, c.text, re.I):
                    status = 'asserted'
                    intrinsic_alarm = re.fullmatch(r'沒有生命跡象|無生命跡象|沒有呼吸|無呼吸|沒有反應|無反應|沒有回應|無回應', m.group())
                    internal_denial = re.search(r'沒有|並未|並無|未見|不會|不是', m.group()) and not intrinsic_alarm
                    if self._negated(c.text, m.start()) or internal_denial:
                        status = 'negated'
                    elif c.educational:
                        status = 'educational'
                    elif c.historical and not historical_ok:
                        status = 'historical'
                    e = Evidence(rule, m.group(), c.start + m.start(), c.start + m.end(), status)
                    if status == 'asserted':
                        out.append(e)
                    elif e not in suppressed:
                        suppressed.append(e)
            return out

        def result(risk: str, rule: str, reason: str, evidence: list[Evidence] | None = None,
                   pressure: tuple[int, int] | None = None) -> RiskResult:
            return RiskResult(risk, ACTION[risk], [rule], text, rationale=reason,
                              sbp=pressure[0] if pressure else None, dbp=pressure[1] if pressure else None,
                              review_required=risk != '低', evidence=evidence or [],
                              suppressed_evidence=suppressed.copy())

        high_patterns = [
            ('H12-CONSCIOUS', r'昏迷|叫不(?:太)?醒|喚不(?:太)?醒|很難叫醒|失去意識|意識不清|沒有生命跡象|無生命跡象|沒有呼吸|無呼吸|沒有反應|無反應|意識(?:狀態)?(?:變了|改變)|突然.{0,6}(?:混亂|搞不清楚)', '意識或生命徵象警訊，停止一般生成並交人工接管。'),
            ('H12-FAST', r'(?:臉|嘴角).{0,6}(?:歪|不對稱)|(?:說話|講話|口齒).{0,6}(?:不清|含糊|說不出)|(?:單側|一側|一邊|半邊|左半邊|右半邊|[左右](?:邊)?半身).{0,8}(?:無力|沒力|抬不起|麻木|動不了|不能動|無法動)|(?:左手|右手|左腳|右腳).{0,4}(?:突然沒力|突然無力|抬不起)', '疑似 FAST 警訊；剛發生而短暫緩解不取消緊急處理。'),
            ('H12-BREATH', r'喘不過氣|呼吸困難|吸不到氣|不能呼吸|無法呼吸|喘不過來|(?:嘴唇|唇色|臉色|臉|皮膚).{0,6}(?:發青|發紫|變紫|發黑|變黑)', '呼吸或膚色危險敘述，需緊急確認。'),
        ]
        for rule, pattern, reason in high_patterns:
            found = hits(pattern, rule)
            if found:
                return result('高', rule, reason, found)

        def clause_for(e: Evidence) -> Clause:
            return next(c for c in clauses if c.start <= e.start < c.start + len(c.text))

        seizure = hits(r'(?:全身|身體|四肢|手腳|眼皮|眼角|手指|小腿|腳趾)?抽搐', 'H13-SEIZURE')
        generalized, focal = [], []
        for e in seizure:
            left = clause_for(e).text[:e.start-clause_for(e).start]
            (focal if re.search(r'眼皮|眼角|手指|小腿|腳趾', left[-6:]+e.text) else generalized).append(e)
        if generalized:
            return result('高', 'H13-SEIZURE', '目前疑似抽搐事件先停止生成並交人員確認；此為研究接管政策，不據此診斷癲癇。', generalized)
        foam = hits(r'口吐白沫|嘴巴(?:吐出|吐著)白沫|吐白沫', 'H13-ACUTE-POSTURE')
        posture = hits(r'頭(?:部)?.{0,4}(?:垂下|垂了下)|(?:突然|剛剛).{0,5}癱軟', 'H13-ACUTE-POSTURE')
        for a in foam:
            for b in posture:
                lo, hi = sorted([a.start, b.start])
                if hi-lo <= 100 and not re.search(r'[。!?！？]', text[lo:hi]):
                    return result('高', 'H13-ACUTE-POSTURE', '姿態突變合併口吐白沫的敘述，先交人員立即確認，不自行推測病因。', [a,b])

        ambiguous_response = []
        for e in hits(r'沒有回應|無回應', 'M13-RESPONSE'):
            c = clause_for(e)
            if re.search(r'電話|訊息|LINE|客服|系統|機器人', c.text, re.I):
                suppressed.append(Evidence(e.rule,e.text,e.start,e.end,'communication_context'))
                continue
            left = c.text[:e.start-c.start]
            if re.search(r'呼喚|呼叫|怎麼叫|叫了|叫他|叫她|拍他|拍她', left):
                return result('高', 'H13-RESPONSE', '呼喚或拍觸後沒有回應，先停止生成並交人工接管。', [e])
            ambiguous_response.append(e)

        chest = hits(r'胸(?:口|部)?.{0,4}(?:痛|悶)', 'H12-CHEST')
        severe = hits(r'冒冷汗|冷汗|很喘|喘得|喘不|很厲害|劇烈|超痛|很痛|痛得受不了', 'H12-CHEST')
        if chest and severe:
            return result('高', 'H12-CHEST', '胸部不適合併嚴重程度或伴隨警訊。', chest + severe)

        airway = hits(r'氣切|氣管內管|呼吸道', 'H12-AIRWAY')
        obstruction = hits(r'卡住|阻塞|堵住|緊急狀況', 'H12-AIRWAY')
        bleeding = hits(r'出血|緊急狀況', 'H12-AIRWAY')
        if airway and obstruction and bleeding:
            return result('高', 'H12-AIRWAY', '氣道／管路異常伴隨出血或緊急敘述。', airway + obstruction + bleeding)

        trauma = hits(r'跌倒|摔倒|摔傷|撞傷|受傷', 'H12-TRAUMA')
        deformity = hits(r'變形|形狀(?:也|看起來|已經)?(?:不太對|不對|異常)|歪掉|不正常角度', 'H12-TRAUMA')
        if trauma and deformity:
            return result('高', 'H12-TRAUMA', '受傷後變形；未喊痛不構成排除條件。', trauma + deformity)

        oxygen = hits(r'(?:血氧(?:飽和度)?|SpO2)(?:值|讀數)?\s*(?:是|為|只有|降到|降至|量到|量起來|大約|約|:|=|量到只有|量到是)?\s*(\d+(?:\.\d+)?)\s*%?', 'H12-OXYGEN')
        target_match = re.search(r'(?:目標|醫囑範圍)(?:血氧)?\s*(\d{2,3})\s*%?\s*(?:到|至|[-~–])\s*(\d{2,3})', text)
        baseline_match = re.search(r'平常血氧(?:是|為|約)?\s*(\d{2,3})', text)
        target_range = None
        if target_match:
            lo, hi = map(int, target_match.groups())
            if 1 <= lo <= hi <= 100:
                target_range = (lo, hi)
        elif baseline_match:
            value = int(baseline_match.group(1))
            if 1 <= value <= 100:
                target_range = (value, value)
        numeric_review = []
        pressures = []
        for e in hits(r'(?:血壓|BP)\s*(?:是|為|大約|約|只有|量到|降到|降至|:|=)?\s*\d{2,3}\s*/\s*\d{2,3}(?![\d.])', 'H13-BP-COMBINED'):
            c = clause_for(e)
            left = c.text[:e.start-c.start]
            if re.search(r'平常|平時|一向|通常|基準', left) and not re.search(CURRENT,left):
                suppressed.append(Evidence(e.rule,e.text,e.start,e.end,'baseline'))
                continue
            sbp, dbp = map(int,re.search(r'(\d+)\s*/\s*(\d+)$',e.text).groups())
            if not (0 < dbp < sbp <= 300):
                numeric_review.append(e)
            else:
                pressures.append((e,sbp,dbp))
        somnolence = hits(r'嗜睡|一直睡|睡不停|睡個不停', 'H13-BP-COMBINED')
        deterioration = hits(r'變虛弱|明顯虛弱|全身無力|冒冷汗', 'H13-BP-COMBINED')
        for e,sbp,dbp in pressures:
            if sbp < 90 and dbp < 60 and somnolence and deterioration:
                return result('高', 'H13-BP-COMBINED', '低血壓讀數合併嗜睡與虛弱等敘述，依研究保守政策交人工接管；量測與判準仍需專業確認。', [e]+somnolence+deterioration, (sbp,dbp))
        for e in oxygen:
            value = float(re.search(r'(\d+(?:\.\d+)?)\s*%?$', e.text).group(1))
            if not (1 <= value <= 100):
                numeric_review.append(e)
            elif value <= 88 and not (target_range and target_range[0] <= value <= target_range[1]):
                return result('高', 'H12-OXYGEN', '目前血氧讀數達本研究緊急提示門檻；讀數仍需確認。', [e])
            elif value <= 92 or target_range:
                numeric_review.append(e)
        # A present fall/collapse can require handover without a diagnosis or
        # an explicit statement of unconsciousness. Exclude histories, risk,
        # prevention, hypothetical and negated statements at the match scope.
        fall_events = hits(r'跌倒|摔倒|滑倒|跌落|倒在(?:地上|地板上|洗手間|廁所|浴室|房間|走廊)|倒地', 'H12-FALL')
        current_falls = []
        for e in fall_events:
            c = next(c for c in clauses if c.start <= e.start < c.start + len(c.text))
            local_start = e.start - c.start
            left = re.split(r'但是|可是|不過|然而|但|卻', c.text[:local_start])[-1]
            right = c.text[local_start + len(e.text):]
            recent = bool(re.search(r'現在|今天|昨天|剛才|剛剛|此刻|正在|這次|突然', left))
            excluded = None
            if re.search(r'沒有|並未|並無|未見|不是', left[-4:]):
                excluded = 'negated'
            elif re.search(r'怕|擔心|避免|預防|防止|減少|降低|容易|可能|差點|差一點|以免', left[-10:]):
                excluded = 'risk_or_prevention'
            elif re.search(r'如果|萬一|假設', left):
                excluded = 'hypothetical'
            elif not recent and re.search(r'之前|曾經|曾|前陣子|上個月|上週|以前|病史', left):
                excluded = 'historical'
            elif not recent and re.search(r'常常|時常|經常|反覆|多次|頻繁', left[-8:]):
                excluded = 'recurrent_history'
            elif not recent and re.match(r'過|(?:的)?(?:風險|紀錄|經驗|病史)|後.{0,8}(?:失能|臥床|復健|復能|出院|開刀|手術)', right):
                excluded = 'background_or_risk'
            if excluded:
                suppressed.append(Evidence(e.rule, e.text, e.start, e.end, excluded))
            else:
                current_falls.append(e)
        if current_falls:
            return result('高', 'H12-FALL', '目前跌倒／倒地事件先停止生成、立即交人工接管；未交代意識狀態不構成降級理由。', current_falls)

        if ambiguous_response:
            return result('中', 'M13-RESPONSE', '互動時沒有回應的原因及起始時間不明，先交人工確認，避免直接以一般資源詢問放行。', ambiguous_response)
        if focal or foam or posture:
            return result('中', 'M13-SYMPTOM', '有待確認的局部抽動、口吐白沫或姿態變化，需人工釐清。', focal+foam+posture)

        caregiver_pain = hits(r'腰痠背痛|腰酸背痛|腰背(?:痠痛|疼痛)|背部(?:痠痛|疼痛)', 'M13-SYMPTOM')
        if caregiver_pain:
            return result('中', 'M13-SYMPTOM', '持續疼痛或搬扶安全問題交人工判讀，不直接給個別動作處方。', caregiver_pain)

        if numeric_review:
            return result('中', 'M12-MEASUREMENT', '量測或個別目標需人工確認，不自行調整治療。', numeric_review)

        oxygen_unclear = hits(r'(?:血氧|SpO2).{0,6}(?:量不到|測不到|不準|錯誤|異常|偏低)', 'M12-MEASUREMENT')
        if oxygen_unclear:
            return result('中', 'M12-MEASUREMENT', '血氧量測無法確認，需人工釐清。', oxygen_unclear)

        if re.search(r'轉人工|找真人|人工客服|人工協助', text):
            return result('中', 'M12-REQUEST', '明確提出人工處理需求。')

        symptoms = hits(r'傷口|壓瘡|褥瘡|壓傷|發燒|感染|化膿|膿尿|漏尿|走失|遊走|遊蕩|躁動|幻覺|常常.{0,4}跌倒|反覆.{0,4}跌倒|走路不穩|頭暈|發麻|痠痛|疼痛|不舒服|不太舒服|胸悶|胸痛|胸口痛|有點喘|容易喘|痰.{0,4}咳不出|吃.{0,5}嗆|嗆咳|一直咳|反應.{0,3}變慢|食慾.{0,3}下降|睡不好|睡不著|失眠|便祕|便秘|倒在地上|倒地', 'M12-SYMPTOM')
        if symptoms:
            return result('中', 'M12-SYMPTOM', '有個別症狀或照護安全問題，需人工判讀。', symptoms)

        # Any explicit BP interpretation is a personal measurement question here.
        bp = hits(r'(?:血壓|收縮壓|舒張壓).{0,12}\d+', 'M12-MEASUREMENT')
        if bp:
            return result('中', 'M12-MEASUREMENT', '個別血壓數值或變化須人工判讀。', bp)

        active_clinical = hits(CLINICAL, 'M12-CARE', historical_ok=True)
        questions = re.split(r'[。!?！？]', text)
        question = next((q for q in reversed(questions) if q.strip()), text)
        explicit_procedure = bool(re.search(PROCEDURE, question))
        resource_query = bool(re.search(RESOURCE_QUERY, question))
        if active_clinical and explicit_procedure and not resource_query:
            return result('中', 'M12-CARE', '詢問個別照護處置或調整，需人工確認。', active_clinical)

        # Educational text is low only if no separate asserted clinical concern exists.
        if clauses and all(c.educational for c in clauses):
            return result('低', 'L12-INFO', '一般知識／假設詢問，未辨識到另行陳述的目前警訊。')
        if re.search(r'(?:如何|怎麼|想了解).{0,5}(?:預防跌倒|防跌)|防跌.{0,5}(?:課程|資訊|方法)', text):
            return result('低', 'L12-FALL-INFO', '一般防跌資訊，未命中目前事件或症狀。')
        if re.search(RESOURCE, text) or re.search(r'到宅(?:協助|服務|支援)', text):
            return result('低', 'L12-RESOURCE', '一般照顧資源、服務或支持資訊，未命中目前警訊。')
        if re.search(r'陪伴|互動|聊天|關懷|認識其他|分享壓力', text):
            return result('低', 'L12-SUPPORT', '一般陪伴與互動資訊，未命中個別處置或急症。')
        if re.fullmatch(r'(你好|您好|嗨|哈囉|謝謝|感謝|再見)[!！。 ]*', text):
            return result('低', 'L12-GREETING', '一般問候。')
        if suppressed and all(e.status == 'negated' for e in suppressed) and not re.search(r'怎麼|如何|該|要不要', text):
            return result('中', 'M12-NEGATED-ONLY', '只有否定症狀，仍需確認實際需求。')
        return result('中', 'M12-UNKNOWN', '資訊不足或未涵蓋的語句，保留人工釐清。')
