from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List


class GroundTruthBuilder:
    @staticmethod
    def questionnaire_to_ground_truth(questionnaire_with_answers: Dict[str, Any]) -> Dict[int, Any]:
        gt: Dict[int, Any] = {}
        for q in questionnaire_with_answers.get("questions", []):
            gt[int(q.get("id"))] = q.get("answer")
        return gt

    @staticmethod
    def strip_answers(questionnaire: Dict[str, Any]) -> Dict[str, Any]:
        out = json.loads(json.dumps(questionnaire, ensure_ascii=False))
        for q in out.get("questions", []):
            q.pop("answer", None)
        return out

    @staticmethod
    def normalize_choice(value: Any, options: List[str]) -> Any:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if normalized in ["男", "男性", "男生"]:
            normalized = "男性"
        if normalized in ["女", "女性", "女生"]:
            normalized = "女性"
        for opt in options:
            if opt in normalized:
                return opt
        for opt in options:
            if normalized in opt:
                return opt
        return None

    @staticmethod
    def merge_values(values: List[str]) -> str:
        values = [v for v in values if v]
        if not values:
            return ""
        return "；".join(values)

    @staticmethod
    def build_ground_truth(questionnaire: Dict[str, Any], raw_sample: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[int, Any]:
        field_map = mapping.get("field_map", {})
        ground_truth: Dict[int, Any] = {}
        for q in questionnaire.get("questions", []):
            qid = str(q["id"])
            fields = field_map.get(qid, [])
            collected = []
            for field_name in fields:
                value = raw_sample.get(field_name)
                if value is not None:
                    collected.append(value)
            if q.get("type") in ["single_choice", "Likert"]:
                ans_raw = collected[0] if collected else None
                opts = q.get("options") or q.get("scale") or []
                ground_truth[int(qid)] = GroundTruthBuilder.normalize_choice(ans_raw, opts)
            else:
                ground_truth[int(qid)] = GroundTruthBuilder.merge_values([str(v) for v in collected])
        return ground_truth

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"[\s\-_/，。！？；：、\(\)\[\]{}<>\"'“”‘’]+", "", text)
        stop = ["请", "选择", "填写", "你的", "您", "是否", "主要", "程度", "情况", "方面", "总体", "倾向"]
        for item in stop:
            text = text.replace(item, "")
        return text

    @staticmethod
    def infer_field_map(questionnaire: Dict[str, Any], sample: Dict[str, Any]) -> Dict[str, List[str]]:
        keys = list(sample.keys())
        norm_keys = {GroundTruthBuilder._normalize_text(k): k for k in keys}
        mapping: Dict[str, List[str]] = {}
        for q in questionnaire.get("questions", []):
            qid = str(q["id"])
            qtext = GroundTruthBuilder._normalize_text(q.get("question", ""))
            best_key = None
            best_score = 0.0
            for normalized_key, original in norm_keys.items():
                if not normalized_key:
                    continue
                if normalized_key in qtext or qtext in normalized_key:
                    best_key = original
                    best_score = 1.0
                    break
                score = SequenceMatcher(None, normalized_key, qtext).ratio()
                if score > best_score:
                    best_score = score
                    best_key = original
            mapping[qid] = [best_key] if best_key and best_score >= 0.4 else []
        return mapping
