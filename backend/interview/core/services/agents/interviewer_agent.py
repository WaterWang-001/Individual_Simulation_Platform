from __future__ import annotations

import json
from typing import Any, Dict, List

from ...schemas.common import ModelConfig
from ...services.llm_service import call_llm_with_retry
from ...utils.json_tools import request_json_with_retry, validate_action_json, validate_plan_json
from ...utils.prompts import load_prompt, render_prompt


def conversation_to_text(history: List[Dict[str, str]]) -> str:
    return "\n".join(f"{item.get('role', '')}: {item.get('content', '')}" for item in history)


class InterviewerAgent:
    def __init__(self, model_cfg: ModelConfig, handling_mode: str = "default"):
        self.model_cfg = model_cfg
        self.action_prompt = load_prompt("interviewer_action_prompt.txt")
        self.response_prompt = load_prompt("interviewer_response_prompt_alt.txt" if handling_mode == "alt" else "interviewer_response_prompt.txt")
        self.plan_prompt = load_prompt("interviewer_plan_prompt.txt")
        self.intro_prompt = load_prompt("interviewer_intro_prompt.txt")
        self.free_topic_prompt = load_prompt("free_topic_followup_prompt.txt")

    def decide_action(self, answered_ids: List[int], skipped_ids: List[int], remaining_ids: List[int], stage_name: str, stage_goal: str, stage_candidates: List[int], plan_used: int, plan_limit: int, max_turns: int, used_turns: int, history: List[Dict[str, str]]) -> Dict[str, Any]:
        prompt = render_prompt(
            self.action_prompt,
            answered_ids=answered_ids,
            skipped_ids=skipped_ids,
            remaining_ids=remaining_ids,
            stage_name=stage_name,
            stage_goal=stage_goal,
            stage_candidates=stage_candidates,
            plan_used=plan_used,
            plan_limit=plan_limit,
            max_turns=max_turns,
            used_turns=used_turns,
            conversation_history=conversation_to_text(history),
        )
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        try:
            return request_json_with_retry(self.model_cfg, messages, validate_action_json, max_retries=3)
        except Exception:
            return {"action": "ask_question", "target_question_id": None, "reason_tag": "normal", "note": "fallback"}

    def generate_response(self, action: str, reason_tag: str, current_question: Dict[str, Any], history: List[Dict[str, str]]) -> str:
        prompt = render_prompt(
            self.response_prompt,
            action=action,
            reason_tag=reason_tag,
            current_question=json.dumps(current_question, ensure_ascii=False),
            conversation_history=conversation_to_text(history),
        )
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        text = call_llm_with_retry(self.model_cfg, messages, max_retries=3)
        return text or "我想进一步了解一下这个问题。"

    def generate_plan(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        prompt = render_prompt(self.plan_prompt, conversation_history=conversation_to_text(history))
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        try:
            return request_json_with_retry(self.model_cfg, messages, validate_plan_json, max_retries=3)
        except Exception:
            return {"summary": "", "missing": [], "next_steps": []}

    def generate_intro(self, intro_text: str) -> str:
        prompt = render_prompt(self.intro_prompt, intro_text=intro_text)
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        text = call_llm_with_retry(self.model_cfg, messages, max_retries=3)
        return text or "您好，我是本次访谈助手。我们会围绕主题进行简短交流，您可随时停止。"

    def generate_free_followup(self, current_question: Dict[str, Any], history: List[Dict[str, str]]) -> str:
        prompt = render_prompt(
            self.free_topic_prompt,
            conversation_history=conversation_to_text(history),
            current_question=json.dumps(current_question, ensure_ascii=False),
        )
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        text = call_llm_with_retry(self.model_cfg, messages, max_retries=3)
        return text or "这个点我想再听听你的具体经历。"
