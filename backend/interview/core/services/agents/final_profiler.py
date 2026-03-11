from __future__ import annotations

import json
from typing import Any, Dict, List

from ...schemas.common import ModelConfig
from ...utils.json_tools import request_json_with_retry, validate_final_profile_json
from ...utils.prompts import load_prompt, render_prompt
from .interviewer_agent import conversation_to_text


class FinalProfiler:
    def __init__(self, model_cfg: ModelConfig):
        self.model_cfg = model_cfg
        self.prompt = load_prompt("interview_final_summary_prompt.txt")

    def build(self, questionnaire: Dict[str, Any], filled: Dict[str, Any], history: List[Dict[str, str]]) -> Dict[str, Any]:
        prompt = render_prompt(
            self.prompt,
            questionnaire_json=json.dumps(questionnaire, ensure_ascii=False),
            filled_json=json.dumps(filled, ensure_ascii=False),
            conversation_history=conversation_to_text(history),
        )
        try:
            return request_json_with_retry(
                self.model_cfg,
                [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
                validate_final_profile_json,
                max_retries=3,
            )
        except Exception:
            return {
                "profile_summary": "",
                "questionnaire_traits": [],
                "general_personality_traits": [],
                "communication_style": [],
                "consistency_and_conflicts": [],
                "risk_signals": [],
                "insights": [],
                "next_interview_suggestions": [],
            }
