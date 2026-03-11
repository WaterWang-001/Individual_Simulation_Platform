from __future__ import annotations

import json
from typing import Any, Dict, List

from ...schemas.common import ModelConfig
from ...utils.json_tools import request_json_with_retry, validate_questionnaire_filled_json, validate_structured_answers_json
from ...utils.prompts import load_prompt, render_prompt
from .interviewer_agent import conversation_to_text


class QuestionnaireFiller:
    def __init__(self, model_cfg: ModelConfig, use_summary: bool = False):
        self.model_cfg = model_cfg
        self.prompt = load_prompt("questionnaire_fill_prompt.txt")
        self.structured_prompt = load_prompt("structured_answer_prompt.txt")
        self.use_summary = use_summary

    def _apply_answers(self, questionnaire: Dict[str, Any], answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        output = json.loads(json.dumps(questionnaire, ensure_ascii=False))
        ans_map = {int(answer.get("id")): answer.get("answer") for answer in answers}
        for question in output.get("questions", []):
            qid = int(question["id"])
            answer = ans_map.get(qid)
            qtype = question.get("type")
            if answer is None:
                question["answer"] = None
                continue
            if qtype == "single_choice":
                options = question.get("options", [])
                if answer in options:
                    question["answer"] = answer
                else:
                    match = next((opt for opt in options if str(opt) in str(answer) or str(answer) in str(opt)), None)
                    question["answer"] = match
            elif qtype == "Likert":
                scale = question.get("scale", [])
                if answer in scale:
                    question["answer"] = answer
                else:
                    match = next((opt for opt in scale if str(opt) in str(answer) or str(answer) in str(opt)), None)
                    question["answer"] = match
            else:
                question["answer"] = answer
        return output

    def fill(self, questionnaire: Dict[str, Any], history: List[Dict[str, str]]) -> Dict[str, Any]:
        if self.use_summary:
            prompt = render_prompt(self.structured_prompt, questionnaire_json=json.dumps(questionnaire, ensure_ascii=False), conversation_history=conversation_to_text(history))
            messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
            try:
                structured = request_json_with_retry(self.model_cfg, messages, validate_structured_answers_json, max_retries=3)
                return self._apply_answers(questionnaire, structured.get("answers", []))
            except Exception:
                pass
        prompt = render_prompt(self.prompt, questionnaire_json=json.dumps(questionnaire, ensure_ascii=False), conversation_history=conversation_to_text(history))
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        try:
            return request_json_with_retry(self.model_cfg, messages, validate_questionnaire_filled_json, max_retries=3)
        except Exception:
            output = json.loads(json.dumps(questionnaire, ensure_ascii=False))
            for question in output.get("questions", []):
                question["answer"] = None
            return output
