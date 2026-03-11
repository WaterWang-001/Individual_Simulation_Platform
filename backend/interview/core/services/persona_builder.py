from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from ..schemas.common import ModelConfig
from ..services.llm_service import call_llm
from ..utils.json_tools import extract_json
from ..utils.prompts import load_prompt, render_prompt


BASE_DIR = Path(__file__).resolve().parents[2]


class PersonaBuilder:
    @staticmethod
    def load_persona_examples() -> str:
        candidates = [
            (BASE_DIR / "prompt" / "用户画像示例.txt").resolve(),
            (BASE_DIR.parent / "prompt" / "用户画像示例.txt").resolve(),
        ]
        for sample_path in candidates:
            if sample_path.exists():
                return sample_path.read_text(encoding="utf-8").strip()
        return ""

    @staticmethod
    def _persona_has_required_fields(persona: Dict[str, Any]) -> bool:
        if not isinstance(persona, dict):
            return False
        if not isinstance(persona.get("persona_profile"), str):
            return False
        if not isinstance(persona.get("persona_facts"), list):
            return False
        if not isinstance(persona.get("persona_traits"), dict):
            return False
        big_five = persona.get("persona_traits", {}).get("big_five", {})
        keys = {"开放性", "尽责性", "外向性", "宜人性", "神经质"}
        return isinstance(big_five, dict) and keys.issubset(set(big_five.keys()))

    @staticmethod
    def build_fallback(ground_truth: Dict[int, Any]) -> Dict[str, Any]:
        facts = []
        for qid, answer in sorted(ground_truth.items()):
            if answer in [None, ""]:
                continue
            facts.append(f"Q{qid}: {answer}")
        return {
            "persona_profile": "受访者回答较具体，表达相对理性，愿意提供事实信息但在部分问题上会保留。",
            "persona_facts": facts[:20],
            "persona_traits": {
                "big_five": {dim: "中" for dim in ["开放性", "尽责性", "外向性", "宜人性", "神经质"]},
                "behavior_habits": ["倾向按自身节奏回应问题", "遇到敏感问题会先评估再回答", "习惯结合经历给出解释"],
                "language_habits": ["偏口语化", "会先给结论再补充理由", "在不确定时使用模糊表达"],
                "memorable_recent_events": [],
                "deep_impression_points": [],
            },
            "answer_memory": {str(k): v for k, v in ground_truth.items()},
        }

    @staticmethod
    def ensure_consistency(persona: Dict[str, Any], ground_truth: Dict[int, Any]) -> Dict[str, Any]:
        output = json.loads(json.dumps(persona, ensure_ascii=False))
        output.setdefault("persona_facts", [])
        output.setdefault("persona_traits", {})
        output.setdefault("answer_memory", {})
        for key, value in ground_truth.items():
            output["answer_memory"][str(key)] = value
        existing = "\n".join(str(x) for x in output["persona_facts"])
        for key, value in sorted(ground_truth.items()):
            if value in [None, ""]:
                continue
            token = f"Q{key}: {value}"
            if token not in existing:
                output["persona_facts"].append(token)
        output["persona_facts"] = output["persona_facts"][:40]
        traits = output["persona_traits"]
        traits.setdefault("big_five", {})
        for dim in ["开放性", "尽责性", "外向性", "宜人性", "神经质"]:
            traits["big_five"].setdefault(dim, "中")
        traits.setdefault("behavior_habits", [])
        traits.setdefault("language_habits", [])
        traits.setdefault("memorable_recent_events", [])
        traits.setdefault("deep_impression_points", [])
        return output

    @classmethod
    def generate_persona(cls, model_cfg: ModelConfig, ground_truth: Dict[int, Any]) -> Dict[str, Any]:
        prompt_tmpl = load_prompt("persona_from_answers_prompt.txt")
        examples = cls.load_persona_examples()
        prompt = render_prompt(
            prompt_tmpl,
            answers_json=json.dumps(ground_truth, ensure_ascii=False, indent=2),
            persona_examples=examples,
        )
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        persona = None
        last_error = None
        for _ in range(3):
            try:
                raw = call_llm(model_cfg, messages)
            except Exception as exc:
                last_error = exc
                break
            try:
                candidate = extract_json(raw)
                if cls._persona_has_required_fields(candidate):
                    persona = candidate
                    break
            except Exception:
                pass
            messages.append({"role": "user", "content": "请只输出严格JSON，并补齐所有必需字段。"})
        if persona is None:
            persona = cls.build_fallback(ground_truth)
            if last_error is not None:
                persona.setdefault("warnings", []).append(f"模型画像生成失败，已使用规则回退: {last_error}")
        return cls.ensure_consistency(persona, ground_truth)
