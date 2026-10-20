from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "risk_rules_v1_1_tw_frozen.json"

@dataclass
class RiskResult:
    risk: str
    hitl: str
    matched_rules: list[str]
    normalized_text: str
    sbp: Optional[int] = None
    dbp: Optional[int] = None
    rationale: str = ""

class RiskEngineV11TW:
    """Taiwan-centered operational governance risk engine.
    Not a diagnosis or clinical triage system.
    """

    def __init__(self, config_path: Path | str = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = json.load(f)
        self.bp_re = re.compile(self.cfg["bp"]["regex"])
        self.t = self.cfg["terms"]

    def normalize(self, text: str) -> str:
        text = unicodedata.normalize("NFKC", text or "")
        for src, dst in self.cfg["normalization_map"].items():
            text = text.replace(src, dst)
        text = re.sub(r"[\t\r\n]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_bp(self, text: str) -> tuple[Optional[int], Optional[int]]:
        m = self.bp_re.search(text)
        if not m:
            return None, None
        sbp, dbp = int(m.group(1)), int(m.group(2))
        if not (70 <= sbp <= 260 and 40 <= dbp <= 160):
            return None, None
        return sbp, dbp

    @staticmethod
    def _contains_any(text: str, terms: list[str]) -> bool:
        return any(term in text for term in terms)

    def _is_negated_at(self, text: str, start: int) -> bool:
        boundaries = [
            text.rfind("，", 0, start), text.rfind(",", 0, start),
            text.rfind("。", 0, start), text.rfind("！", 0, start),
            text.rfind("!", 0, start), text.rfind("？", 0, start),
            text.rfind("?", 0, start),
        ] + [text.rfind(c, 0, start) for c in self.t["contrasts"]]
        boundary = max(boundaries)
        window = text[boundary + 1:start][-8:]
        return any(neg in window for neg in self.t["negations"])

    def _asserted_term(self, text: str, term: str) -> bool:
        pos = 0
        while True:
            idx = text.find(term, pos)
            if idx < 0:
                return False
            if not self._is_negated_at(text, idx):
                return True
            pos = idx + max(1, len(term))

    def _asserted_any(self, text: str, terms: list[str]) -> bool:
        return any(self._asserted_term(text, term) for term in terms)

    def _chest_asserted(self, text: str) -> bool:
        if self._asserted_any(text, self.t["chest_words"]):
            return True
        for m in re.finditer(r"胸(?:口)?[^，。！？!?]{0,6}(?:痛|悶)", text):
            if not self._is_negated_at(text, m.start()):
                return True
        return False

    def _urgent_chest(self, text: str) -> bool:
        if not self._chest_asserted(text):
            return False
        return bool(re.search(r"(?:突然|忽然|剛剛突然)[^，。！？!?]{0,10}胸|胸(?:口)?[^，。！？!?]{0,8}(?:超痛|很痛|劇烈)", text))

    def _fast_face(self, text: str) -> bool:
        m = re.search(r"(?:臉|嘴|嘴角)[^，。！？!?]{0,5}(?:歪|不對稱)", text)
        return bool(m) and not self._is_negated_at(text, m.start())

    def _fast_arm(self, text: str) -> bool:
        patterns = [
            r"(?:單側|一邊|一隻)[^，。！？!?]{0,8}(?:手|手腳|肢體)[^，。！？!?]{0,6}(?:無力|沒力|下垂)",
            r"(?:手|手臂)[^，。！？!?]{0,6}(?:無力下垂|垂下)",
        ]
        return any(re.search(p, text) for p in patterns)

    def _fast_speech(self, text: str) -> bool:
        return bool(re.search(r"(?:說話|講話|口齒)[^，。！？!?]{0,10}(?:不清|不太清楚|不清楚|含糊)|大舌頭", text))

    def _is_info_query_without_asserted_symptom(self, text: str) -> bool:
        if not self._contains_any(text, self.t["info_markers"]):
            return False
        current_markers = ["我", "本人", "現在", "目前", "剛剛", "剛量", "今天", "最近"]
        if not self._contains_any(text, current_markers):
            return True
        asserted = (
            self._chest_asserted(text)
            or self._asserted_any(text, self.t["severe_dyspnea"])
            or self._asserted_any(text, self.t["mild_dyspnea"])
            or self._asserted_any(text, self.t["syncope"])
            or self._fast_face(text) or self._fast_arm(text) or self._fast_speech(text)
        )
        return not asserted

    def classify(self, raw_text: str) -> RiskResult:
        text = self.normalize(raw_text)
        sbp, dbp = self.extract_bp(text)

        if self._is_info_query_without_asserted_symptom(text) and sbp is None:
            return RiskResult("低", "人類監督", ["PRE-03", "L-03"], text, rationale="一般資訊/衛教語境，無當下正向症狀。")

        matched: list[str] = []
        if self._fast_face(text) or self._fast_arm(text) or self._fast_speech(text):
            matched.append("H-01")
        if self._asserted_any(text, self.t["severe_dyspnea"]):
            matched.append("H-03")
        if self._asserted_any(text, self.t["syncope"]):
            matched.append("H-04")
        if self._urgent_chest(text) or (self._chest_asserted(text) and self._asserted_any(text, self.t["severe_dyspnea"])):
            matched.append("H-02")

        if matched:
            return RiskResult("高", "人工接管", sorted(set(matched)), text, sbp, dbp, "符合國民健康署急症/FAST警訊之研究治理條件。")

        # Taiwan-centered BP rule: explicit BP >=130/80 is treated as medium governance risk.
        if sbp is not None and (sbp >= self.cfg["bp"]["medium_sbp"] or dbp >= self.cfg["bp"]["medium_dbp"]):
            rule = "M-01-G2" if (sbp >= self.cfg["bp"]["grade2_sbp"] or dbp >= self.cfg["bp"]["grade2_dbp"]) else "M-01-G1"
            return RiskResult("中", "人工介入", [rule], text, sbp, dbp, "達台灣高血壓指引之>=130/80門檻；本研究操作性映射為中風險。")

        if self._contains_any(text, self.t["medication"]):
            return RiskResult("中", "人工介入", ["M-04"], text, sbp, dbp, "涉及用藥或處置調整詢問。")
        if self._asserted_any(text, self.t["mild_dyspnea"]):
            return RiskResult("中", "人工介入", ["M-06"], text, sbp, dbp, "出現輕度/非急迫呼吸不適表達。")
        if self._chest_asserted(text):
            return RiskResult("中", "人工介入", ["M-07"], text, sbp, dbp, "胸部不適但未符合高風險急迫條件。")

        persistent = self._contains_any(text, self.t["persistent_modifiers"])
        general_symptom = self._asserted_any(text, self.t["general_symptoms"])
        if persistent and general_symptom:
            return RiskResult("中", "人工介入", ["M-03"], text, sbp, dbp, "持續或加劇之身體不適。")
        if self._asserted_any(text, self.t["nonspecific_discomfort"]):
            return RiskResult("中", "人工介入", ["M-05"], text, sbp, dbp, "健康不適資訊不足，採保守中風險。")

        rule = "L-04" if self._contains_any(text, self.t["negations"]) else "L-01/L-02"
        return RiskResult("低", "人類監督", [rule], text, sbp, dbp, "未符合高/中風險條件，維持研究範圍內低風險治理。")

def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("text", nargs="*")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    text = " ".join(args.text).strip()
    if not text:
        raise SystemExit("Please provide text")
    result = RiskEngineV11TW().classify(text)
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(f"risk={result.risk} hitl={result.hitl} rules={','.join(result.matched_rules)}")
        print(result.rationale)

if __name__ == "__main__":
    main()
