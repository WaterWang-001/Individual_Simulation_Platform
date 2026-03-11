from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from .config import PluginConfig, project_model_config_candidates, resolve_config_secret
    from .paths import PluginPaths
except ImportError:  # script mode
    from config import PluginConfig, project_model_config_candidates, resolve_config_secret
    from paths import PluginPaths


@dataclass
class ToolError:
    code: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PluginToolkit:
    def __init__(self, config: PluginConfig, paths: PluginPaths):
        self.config = config
        self.paths = paths
        from core.io.output_store import OutputStore
        from core.services.agents.final_profiler import FinalProfiler
        from core.services.agents.interviewer_agent import InterviewerAgent, conversation_to_text
        from core.services.agents.interviewee_agent import IntervieweeAgent
        from core.services.agents.questionnaire_filler import QuestionnaireFiller
        from core.services.benchmark_case_service import BenchmarkCaseService
        from core.services.evaluation.scorer import Scorer
        from core.services.evaluation.stage_planner import StagePlanner
        from core.services.output_analysis_service import OutputAnalysisService
        from core.services.persona_builder import PersonaBuilder
        from core.services.llm_service import call_llm_with_retry
        from core.utils.json_tools import (
            request_json_with_retry,
            validate_aggregate_results_json,
            validate_candidate_personas_json,
            validate_individual_summary_json,
            validate_interview_outline_json,
            validate_interview_plan_json,
            validate_interview_task_json,
            validate_persona_pool_review_json,
            validate_professional_report_json,
            validate_research_insights_json,
            validate_simulated_reply_json,
            validate_stage_plan_json,
            validate_subject_report_json,
            validate_topic_report_json,
        )
        from core.utils.prompts import load_prompt, render_prompt

        self.OutputStore = OutputStore
        self.FinalProfiler = FinalProfiler
        self.InterviewerAgent = InterviewerAgent
        self.IntervieweeAgent = IntervieweeAgent
        self.QuestionnaireFiller = QuestionnaireFiller
        self.BenchmarkCaseService = BenchmarkCaseService
        self.OutputAnalysisService = OutputAnalysisService
        self.PersonaBuilder = PersonaBuilder
        self.Scorer = Scorer
        self.StagePlanner = StagePlanner
        self.conversation_to_text = conversation_to_text
        self.call_llm_with_retry = call_llm_with_retry
        self.request_json_with_retry = request_json_with_retry
        self.validate_interview_task_json = validate_interview_task_json
        self.validate_candidate_personas_json = validate_candidate_personas_json
        self.validate_persona_pool_review_json = validate_persona_pool_review_json
        self.validate_interview_plan_json = validate_interview_plan_json
        self.validate_stage_plan_json = validate_stage_plan_json
        self.validate_simulated_reply_json = validate_simulated_reply_json
        self.validate_individual_summary_json = validate_individual_summary_json
        self.validate_research_insights_json = validate_research_insights_json
        self.validate_aggregate_results_json = validate_aggregate_results_json
        self.validate_professional_report_json = validate_professional_report_json
        self.validate_interview_outline_json = validate_interview_outline_json
        self.validate_subject_report_json = validate_subject_report_json
        self.validate_topic_report_json = validate_topic_report_json
        self.load_prompt = load_prompt
        self.render_prompt = render_prompt

    def _relpath(self, value: str | Path) -> str:
        path = Path(value)
        try:
            return str(path.resolve().relative_to(self.paths.project_root.resolve()))
        except Exception:
            return str(value)

    def _sanitize_paths(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_paths(value)
                elif isinstance(value, str) and (
                    key.endswith("_path")
                    or key in {"path", "benchmark_dir", "project_root", "plugin_root", "demo_root", "outputs_dir"}
                ):
                    sanitized[key] = self._relpath(value)
                else:
                    sanitized[key] = value
            return sanitized
        if isinstance(obj, list):
            return [self._sanitize_paths(item) for item in obj]
        return obj

    def _load_project_model_config(self, model_name: Optional[str] = None):
        from core.schemas.common import ModelConfig

        config_path, raw, error = self._read_project_model_config_file()
        if raw is None:
            return None, self.error(
                error or "项目模型配置不存在。",
                code="model_config_not_found",
            )
        target = model_name or self.config.default_interviewer
        for item in raw.get("models", []):
            if item.get("name") == target:
                resolved, warning = self._resolve_model_config(item)
                if resolved is None:
                    return None, self.error(warning or f"模型 {target} 缺少有效配置", code="model_config_invalid")
                return resolved, None
        return None, self.error(f"模型不存在: {target}", code="model_not_found")

    def _try_load_project_model_config(self, model_name: Optional[str] = None):
        config_path, raw, error = self._read_project_model_config_file()
        if raw is None:
            return None, error or "未找到模型配置，已使用规则回退。"
        target = model_name or self.config.default_interviewer
        for item in raw.get("models", []):
            if item.get("name") == target:
                resolved, warning = self._resolve_model_config(item)
                if resolved is None:
                    return None, warning or f"模型 {target} 缺少有效配置，已使用规则回退。"
                return resolved, warning
        return None, f"模型 {target} 不存在，已使用规则回退。"

    def _project_model_config_candidates(self) -> List[Path]:
        return project_model_config_candidates(self.paths.plugin_root, self.config.project_model_config)

    def _read_project_model_config_file(self) -> tuple[Optional[Path], Optional[Dict[str, Any]], Optional[str]]:
        candidates = self._project_model_config_candidates()
        for config_path in candidates:
            if not config_path.exists():
                continue
            try:
                raw = json.loads(config_path.read_text(encoding="utf-8"))
            except Exception as exc:
                return config_path, None, f"模型配置读取失败 {self._relpath(config_path)}: {exc}"
            if not isinstance(raw, dict):
                return config_path, None, f"模型配置格式无效 {self._relpath(config_path)}，已使用规则回退。"
            return config_path, raw, None
        names = "、".join(self._relpath(path) for path in candidates)
        return None, None, f"未找到模型配置 {names}，已使用规则回退。"

    def _resolve_model_config(self, item: Dict[str, Any]):
        from core.schemas.common import ModelConfig

        target = str(item.get("name") or "").strip() or "unknown"
        api_key, api_key_warning = resolve_config_secret(item.get("api_key"), str(item.get("api_key_env") or ""))
        base_url, base_url_warning = resolve_config_secret(item.get("base_url"), str(item.get("base_url_env") or ""))
        if not api_key:
            detail = api_key_warning or "缺少 api_key"
            return None, f"模型 {target} 配置无效: {detail}，已使用规则回退。"
        if not base_url:
            detail = base_url_warning or "缺少 base_url"
            return None, f"模型 {target} 配置无效: {detail}，已使用规则回退。"
        warnings = [text for text in [api_key_warning, base_url_warning] if text]
        warning = None
        if warnings:
            warning = f"模型 {target} 配置包含环境变量解析信息: {'; '.join(warnings)}"
        return ModelConfig(name=target, api_key=api_key, base_url=base_url), warning

    def ok(self, **payload: Any) -> Dict[str, Any]:
        return {"ok": True, **self._sanitize_paths(payload)}

    def error(self, message: str, code: str = "error") -> Dict[str, Any]:
        return {"ok": False, "error": ToolError(code=code, message=message).to_dict()}

    def _normalize_history(self, history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for item in history or []:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip() or "unknown"
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            out.append({"role": role, "content": content})
        return out

    def _normalize_constraints(self, constraints: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(constraints, dict):
            return {}
        return copy.deepcopy(constraints)

    def _normalize_survey(self, survey: Optional[Dict[str, Any]], topic: str = "") -> Dict[str, Any]:
        if not isinstance(survey, dict):
            return {"survey_name": topic or "自动化访谈", "questions": []}
        output = copy.deepcopy(survey)
        output.setdefault("survey_name", topic or output.get("title") or "自动化访谈")
        output.setdefault("questions", [])
        normalized_questions = []
        for idx, question in enumerate(output.get("questions", []), start=1):
            if not isinstance(question, dict):
                continue
            q = copy.deepcopy(question)
            q.setdefault("id", idx)
            q.setdefault("type", "text_input")
            q.setdefault("question", f"问题{idx}")
            normalized_questions.append(q)
        output["questions"] = normalized_questions
        return output

    def _make_task_id(self, topic: str) -> str:
        slug = "".join(ch if ch.isalnum() else "-" for ch in topic.lower()).strip("-") or "interview-task"
        return f"{slug[:40]}-{uuid4().hex[:8]}"

    def _survey_from_plan(self, task: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        survey = self._normalize_survey(task.get("survey"), task.get("topic", ""))
        if survey.get("questions"):
            return survey
        questions = []
        for question in plan.get("questions", []):
            if not isinstance(question, dict):
                continue
            q = {
                "id": question.get("id"),
                "question": question.get("question"),
                "type": question.get("type", "text_input"),
            }
            if question.get("options"):
                q["options"] = question.get("options")
            if question.get("scale"):
                q["scale"] = question.get("scale")
            questions.append(q)
        survey["questions"] = questions
        survey.setdefault("survey_name", plan.get("topic") or task.get("topic") or "自动化访谈")
        return survey

    def _extract_answers_from_filled(self, filled_questionnaire: Dict[str, Any]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for question in filled_questionnaire.get("questions", []):
            qid = question.get("id")
            if qid is None:
                continue
            answers[str(qid)] = question.get("answer")
        return answers

    def _apply_filled_slots(self, survey: Dict[str, Any], filled_slots: Dict[str, Any]) -> Dict[str, Any]:
        output = copy.deepcopy(survey)
        for question in output.get("questions", []):
            qid = str(question.get("id"))
            question["answer"] = filled_slots.get(qid)
        return output

    def _question_map(self, survey: Dict[str, Any], plan: Optional[Dict[str, Any]] = None) -> Dict[int, Dict[str, Any]]:
        qmap: Dict[int, Dict[str, Any]] = {}
        for question in survey.get("questions", []):
            qmap[int(question["id"])] = copy.deepcopy(question)
        if plan:
            meta_by_id = {int(q["id"]): q for q in plan.get("questions", []) if isinstance(q, dict) and q.get("id") is not None}
            for qid, question in list(qmap.items()):
                if qid in meta_by_id:
                    merged = copy.deepcopy(meta_by_id[qid])
                    merged.update(question)
                    qmap[qid] = merged
        return qmap

    def _heuristic_stage_name(self, question_text: str) -> str:
        text = question_text or ""
        if any(token in text for token in ["背景", "年龄", "职业", "身份", "家庭", "教育"]):
            return "背景与基本信息"
        if any(token in text for token in ["看法", "态度", "评价", "是否同意", "认可"]):
            return "态度与评价"
        if any(token in text for token in ["原因", "影响", "挑战", "困难", "为什么"]):
            return "经验与决策逻辑"
        return "核心主题探索"

    def _fallback_task(
        self,
        topic: str,
        target_population: str,
        research_goal: str,
        survey: Dict[str, Any],
        sample_size: int,
        report_style: str,
        constraints: Dict[str, Any],
        warning: Optional[str] = None,
    ) -> Dict[str, Any]:
        warnings = []
        if warning:
            warnings.append(warning)
        if not survey.get("questions"):
            warnings.append("未提供结构化问卷，后续建议先生成访谈大纲或访谈计划。")
        return {
            "task_id": self._make_task_id(topic or "interview"),
            "topic": topic,
            "target_population": target_population,
            "research_goal": research_goal,
            "sample_size": max(1, int(sample_size or 1)),
            "report_style": report_style or "professional",
            "survey": survey,
            "constraints": constraints,
            "warnings": warnings,
        }

    def _fallback_persona_pool(self, task: Dict[str, Any], sample_size: int) -> Dict[str, Any]:
        target = task.get("target_population") or "目标人群"
        topic = task.get("topic") or "该主题"
        base_profiles = [
            ("开放支持", "整体较支持，愿意分享正向经验", ["积极", "支持"], "先做判断再补理由", ["支持派", "信息充分"]),
            ("谨慎观望", "愿意交流，但存在现实顾虑和权衡", ["犹豫", "谨慎"], "先讲顾虑再讲条件", ["观望派", "成本敏感"]),
            ("被动执行", "更多受环境或他人影响，主观投入较低", ["被动", "随大流"], "回答简短，依赖既有经验", ["低参与", "跟随型"]),
            ("质疑保留", "对主题相关做法有明显保留态度", ["保留", "怀疑"], "会追问依据，强调风险", ["质疑派", "风险敏感"]),
        ]
        personas = []
        for idx in range(max(1, sample_size)):
            label, summary, attitudes, decision_style, tags = base_profiles[idx % len(base_profiles)]
            personas.append(
                {
                    "persona_id": f"persona_{idx + 1:02d}",
                    "profile_summary": f"{target}中的{label}类型，围绕{topic}表现出{summary}。",
                    "demographics": {
                        "target_population": target,
                        "life_stage": "未明确",
                        "education": "未明确",
                        "occupation": "未明确",
                    },
                    "topic_attitudes": attitudes,
                    "behavior_habits": ["会结合个人经验作答", "在关键问题上表达个人判断"],
                    "decision_style": decision_style,
                    "language_style": "口语化、愿意解释但长度不稳定",
                    "diversity_tags": tags,
                }
            )
        return {
            "personas": personas,
            "coverage_notes": ["当前为规则回退生成的人群差异样本，建议后续用模型补充更细粒度差异。"],
        }

    def _fallback_plan(self, task: Dict[str, Any]) -> Dict[str, Any]:
        survey = self._normalize_survey(task.get("survey"), task.get("topic", ""))
        question_rows = survey.get("questions", [])
        if not question_rows:
            questions = [
                {"id": 1, "question": f"请先简单介绍一下你与{task.get('topic', '这个主题')}的相关经历。", "type": "text_input", "stage_name": "背景与进入话题", "intent": "建立背景", "optional": False, "followup_hint": "追问具体经历和角色"},
                {"id": 2, "question": f"你对{task.get('topic', '这个主题')}目前最关心的点是什么？", "type": "text_input", "stage_name": "核心观点", "intent": "识别核心关切", "optional": False, "followup_hint": "追问原因与影响"},
                {"id": 3, "question": "如果从你的实际经验出发，你会给出哪些建议？", "type": "text_input", "stage_name": "建议与收尾", "intent": "提炼建议", "optional": True, "followup_hint": "追问优先级和落地条件"},
            ]
        else:
            questions = []
            for question in question_rows:
                stage_name = self._heuristic_stage_name(str(question.get("question", "")))
                questions.append(
                    {
                        "id": int(question.get("id")),
                        "question": question.get("question"),
                        "type": question.get("type", "text_input"),
                        "stage_name": stage_name,
                        "intent": "覆盖该问题对应的信息槽位",
                        "optional": False,
                        "followup_hint": "如果回答模糊，则追问具体经历、原因或条件。",
                        "options": question.get("options"),
                        "scale": question.get("scale"),
                    }
                )
        stage_buckets: Dict[str, List[int]] = {}
        for question in questions:
            stage_buckets.setdefault(question["stage_name"], []).append(int(question["id"]))
        stages = []
        must_cover_ids: List[int] = []
        for idx, (stage_name, question_ids) in enumerate(stage_buckets.items(), start=1):
            stages.append(
                {
                    "stage_id": f"stage_{idx}",
                    "stage_name": stage_name,
                    "stage_goal": f"围绕“{stage_name}”收集足够信息以服务研究目标。",
                    "question_ids": question_ids,
                    "must_cover": question_ids[: min(2, len(question_ids))],
                }
            )
            must_cover_ids.extend(question_ids[: min(2, len(question_ids))])
        return {
            "topic": task.get("topic"),
            "intro_text": f"本次访谈围绕“{task.get('topic')}”展开，重点了解{task.get('target_population') or '目标对象'}的经历、判断与需求。",
            "closing_prompt": "感谢你的分享。如果还有想补充的地方，可以在最后再补充一句。",
            "stages": stages,
            "questions": questions,
            "must_cover_ids": must_cover_ids,
            "sensitive_points": [],
            "completion_rule": {
                "min_must_cover": len(must_cover_ids),
                "max_turns": max(8, len(questions) * 2),
                "stop_when": "must_cover 完成且没有新的高价值追问点",
            },
        }

    def _fallback_stage_plan(
        self,
        task: Dict[str, Any],
        plan: Dict[str, Any],
        answered_ids: List[int],
        used_turns: int,
    ) -> Dict[str, Any]:
        answered = set(int(x) for x in answered_ids)
        for stage in plan.get("stages", []):
            question_ids = [int(qid) for qid in stage.get("question_ids", [])]
            remaining = [qid for qid in question_ids if qid not in answered]
            if remaining:
                must_cover = [int(qid) for qid in stage.get("must_cover", [])]
                must_cover_remaining = [qid for qid in must_cover if qid not in answered]
                next_focus = remaining[0]
                return {
                    "current_stage": stage.get("stage_name"),
                    "stage_goal": stage.get("stage_goal"),
                    "must_cover_remaining": must_cover_remaining,
                    "next_focus": next_focus,
                    "used_turns": used_turns,
                }
        return {
            "current_stage": "收尾",
            "stage_goal": "确认是否还有补充信息并准备结束访谈。",
            "must_cover_remaining": [],
            "next_focus": None,
            "used_turns": used_turns,
        }

    def _fallback_simulated_reply(self, persona: Dict[str, Any], question: Dict[str, Any], event_policy: Dict[str, Any]) -> Dict[str, Any]:
        qid = str(question.get("id"))
        answer_memory = persona.get("answer_memory") if isinstance(persona, dict) else {}
        if not isinstance(answer_memory, dict):
            answer_memory = {}
        enabled = bool((event_policy or {}).get("enabled", False))
        trigger_prob = float((event_policy or {}).get("trigger_prob", 0.0) or 0.0)
        event_type = "none"
        reply = answer_memory.get(qid)
        if enabled and trigger_prob > 0 and random.random() < trigger_prob:
            event_type = str((event_policy or {}).get("event_type") or "passive_noncooperation")
            if event_type == "topic_refusal":
                reply = "这个问题我不太想展开。"
            elif event_type == "question_misunderstanding":
                reply = "我有点没理解，你说的是哪一方面？"
            else:
                reply = "我现在只想简单说一点。"
        if reply in [None, ""]:
            reply = f"就{question.get('question', '这个问题')}来说，我会更关注实际经验、影响和可行性。"
        return {
            "reply": str(reply),
            "event": {"event_type": event_type},
            "state_hint": "needs_recovery" if event_type != "none" else "continue",
        }

    def _fallback_subject_report(
        self,
        task: Dict[str, Any],
        persona: Dict[str, Any],
        history: List[Dict[str, str]],
        filled_questionnaire: Dict[str, Any],
        research_insights: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        answers = self._extract_answers_from_filled(filled_questionnaire)
        return {
            "topic": task.get("topic"),
            "user_need_response": f"本报告围绕“{task.get('research_goal') or task.get('topic')}”整理该对象的经历、判断和关键顾虑。",
            "subject_summary": persona.get("profile_summary") or persona.get("persona_profile") or "该对象愿意围绕主题提供个人经验与判断。",
            "questionnaire_aligned_findings": [
                {"question_id": q.get("id"), "question": q.get("question"), "answer": q.get("answer")} for q in filled_questionnaire.get("questions", [])
            ],
            "traits_and_patterns": persona.get("persona_traits") or {"behavior_habits": [], "language_habits": []},
            "risks_and_concerns": ["部分结论仍基于有限轮次访谈，需要结合更多样本验证。"],
            "actionable_recommendations": research_insights.get("action_suggestions", []) if isinstance(research_insights, dict) else [],
            "evidence_trace": history[-6:],
            "confidence_notes": {"level": "medium", "answer_count": len([v for v in answers.values() if v not in [None, ""]])},
        }

    def _fallback_research_insights(self, task: Dict[str, Any], filled_questionnaire: Dict[str, Any]) -> Dict[str, Any]:
        non_empty = [q for q in filled_questionnaire.get("questions", []) if q.get("answer") not in [None, ""]]
        return {
            "topic": task.get("topic"),
            "research_goal": task.get("research_goal"),
            "key_insights": [
                f"本对象对“{task.get('topic')}”给出了 {len(non_empty)} 个有效回答，可作为单个样本的经验观察。"
            ],
            "decision_patterns": ["倾向从个人经验出发解释观点。"],
            "barriers": ["若样本量不足，难以判断结论代表性。"],
            "action_suggestions": ["在后续样本中重点验证高频关注点和关键分歧。"],
            "evidence_trace": [{"question_id": q.get("id"), "answer": q.get("answer")} for q in non_empty[:5]],
        }

    def _fallback_aggregation(self, task: Dict[str, Any], interview_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        sample_overview = {
            "sample_size": len(interview_results),
            "persona_ids": [item.get("persona_id") for item in interview_results],
        }
        common_patterns = []
        for result in interview_results:
            insights = result.get("research_insights") or {}
            for text in insights.get("key_insights", []):
                if text and text not in common_patterns:
                    common_patterns.append(text)
        return {
            "topic": task.get("topic"),
            "sample_overview": sample_overview,
            "common_patterns": common_patterns[:6] or ["当前样本总体围绕同一主题表达了不同层次的经历与判断。"],
            "differences": ["样本间在态度强弱、风险感知和行动条件上存在差异。"],
            "risks": ["当前聚合结果仍受样本量与 persona 多样性的限制。"],
            "recommendations": ["补充更多具有差异特征的对象，以增强研究结论的稳健性。"],
        }

    def _fallback_professional_report(
        self,
        task: Dict[str, Any],
        personas: List[Dict[str, Any]],
        interview_results: List[Dict[str, Any]],
        aggregation: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "topic": task.get("topic"),
            "executive_summary": f"本次围绕“{task.get('topic')}”的自动化访谈共覆盖 {len(interview_results)} 个对象，形成了若干可用于研究判断的共性与差异结论。",
            "methodology": {
                "target_population": task.get("target_population"),
                "sample_size": len(interview_results),
                "report_style": task.get("report_style"),
            },
            "sample_profile": {
                "persona_count": len(personas),
                "diversity_tags": sorted({tag for persona in personas for tag in persona.get("diversity_tags", [])}),
            },
            "key_findings": aggregation.get("common_patterns", []),
            "theme_analysis": {
                "common_patterns": aggregation.get("common_patterns", []),
                "differences": aggregation.get("differences", []),
                "risks": aggregation.get("risks", []),
            },
            "population_segments": [
                {
                    "persona_id": result.get("persona_id"),
                    "summary": (result.get("subject_report") or {}).get("subject_summary"),
                }
                for result in interview_results
            ],
            "recommendations": aggregation.get("recommendations", []),
            "limitations": ["当前版本以单轮自动化编排为主，复杂追问策略仍可继续增强。"],
        }

    def _json_prompt(self, prompt_name: str, validator, model_name: Optional[str], fallback: Any = None, **kwargs: Any):
        model_cfg, warning = self._try_load_project_model_config(model_name)
        if model_cfg is None:
            return fallback, warning, None
        prompt = self.render_prompt(self.load_prompt(prompt_name), **kwargs)
        try:
            obj = self.request_json_with_retry(
                model_cfg,
                [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": prompt}],
                validator,
                max_retries=3,
            )
            return obj, warning, model_cfg.name
        except Exception as exc:
            return fallback, f"{warning + ' ' if warning else ''}模型生成失败，已使用规则回退: {exc}", model_cfg.name

    def get_project_map(self) -> Dict[str, Any]:
        prompt_files = sorted([p.name for p in self.paths.prompts_dir.glob("*.txt")])
        return self.ok(
            server_name=self.config.server_name,
            project_root=".",
            plugin_root=".",
            demo_root=self._relpath(self.paths.demo_root) if self.paths.demo_root.exists() else None,
            top_level_scripts=sorted([p.name for p in self.paths.project_root.glob("*.py")]),
            prompt_count=len(prompt_files),
            prompt_files=prompt_files,
            primary_capabilities=[
                "create_interview_task",
                "generate_candidate_personas",
                "generate_interview_plan",
                "run_single_interview",
                "aggregate_interview_results",
                "generate_professional_report",
            ],
            auxiliary_capabilities=[
                "generate_interview_outline",
                "plan_interview_stage",
                "draft_next_question",
                "simulate_interviewee_reply",
                "fill_questionnaire_from_history",
                "summarize_individual_interview",
                "extract_research_insights_from_interview",
                "score_questionnaire",
                "build_persona_from_answers",
            ],
            legacy_capabilities=[
                "legacy_list_benchmark_cases",
                "legacy_read_benchmark_case",
                "legacy_analyze_outputs",
                "legacy_compare_models_by_survey",
                "legacy_find_representative_cases",
                "legacy_read_output_record",
            ],
            default_event_mode="disabled",
        )

    def list_prompt_templates(self) -> Dict[str, Any]:
        items = []
        for path in sorted(self.paths.prompts_dir.glob("*.txt")):
            name = path.name
            if "persona" in name or "profile" in name:
                category = "persona"
            elif "plan" in name or "outline" in name or "task" in name:
                category = "planning"
            elif "report" in name or "summary" in name:
                category = "reporting"
            elif "interviewee" in name or "interviewer" in name:
                category = "conversation"
            elif "questionnaire" in name or "structured_answer" in name:
                category = "questionnaire"
            else:
                category = "other"
            items.append({"name": name, "path": self._relpath(path), "category": category})
        return self.ok(items=items)

    def score_questionnaire(self, questionnaire: Dict[str, Any], filled_questionnaire: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        score = self.Scorer().score(questionnaire, filled_questionnaire, ground_truth)
        return self.ok(score=score)

    def create_interview_task(
        self,
        topic: str,
        target_population: str,
        research_goal: str,
        survey: Optional[Dict[str, Any]] = None,
        sample_size: int = 5,
        report_style: str = "professional",
        constraints: Optional[Dict[str, Any]] = None,
        user_need: str = "",
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        survey_obj = self._normalize_survey(survey, topic)
        constraints_obj = self._normalize_constraints(constraints)
        fallback = self._fallback_task(topic, target_population, research_goal, survey_obj, sample_size, report_style, constraints_obj)
        task, warning, used_model = self._json_prompt(
            "create_interview_task_prompt.txt",
            self.validate_interview_task_json,
            model_name,
            fallback=fallback,
            topic=topic,
            target_population=target_population,
            research_goal=research_goal,
            survey_json=json.dumps(survey_obj, ensure_ascii=False, indent=2),
            sample_size=max(1, int(sample_size or 1)),
            report_style=report_style,
            constraints_json=json.dumps(constraints_obj, ensure_ascii=False, indent=2),
            user_need=user_need or "形成一次可执行的自动化访谈任务",
        )
        if warning:
            task.setdefault("warnings", []).append(warning)
        task.setdefault("task_id", self._make_task_id(topic))
        task.setdefault("topic", topic)
        task.setdefault("target_population", target_population)
        task.setdefault("research_goal", research_goal)
        task.setdefault("sample_size", max(1, int(sample_size or 1)))
        task.setdefault("report_style", report_style)
        task.setdefault("survey", survey_obj)
        task.setdefault("constraints", constraints_obj)
        task.setdefault("warnings", [])
        return self.ok(model_name=used_model, task=task)

    def generate_candidate_personas(
        self,
        task: Dict[str, Any],
        persona_pool: Optional[List[Dict[str, Any]]] = None,
        diversity_requirements: Optional[List[str]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = copy.deepcopy(task)
        sample_size = max(1, int(task.get("sample_size", 5)))
        fallback = self._fallback_persona_pool(task, sample_size)
        pool_json = json.dumps(persona_pool or [], ensure_ascii=False, indent=2)
        result, warning, used_model = self._json_prompt(
            "generate_candidate_personas_prompt.txt",
            self.validate_candidate_personas_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            persona_pool_json=pool_json,
            diversity_requirements_json=json.dumps(diversity_requirements or [], ensure_ascii=False, indent=2),
        )
        personas = result.get("personas", [])[:sample_size]
        if persona_pool:
            existing_ids = {p.get("persona_id") for p in personas if isinstance(p, dict)}
            for persona in persona_pool:
                if not isinstance(persona, dict):
                    continue
                if len(personas) >= sample_size:
                    break
                if persona.get("persona_id") in existing_ids:
                    continue
                personas.append(copy.deepcopy(persona))
        result["personas"] = personas[:sample_size]
        if warning:
            result.setdefault("coverage_notes", []).append(warning)
        return self.ok(model_name=used_model, personas=result.get("personas", []), coverage_notes=result.get("coverage_notes", []))

    def review_persona_pool(
        self,
        task: Dict[str, Any],
        personas: List[Dict[str, Any]],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        fallback = {
            "coverage_ok": len(personas) >= max(1, min(3, int(task.get("sample_size", 3)))),
            "homogeneity_risk": "medium" if len(personas) < 3 else "low",
            "missing_segments": [],
            "recommendations": ["优先补充态度、经验或信息来源差异明显的对象。"],
        }
        review, warning, used_model = self._json_prompt(
            "review_persona_pool_prompt.txt",
            self.validate_persona_pool_review_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            personas_json=json.dumps(personas or [], ensure_ascii=False, indent=2),
        )
        if warning:
            review.setdefault("recommendations", []).append(warning)
        return self.ok(model_name=used_model, review=review)

    def generate_interview_plan(self, task: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
        task = copy.deepcopy(task)
        fallback = self._fallback_plan(task)
        plan, warning, used_model = self._json_prompt(
            "generate_interview_plan_prompt.txt",
            self.validate_interview_plan_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            survey_json=json.dumps(task.get("survey") or {}, ensure_ascii=False, indent=2),
        )
        if warning:
            plan.setdefault("warnings", []).append(warning)
        return self.ok(model_name=used_model, plan=plan)

    def generate_interview_outline(
        self,
        topic: str,
        research_goal: str = "",
        target_population: str = "",
        user_need: str = "",
        interview_style: str = "semi_structured",
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        task_payload = self.create_interview_task(
            topic=topic,
            target_population=target_population or "与该主题相关的目标对象",
            research_goal=research_goal or "围绕该主题获取可用于访谈分析的关键信息",
            survey=None,
            sample_size=5,
            report_style=interview_style,
            constraints={"interview_style": interview_style},
            user_need=user_need or "生成一份能直接用于自动化访谈流程的访谈大纲",
            model_name=model_name,
        )
        if not task_payload.get("ok"):
            return task_payload
        task = task_payload["task"]
        plan_payload = self.generate_interview_plan(task=task, model_name=model_name)
        if not plan_payload.get("ok"):
            return plan_payload
        plan = plan_payload["plan"]
        outline = {
            "topic": task.get("topic"),
            "survey_name": (task.get("survey") or {}).get("survey_name") or f"{task.get('topic')}访谈提纲",
            "interview_goal": task.get("research_goal"),
            "intro_text": plan.get("intro_text", ""),
            "stages": plan.get("stages", []),
            "questions": plan.get("questions", []),
            "closing_prompt": plan.get("closing_prompt", ""),
        }
        return self.ok(model_name=plan_payload.get("model_name"), outline=outline)

    def plan_interview_stage(
        self,
        task: Dict[str, Any],
        plan: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
        filled_slots: Optional[Dict[str, Any]] = None,
        answered_ids: Optional[List[int]] = None,
        used_turns: int = 0,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        filled_slots = filled_slots or {}
        covered_from_slots = [int(k) for k, v in filled_slots.items() if v not in [None, ""]]
        answered = sorted(set((answered_ids or []) + covered_from_slots))
        fallback = self._fallback_stage_plan(task, plan, answered, used_turns)
        stage_plan, warning, used_model = self._json_prompt(
            "plan_interview_stage_prompt.txt",
            self.validate_stage_plan_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            plan_json=json.dumps(plan, ensure_ascii=False, indent=2),
            history_json=json.dumps(self._normalize_history(history), ensure_ascii=False, indent=2),
            filled_slots_json=json.dumps(filled_slots, ensure_ascii=False, indent=2),
            answered_ids_json=json.dumps(answered, ensure_ascii=False),
            used_turns=used_turns,
        )
        if warning:
            stage_plan.setdefault("warnings", []).append(warning)
        return self.ok(model_name=used_model, stage=stage_plan)

    def draft_next_question(
        self,
        task: Dict[str, Any],
        plan: Dict[str, Any],
        persona: Dict[str, Any],
        history: List[Dict[str, Any]],
        filled_slots: Optional[Dict[str, Any]] = None,
        answered_ids: Optional[List[int]] = None,
        skipped_ids: Optional[List[int]] = None,
        used_turns: int = 0,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = self._normalize_history(history)
        filled_slots = filled_slots or {}
        skipped = set(int(x) for x in (skipped_ids or []))
        stage_payload = self.plan_interview_stage(task, plan, history, filled_slots, answered_ids, used_turns, model_name)
        if not stage_payload.get("ok"):
            return stage_payload
        stage = stage_payload["stage"]
        survey = self._survey_from_plan(task, plan)
        qmap = self._question_map(survey, plan)
        answered = set(int(x) for x in (answered_ids or [])) | {int(k) for k, v in filled_slots.items() if v not in [None, ""]}
        candidate_ids = [int(qid) for qid in next((s.get("question_ids", []) for s in plan.get("stages", []) if s.get("stage_name") == stage.get("current_stage")), [])]
        if not candidate_ids:
            candidate_ids = sorted(qmap.keys())
        remaining = [qid for qid in candidate_ids if qid not in answered and qid not in skipped]
        if not remaining:
            return self.ok(
                model_name=stage_payload.get("model_name"),
                stage=stage,
                action={"action": "conclude", "target_question_id": None, "reason_tag": "complete"},
                target_question=None,
                question_text="",
                coverage_update_hint="所有阶段问题已覆盖，可以进入收尾。",
            )
        target_qid = int(stage.get("next_focus") or remaining[0])
        if target_qid not in qmap:
            target_qid = remaining[0]
        target_question = qmap[target_qid]
        question_text = str(target_question.get("question") or "")
        model_cfg, warning = self._try_load_project_model_config(model_name)
        if model_cfg is not None:
            try:
                agent = self.InterviewerAgent(model_cfg)
                question_text = agent.generate_response("ask_question", "plan_driven", target_question, history)
            except Exception:
                pass
        elif warning:
            target_question.setdefault("warnings", []).append(warning)
        return self.ok(
            model_name=model_cfg.name if model_cfg else None,
            stage=stage,
            action={"action": "ask_question", "target_question_id": target_qid, "reason_tag": "plan_driven"},
            target_question=target_question,
            question_text=question_text,
            coverage_update_hint=target_question.get("followup_hint") or "优先收集与该问题直接相关的事实、原因和例子。",
        )

    def simulate_interviewee_reply(
        self,
        task: Dict[str, Any],
        persona: Dict[str, Any],
        question: Dict[str, Any],
        history: List[Dict[str, Any]],
        stage_context: Optional[Dict[str, Any]] = None,
        event_policy: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = self._normalize_history(history)
        event_policy = event_policy or {"enabled": False, "trigger_prob": 0.0}
        fallback = self._fallback_simulated_reply(persona, question, event_policy)
        model_cfg, warning = self._try_load_project_model_config(model_name)
        if model_cfg is None:
            if warning:
                fallback.setdefault("warnings", []).append(warning)
            return self.ok(model_name=None, simulation=fallback)
        try:
            qid = int(question.get("id") or 1)
            if event_policy.get("enabled"):
                scenario_plan = {
                    qid: {
                        "event_type": str(event_policy.get("event_type") or "passive_noncooperation"),
                        "event_description": "根据事件策略触发的异常场景",
                        "event_emotion": str(event_policy.get("emotion") or "犹豫"),
                        "event_intensity": str(event_policy.get("intensity") or "轻微"),
                        "event_expression": str(event_policy.get("expression") or "直接表达"),
                    }
                }
                no_event_mode = False
                trigger_prob = float(event_policy.get("trigger_prob", 0.0) or 0.0)
            else:
                scenario_plan = {qid: {"event_type": "none", "event_description": "无异常", "event_emotion": "平静", "event_intensity": "轻微", "event_expression": "直接表达"}}
                no_event_mode = True
                trigger_prob = 0.0
            agent = self.IntervieweeAgent(model_cfg, persona, scenario_plan, event_trigger_prob=trigger_prob, no_event_mode=no_event_mode)
            reply, event = agent.respond(qid, str(question.get("question") or ""), history)
            result = {
                "reply": reply,
                "event": event,
                "state_hint": "needs_recovery" if (event or {}).get("event_type") not in [None, "", "none"] else "continue",
            }
            return self.ok(model_name=model_cfg.name, simulation=result)
        except Exception as exc:
            fallback.setdefault("warnings", []).append(f"模型回复生成失败，已使用规则回退: {exc}")
            return self.ok(model_name=model_cfg.name, simulation=fallback)

    def fill_questionnaire_from_history(
        self,
        task: Dict[str, Any],
        plan: Dict[str, Any],
        history: List[Dict[str, Any]],
        filled_slots: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        survey = self._survey_from_plan(task, plan)
        if filled_slots:
            return self.ok(filled_questionnaire=self._apply_filled_slots(survey, filled_slots), source="filled_slots")
        model_cfg, warning = self._try_load_project_model_config(model_name)
        if model_cfg is None:
            out = self._apply_filled_slots(survey, {})
            if warning:
                out["_warning"] = warning
            return self.ok(filled_questionnaire=out, source="empty_fallback")
        filler = self.QuestionnaireFiller(model_cfg, use_summary=True)
        filled = filler.fill(survey, self._normalize_history(history))
        return self.ok(model_name=model_cfg.name, filled_questionnaire=filled, source="llm_filler")

    def build_persona_from_answers(self, answers: Dict[str, Any], model_name: Optional[str] = None) -> Dict[str, Any]:
        model_cfg, warning = self._try_load_project_model_config(model_name)
        ground_truth = {int(k): v for k, v in answers.items()}
        if model_cfg is None:
            persona = self.PersonaBuilder.ensure_consistency(self.PersonaBuilder.build_fallback(ground_truth), ground_truth)
            if warning:
                persona.setdefault("warnings", []).append(warning)
            return self.ok(model_name=None, persona=persona)
        try:
            persona = self.PersonaBuilder.generate_persona(model_cfg, ground_truth)
        except Exception as exc:
            persona = self.PersonaBuilder.ensure_consistency(self.PersonaBuilder.build_fallback(ground_truth), ground_truth)
            persona.setdefault("warnings", []).append(f"模型画像生成失败，已使用规则回退: {exc}")
        if warning:
            persona.setdefault("warnings", []).append(warning)
        return self.ok(model_name=model_cfg.name, persona=persona)

    def summarize_individual_interview(
        self,
        task: Dict[str, Any],
        persona: Dict[str, Any],
        history: List[Dict[str, Any]],
        filled_questionnaire: Dict[str, Any],
        user_need: str = "",
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = self._normalize_history(history)
        fallback = self._fallback_subject_report(task, persona, history, filled_questionnaire)
        summary, warning, used_model = self._json_prompt(
            "summarize_individual_interview_prompt.txt",
            self.validate_individual_summary_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            persona_json=json.dumps(persona or {}, ensure_ascii=False, indent=2),
            filled_questionnaire_json=json.dumps(filled_questionnaire or {}, ensure_ascii=False, indent=2),
            history_text=self.conversation_to_text(history),
            user_need=user_need or task.get("research_goal") or task.get("topic") or "形成单对象访谈总结",
        )
        if warning:
            summary.setdefault("confidence_notes", {}).setdefault("warnings", []).append(warning)
        return self.ok(model_name=used_model, report=summary)

    def extract_research_insights_from_interview(
        self,
        task: Dict[str, Any],
        persona: Dict[str, Any],
        history: List[Dict[str, Any]],
        filled_questionnaire: Dict[str, Any],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        history = self._normalize_history(history)
        fallback = self._fallback_research_insights(task, filled_questionnaire)
        insights, warning, used_model = self._json_prompt(
            "extract_research_insights_prompt.txt",
            self.validate_research_insights_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            persona_json=json.dumps(persona or {}, ensure_ascii=False, indent=2),
            filled_questionnaire_json=json.dumps(filled_questionnaire or {}, ensure_ascii=False, indent=2),
            history_text=self.conversation_to_text(history),
        )
        if warning:
            insights.setdefault("warnings", []).append(warning)
        return self.ok(model_name=used_model, insights=insights)

    def run_single_interview(
        self,
        task: Dict[str, Any],
        persona: Dict[str, Any],
        plan: Dict[str, Any],
        interviewer_model: Optional[str] = None,
        interviewee_model: Optional[str] = None,
        event_policy: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        history: List[Dict[str, str]] = []
        filled_slots: Dict[str, Any] = {}
        answered_ids: List[int] = []
        skipped_ids: List[int] = []
        event_policy = event_policy or {"enabled": False, "trigger_prob": 0.0}
        completion = plan.get("completion_rule") or {}
        max_turns = int(completion.get("max_turns") or max(8, len(plan.get("questions", [])) * 2 or 8))
        turns = 0
        event_count = 0
        while turns < max_turns:
            draft = self.draft_next_question(
                task=task,
                plan=plan,
                persona=persona,
                history=history,
                filled_slots=filled_slots,
                answered_ids=answered_ids,
                skipped_ids=skipped_ids,
                used_turns=turns,
                model_name=interviewer_model,
            )
            if not draft.get("ok"):
                return draft
            action = draft.get("action", {})
            if action.get("action") == "conclude" or not draft.get("target_question"):
                break
            question_text = draft.get("question_text") or draft.get("target_question", {}).get("question", "")
            target_question = draft.get("target_question") or {}
            history.append({"role": "interviewer", "content": question_text})
            turns += 1
            simulation = self.simulate_interviewee_reply(
                task=task,
                persona=persona,
                question=target_question,
                history=history,
                stage_context=draft.get("stage"),
                event_policy=event_policy,
                model_name=interviewee_model,
            )
            if not simulation.get("ok"):
                return simulation
            sim = simulation.get("simulation", {})
            reply = str(sim.get("reply") or "")
            event = sim.get("event") or {"event_type": "none"}
            history.append({"role": "interviewee", "content": reply})
            turns += 1
            if event.get("event_type") not in [None, "", "none"]:
                event_count += 1
                skipped_ids.append(int(target_question.get("id") or 0))
            else:
                qid = str(target_question.get("id"))
                filled_slots[qid] = reply
                answered_ids.append(int(target_question.get("id") or 0))
            must_cover = set(int(x) for x in plan.get("must_cover_ids", []))
            if must_cover and must_cover.issubset(set(answered_ids)) and len(answered_ids) >= len(must_cover):
                if len(answered_ids) >= len(plan.get("questions", [])):
                    break
        filled_payload = self.fill_questionnaire_from_history(task, plan, history, filled_slots=filled_slots, model_name=interviewer_model)
        if not filled_payload.get("ok"):
            return filled_payload
        filled_questionnaire = filled_payload.get("filled_questionnaire", {})
        persona_payload = self.build_persona_from_answers(self._extract_answers_from_filled(filled_questionnaire), model_name=interviewer_model)
        if not persona_payload.get("ok"):
            return persona_payload
        final_profile = persona_payload.get("persona", {})
        insights_payload = self.extract_research_insights_from_interview(task, persona, history, filled_questionnaire, model_name=interviewer_model)
        if not insights_payload.get("ok"):
            return insights_payload
        subject_payload = self.summarize_individual_interview(task, persona, history, filled_questionnaire, user_need=task.get("research_goal", ""), model_name=interviewer_model)
        if not subject_payload.get("ok"):
            return subject_payload
        process_metrics = {
            "turn_count": turns,
            "event_count": event_count,
            "answered_count": len(set(answered_ids)),
            "completion_ratio": round(len(set(answered_ids)) / max(1, len(plan.get("questions", []))), 4),
            "event_policy": event_policy,
        }
        result = {
            "persona_id": persona.get("persona_id"),
            "history": history,
            "filled_questionnaire": filled_questionnaire,
            "final_profile": final_profile,
            "subject_report": subject_payload.get("report", {}),
            "research_insights": insights_payload.get("insights", {}),
            "process_metrics": process_metrics,
        }
        return self.ok(result=result)

    def aggregate_interview_results(
        self,
        task: Dict[str, Any],
        interview_results: List[Dict[str, Any]],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        fallback = self._fallback_aggregation(task, interview_results)
        aggregation, warning, used_model = self._json_prompt(
            "aggregate_interview_results_prompt.txt",
            self.validate_aggregate_results_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            interview_results_json=json.dumps(interview_results or [], ensure_ascii=False, indent=2),
        )
        if warning:
            aggregation.setdefault("recommendations", []).append(warning)
        return self.ok(model_name=used_model, aggregation=aggregation)

    def generate_professional_report(
        self,
        task: Dict[str, Any],
        personas: List[Dict[str, Any]],
        interview_results: List[Dict[str, Any]],
        aggregation: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        aggregation = aggregation or self.aggregate_interview_results(task, interview_results, model_name).get("aggregation", {})
        fallback = self._fallback_professional_report(task, personas, interview_results, aggregation)
        report, warning, used_model = self._json_prompt(
            "generate_professional_report_prompt.txt",
            self.validate_professional_report_json,
            model_name,
            fallback=fallback,
            task_json=json.dumps(task, ensure_ascii=False, indent=2),
            personas_json=json.dumps(personas or [], ensure_ascii=False, indent=2),
            interview_results_json=json.dumps(interview_results or [], ensure_ascii=False, indent=2),
            aggregation_json=json.dumps(aggregation or {}, ensure_ascii=False, indent=2),
        )
        if warning:
            report.setdefault("limitations", []).append(warning)
        return self.ok(model_name=used_model, report=report)

    def build_subject_report(
        self,
        topic: str,
        user_need: str,
        interview_history: List[Dict[str, str]],
        structured_answers: Optional[Dict[str, Any]] = None,
        persona: Optional[Dict[str, Any]] = None,
        outline: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = {
            "topic": topic,
            "target_population": "未指定",
            "research_goal": user_need,
            "survey": {"survey_name": topic, "questions": (outline or {}).get("questions", [])},
            "sample_size": 1,
            "report_style": "professional",
            "constraints": {},
            "warnings": [],
        }
        filled = structured_answers or {"questions": []}
        return self.summarize_individual_interview(task, persona or {}, interview_history, filled, user_need=user_need, model_name=model_name)

    def build_topic_research_report(
        self,
        topic: str,
        research_goal: str,
        user_need: str,
        subjects: List[Dict[str, Any]],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = {
            "topic": topic,
            "target_population": "未指定",
            "research_goal": research_goal,
            "survey": {},
            "sample_size": len(subjects),
            "report_style": "professional",
            "constraints": {},
            "warnings": [],
        }
        aggregation_payload = self.aggregate_interview_results(task, subjects, model_name=model_name)
        if not aggregation_payload.get("ok"):
            return aggregation_payload
        personas = [item.get("final_profile") or item.get("persona") or {} for item in subjects]
        return self.generate_professional_report(task, personas, subjects, aggregation_payload.get("aggregation"), model_name=model_name)

    def legacy_list_benchmark_cases(self, clean_only: bool = True) -> Dict[str, Any]:
        service = self.BenchmarkCaseService(self.paths.benchmarks_dir)
        return self.ok(items=service.list_cases(clean_only=clean_only))

    def legacy_read_benchmark_case(self, case_id: str) -> Dict[str, Any]:
        service = self.BenchmarkCaseService(self.paths.benchmarks_dir)
        case = service.read_case(case_id)
        if case is None:
            return self.error(f"benchmark case 不存在: {case_id}", code="case_not_found")
        return self.ok(case=case.to_dict())

    def legacy_analyze_outputs(self) -> Dict[str, Any]:
        store = self.OutputStore(self.paths.outputs_dir)
        service = self.OutputAnalysisService(store)
        return self.ok(analysis=service.analyze_outputs())

    def legacy_compare_models_by_survey(self) -> Dict[str, Any]:
        store = self.OutputStore(self.paths.outputs_dir)
        service = self.OutputAnalysisService(store)
        return self.ok(items=service.compare_models_by_survey())

    def legacy_find_representative_cases(self, top_k: int = 5, require_events: bool = True) -> Dict[str, Any]:
        store = self.OutputStore(self.paths.outputs_dir)
        service = self.OutputAnalysisService(store)
        return self.ok(items=service.find_representative_cases(top_k=top_k, require_events=require_events))

    def legacy_read_output_record(
        self,
        record_type: str,
        benchmark_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        store = self.OutputStore(self.paths.outputs_dir)
        return self.ok(items=store.read_output_record(record_type=record_type, benchmark_dir=benchmark_dir, model_name=model_name))
