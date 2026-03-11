from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import APIConnectionError

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.schemas.common import ModelConfig
import server


def make_connection_error() -> APIConnectionError:
    return APIConnectionError(
        message="Connection error.",
        request=httpx.Request("POST", "https://example.com/v1/chat/completions"),
    )


class StubInterviewerAgent:
    def __init__(self, *_args, **_kwargs):
        pass

    def generate_response(self, _action, _reason_tag, current_question, _history):
        return str(current_question.get("question") or "请继续回答。")


class StubIntervieweeAgent:
    def __init__(self, *_args, **_kwargs):
        pass

    def respond(self, _qid, _interviewer_utterance, _history):
        return "这是一个离线回退测试回答。", {"event_type": "none"}


class RuntimeResilienceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.model_cfg = ModelConfig(
            name="mock-model",
            api_key="test-key",
            base_url="https://example.com/v1",
        )

    def _build_demo_inputs(self):
        survey = {
            "survey_name": "运行性回退测试",
            "questions": [
                {"id": 1, "question": "请介绍一下你的基本情况。", "type": "text_input"},
                {"id": 2, "question": "你对这个主题最在意什么？", "type": "text_input"},
            ],
        }
        task = server.create_interview_task(
            topic="离线回退测试",
            target_population="测试对象",
            research_goal="验证模型连接失败时主链路不会崩溃",
            survey=survey,
            sample_size=1,
        )["task"]
        persona = server.generate_candidate_personas(task=task)["personas"][0]
        plan = server.generate_interview_plan(task=task)["plan"]
        return task, persona, plan

    def test_build_persona_from_answers_falls_back_on_connection_error(self):
        with patch.object(server.TOOLKIT, "_try_load_project_model_config", return_value=(self.model_cfg, None)):
            with patch.object(server.TOOLKIT.PersonaBuilder, "generate_persona", side_effect=make_connection_error()):
                payload = server.build_persona_from_answers({"1": "已回答"})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["model_name"], "mock-model")
        self.assertIn("persona", payload)
        self.assertIn("warnings", payload["persona"])
        self.assertTrue(any("规则回退" in text for text in payload["persona"]["warnings"]))

    def test_run_single_interview_survives_connection_error(self):
        task, persona, plan = self._build_demo_inputs()
        with patch.object(server.TOOLKIT, "_try_load_project_model_config", return_value=(self.model_cfg, None)):
            with patch.object(server.TOOLKIT, "request_json_with_retry", side_effect=make_connection_error()):
                with patch.object(server.TOOLKIT, "InterviewerAgent", StubInterviewerAgent):
                    with patch.object(server.TOOLKIT, "IntervieweeAgent", StubIntervieweeAgent):
                        with patch.object(server.TOOLKIT.PersonaBuilder, "generate_persona", side_effect=make_connection_error()):
                            payload = server.run_single_interview(
                                task=task,
                                persona=persona,
                                plan=plan,
                                interviewer_model="mock-model",
                                interviewee_model="mock-model",
                                event_policy={"enabled": False, "trigger_prob": 0.0},
                            )

        self.assertTrue(payload["ok"])
        result = payload["result"]
        self.assertTrue(result["history"])
        self.assertIn("final_profile", result)
        self.assertIn("warnings", result["final_profile"])
        self.assertIn("subject_report", result)
        self.assertIn("research_insights", result)


if __name__ == "__main__":
    unittest.main()
