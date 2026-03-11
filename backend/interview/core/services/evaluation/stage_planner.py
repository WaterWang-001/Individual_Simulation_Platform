from __future__ import annotations

from typing import Any, Dict, List


class StagePlanner:
    def __init__(self, questionnaire: Dict[str, Any]):
        self.questionnaire = questionnaire
        self.qmap = {int(q["id"]): q for q in questionnaire.get("questions", [])}
        self.stage_order = ["basic", "core", "attitude", "reflection", "closing"]
        self.stage_goals = {
            "basic": "快速建立背景与基本信息",
            "core": "覆盖核心事实与经历",
            "attitude": "了解态度/评价/倾向",
            "reflection": "引导反思与深层观点",
            "closing": "收尾与补充",
        }

    def _keywords_match(self, text: str, keywords: List[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def classify(self, question: Dict[str, Any]) -> str:
        text = question.get("question", "")
        qtype = question.get("type")
        basic_kw = ["年龄", "性别", "学历", "专业", "院校", "学校", "学院", "职位", "身份", "民族", "地区", "城市"]
        attitude_kw = ["满意", "看法", "态度", "评价", "认可", "支持", "契合", "是否同意", "倾向"]
        closing_kw = ["其他", "补充", "意见", "经历", "是否同意", "愿意"]
        reflection_kw = ["价值", "影响", "理念", "关联", "意义", "挑战", "困难"]
        if self._keywords_match(text, closing_kw):
            return "closing"
        if qtype == "Likert" or self._keywords_match(text, attitude_kw):
            return "attitude"
        if self._keywords_match(text, reflection_kw):
            return "reflection"
        if qtype == "single_choice" and self._keywords_match(text, basic_kw):
            return "basic"
        return "core"

    def plan(self, answered_ids: List[int], skipped_ids: List[int]) -> Dict[str, Any]:
        remaining = [qid for qid in self.qmap if qid not in answered_ids and qid not in skipped_ids]
        stage_candidates = {stage: [] for stage in self.stage_order}
        for qid in remaining:
            stage_candidates[self.classify(self.qmap[qid])].append(qid)
        stage_name = next((stage for stage in self.stage_order if stage_candidates[stage]), "closing")
        return {
            "stage_name": stage_name,
            "stage_goal": self.stage_goals.get(stage_name, ""),
            "stage_candidates": stage_candidates.get(stage_name, []),
        }
