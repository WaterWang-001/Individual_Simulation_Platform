from __future__ import annotations

import json
from typing import Any, Dict

from ...schemas.common import ModelConfig
from ...utils.json_tools import request_json_with_retry, validate_questionnaire_summary_json
from ...utils.prompts import load_prompt, render_prompt


class QuestionnaireSummarizer:
    def __init__(self, model_cfg: ModelConfig):
        self.model_cfg = model_cfg
        self.prompt = load_prompt("questionnaire_summary_prompt.txt")

    def summarize(self, questionnaire: Dict[str, Any]) -> Dict[str, Any]:
        prompt = render_prompt(self.prompt, questionnaire_json=json.dumps(questionnaire, ensure_ascii=False))
        try:
            return request_json_with_retry(
                self.model_cfg,
                [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
                validate_questionnaire_summary_json,
                max_retries=3,
            )
        except Exception:
            return {
                "intro_text": "您好，我是本次访谈助手。我们将围绕问卷主题进行简短访谈，所有信息仅用于研究分析并匿名处理，您可随时停止。",
                "summary": {"purpose": "", "modules": [], "contains_sensitive": False, "estimated_time": "5-10 分钟"},
            }
