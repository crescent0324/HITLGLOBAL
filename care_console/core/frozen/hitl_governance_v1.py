from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

HIGH_FIXED_MESSAGE = (
    "你描述的狀況可能需要立即處理。系統已停止一般自動醫療性回覆。"
    "請立即尋求緊急醫療協助；若目前有嚴重胸痛、呼吸困難、意識異常、"
    "臉歪、單側手腳無力或說話不清等情況，請撥打119或請身旁的人協助就醫。"
)

MEDIUM_SAFETY_PREFIX = (
    "你提供的資訊需要進一步確認。系統將限制一般醫療性推論，"
    "不提供疾病診斷、藥物劑量調整或治療決策。"
)

@dataclass
class GovernanceResult:
    risk: str
    hitl_state: str
    response_mode: str
    allow_llm: bool
    llm_policy: str
    required_actions: list[str]
    user_message_prefix: str
    fixed_message: str = ""

class HITLGovernanceV1:
    """Deterministic governance mapping for the thesis prototype."""

    def apply(self, risk_result: Any) -> GovernanceResult:
        risk = risk_result.risk
        if risk == "低":
            return GovernanceResult(
                risk="低",
                hitl_state="人類監督",
                response_mode="GENERAL_GENERATIVE",
                allow_llm=True,
                llm_policy="僅限一般長照資訊、非急迫衛教與日常管理；不得診斷、調藥或提供治療決策。",
                required_actions=["保存對話紀錄", "保存風險判定", "保存AI回覆與時間"],
                user_message_prefix=""
            )
        if risk == "中":
            return GovernanceResult(
                risk="中",
                hitl_state="人工介入",
                response_mode="RESTRICTED_GENERATIVE",
                allow_llm=True,
                llm_policy="只可提供風險提示、一般性資訊或要求補充資訊；不得診斷、調整藥物或提供治療決策。",
                required_actions=["限制AI回覆權限", "加入風險提示", "標記人工確認狀態", "保存治理紀錄"],
                user_message_prefix=MEDIUM_SAFETY_PREFIX
            )
        return GovernanceResult(
            risk="高",
            hitl_state="人工接管",
            response_mode="FIXED_SAFETY",
            allow_llm=False,
            llm_policy="停止一般生成式AI醫療性推論。",
            required_actions=["停止一般LLM回覆", "顯示固定安全提示", "標記人工接管/轉介狀態", "保存事件紀錄"],
            user_message_prefix="",
            fixed_message=HIGH_FIXED_MESSAGE
        )
