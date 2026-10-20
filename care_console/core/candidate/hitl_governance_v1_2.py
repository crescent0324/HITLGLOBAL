"""Development-only fall handover text; no notification or call is executed."""
from dataclasses import replace
from hitl_governance_v1 import HITLGovernanceV1

FALL_FIXED_MESSAGE = (
    '你描述的是目前跌倒或倒地的狀況，需要人員立即確認。一般自動回覆已停止，'
    '目前尚未確認有人受理。請先確認現場安全、長輩的意識、呼吸與傷勢，不要急著把長輩拉起來。'
    '若意識不清、呼吸異常、大量出血、無法起身，或可能傷到頭部、頸部、背部或髖部，'
    '請立即撥打119，依派遣員指示處理，不要等待聊天室或後台回覆。'
    '若無法確認長輩是否安全，請立即尋求現場協助，必要時撥打119說明情況。'
)


class HITLGovernanceV12(HITLGovernanceV1):
    def apply(self, risk_result):
        governed = super().apply(risk_result)
        if risk_result.risk == '高' and 'H12-FALL' in risk_result.matched_rules:
            return replace(governed, fixed_message=FALL_FIXED_MESSAGE,
                           required_actions=governed.required_actions + ['優先通知人員確認倒地事件', '記錄尚未受理狀態'])
        return governed
