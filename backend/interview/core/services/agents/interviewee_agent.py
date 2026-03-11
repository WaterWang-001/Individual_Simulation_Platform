from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Tuple

from ...schemas.common import ModelConfig
from ...services.llm_service import call_llm_with_retry
from ...utils.prompts import load_prompt, render_prompt
from .interviewer_agent import conversation_to_text


class IntervieweeAgent:
    def __init__(self, model_cfg: ModelConfig, persona: Dict[str, Any], scenario_plan: Dict[int, Dict[str, str]], event_trigger_prob: float = 0.25, no_event_mode: bool = False):
        self.model_cfg = model_cfg
        self.persona = persona
        self.scenario_plan = scenario_plan
        self.prompt = load_prompt("interviewee_response_prompt.txt")
        self.attempts: Dict[int, int] = {}
        self.event_trigger_prob = event_trigger_prob
        self.no_event_mode = no_event_mode

    def _event_for_attempt(self, qid: int) -> Dict[str, str]:
        event = self.scenario_plan.get(qid, {
            "event_type": "none",
            "event_description": "无异常",
            "event_emotion": "平静",
            "event_intensity": "轻微",
            "event_expression": "直接表达",
        })
        if self.no_event_mode or random.random() > self.event_trigger_prob:
            return {
                "event_type": "none",
                "event_description": "无异常",
                "event_emotion": "平静",
                "event_intensity": "轻微",
                "event_expression": "直接表达",
            }
        attempt = self.attempts.get(qid, 0)
        if event["event_type"] in ["topic_derailment", "question_misunderstanding", "memory_failure", "topic_refusal", "passive_noncooperation"] and attempt >= 1:
            return {
                "event_type": "none",
                "event_description": "无异常",
                "event_emotion": "平静",
                "event_intensity": "轻微",
                "event_expression": "直接表达",
            }
        return event

    def respond(self, qid: int, interviewer_utterance: str, history: List[Dict[str, str]]) -> Tuple[str, Dict[str, Any]]:
        self.attempts[qid] = self.attempts.get(qid, 0) + 1
        event = self._event_for_attempt(qid)
        persona_facts = self.persona.get("persona_facts", [])
        if not isinstance(persona_facts, list):
            persona_facts = [str(persona_facts)]
        prompt = render_prompt(
            self.prompt,
            persona_profile=self.persona.get("persona_profile", ""),
            persona_facts="\n".join(str(x) for x in persona_facts),
            persona_answer_memory=json.dumps(self.persona.get("answer_memory", {}), ensure_ascii=False),
            conversation_history=conversation_to_text(history),
            event_type=event.get("event_type"),
            event_description=event.get("event_description"),
            event_emotion=event.get("event_emotion"),
            event_intensity=event.get("event_intensity"),
            event_expression=event.get("event_expression"),
            interviewer_utterance=interviewer_utterance,
        )
        messages = [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}]
        text = call_llm_with_retry(self.model_cfg, messages, max_retries=3)
        return (text or "嗯，我先想一下。"), event
