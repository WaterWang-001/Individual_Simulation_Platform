from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional


class Scorer:
    def __init__(self, text_threshold: float = 0.7):
        self.text_threshold = text_threshold

    def _normalize_compare_text(self, text: Optional[str]) -> str:
        if text is None:
            return ""
        return re.sub(r"\s+", "", str(text)).strip().lower()

    def _similarity(self, a: Optional[str], b: Optional[str]) -> float:
        if a is None or b is None:
            return 0.0
        a = self._normalize_compare_text(a)
        b = self._normalize_compare_text(b)
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    def _normalize_text(self, text: str) -> str:
        if text is None:
            return ""
        return self._normalize_compare_text(text)

    def _find_choice_index(self, value: Any, options: List[Any]) -> Optional[int]:
        normalized_value = self._normalize_compare_text(value)
        normalized_options = [self._normalize_compare_text(opt) for opt in options]
        if normalized_value in normalized_options:
            return normalized_options.index(normalized_value)
        return None

    def _char_ngrams(self, text: str, n: int = 2) -> List[str]:
        text = self._normalize_text(text)
        if len(text) < n:
            return list(text)
        return [text[i : i + n] for i in range(len(text) - n + 1)]

    def _tfidf_cosine(self, a: str, b: str) -> float:
        docs = [self._char_ngrams(a), self._char_ngrams(b)]
        if not docs[0] or not docs[1]:
            return 0.0
        vocab = list(set(docs[0]) | set(docs[1]))
        df = {term: sum(1 for doc in docs if term in doc) for term in vocab}

        def tfidf(doc: List[str]) -> List[float]:
            tf: Dict[str, int] = {}
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
            return [tf.get(term, 0) * (math.log((2 + 1) / (df[term] + 1)) + 1) for term in vocab]

        v1 = tfidf(docs[0])
        v2 = tfidf(docs[1])
        dot = sum(x * y for x, y in zip(v1, v2))
        n1 = math.sqrt(sum(x * x for x in v1))
        n2 = math.sqrt(sum(x * x for x in v2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def _rouge_l_f1(self, a: str, b: str) -> float:
        a = self._normalize_text(a)
        b = self._normalize_text(b)
        if not a or not b:
            return 0.0
        dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        for i in range(1, len(a) + 1):
            for j in range(1, len(b) + 1):
                if a[i - 1] == b[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        lcs = dp[-1][-1]
        if lcs == 0:
            return 0.0
        precision = lcs / len(a)
        recall = lcs / len(b)
        if precision + recall == 0:
            return 0.0
        return 2 * precision * recall / (precision + recall)

    def _keyword_jaccard(self, a: str, b: str, top_k: int = 20) -> float:
        a_tokens = self._char_ngrams(a)
        b_tokens = self._char_ngrams(b)
        if not a_tokens or not b_tokens:
            return 0.0
        set_a = set(t for t, _ in Counter(a_tokens).most_common(top_k))
        set_b = set(t for t, _ in Counter(b_tokens).most_common(top_k))
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    def score(self, questionnaire: Dict[str, Any], filled: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        qmap = {int(q["id"]): q for q in questionnaire.get("questions", [])}
        filled_map = {int(q["id"]): q.get("answer") for q in filled.get("questions", [])}
        total = 0
        score_sum = 0.0
        details = []
        by_type: Dict[str, Dict[str, Any]] = {}
        for qid, question in qmap.items():
            total += 1
            ground = ground_truth.get(str(qid)) if isinstance(ground_truth, dict) else ground_truth.get(qid)
            pred = filled_map.get(qid)
            qtype = question.get("type")
            if qtype == "Likert":
                scale = question.get("scale", [])
                scoring = question.get("scoring", list(range(len(scale), 0, -1)))
                pred_idx = self._find_choice_index(pred, scale)
                ground_idx = self._find_choice_index(ground, scale)
                if pred_idx is not None and ground_idx is not None:
                    p_score = scoring[pred_idx]
                    g_score = scoring[ground_idx]
                    max_diff = max(max(scoring) - min(scoring), 1) if scoring else 1
                    item_score = 1 - abs(p_score - g_score) / max_diff
                else:
                    item_score = self._similarity(pred, ground) * 0.5
            elif qtype == "single_choice":
                item_score = 1.0 if self._normalize_compare_text(pred) == self._normalize_compare_text(ground) else self._similarity(pred, ground) * 0.4
            else:
                rouge = self._rouge_l_f1(pred, ground)
                tfidf = self._tfidf_cosine(pred, ground)
                jaccard = self._keyword_jaccard(pred, ground)
                item_score = 0.4 * rouge + 0.4 * tfidf + 0.2 * jaccard
            score_sum += item_score
            details.append({"id": qid, "type": qtype, "ground_truth": ground, "pred": pred, "score": round(item_score, 4)})
            bucket = by_type.setdefault(qtype or "unknown", {"count": 0, "score_sum": 0.0})
            bucket["count"] += 1
            bucket["score_sum"] += item_score
        breakdown = {
            qtype: {
                "count": data["count"],
                "score_sum": round(data["score_sum"], 4),
                "avg_score": round(data["score_sum"] / data["count"], 4) if data["count"] else 0.0,
            }
            for qtype, data in by_type.items()
        }
        return {
            "total": total,
            "score": round(score_sum / total, 4) if total else 0.0,
            "details": details,
            "by_type": breakdown,
        }
