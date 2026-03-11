from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List

from ..io.file_store import load_json
from ..schemas.benchmark import BenchmarkCase
from ..schemas.common import ErrorRecord, ModelConfig, WarningRecord
from ..schemas.interview import InterviewState
from ..schemas.outputs import RunResult
from ..services.agents.final_profiler import FinalProfiler
from ..services.agents.interviewee_agent import IntervieweeAgent
from ..services.agents.interviewer_agent import InterviewerAgent
from ..services.agents.questionnaire_filler import QuestionnaireFiller
from ..services.agents.questionnaire_summarizer import QuestionnaireSummarizer
from ..services.evaluation.process_evaluator import ProcessEvaluator
from ..services.evaluation.recovery_policy_engine import RecoveryPolicyEngine
from ..services.evaluation.scorer import Scorer
from ..services.evaluation.stage_planner import StagePlanner


class InterviewOrchestrator:
    def __init__(self, config: Dict[str, ModelConfig]):
        self.config = config

    def _is_answer_sufficient(self, question: Dict[str, Any], answer_text: str, event: Dict[str, Any]) -> bool:
        event_type = (event or {}).get("event_type", "none")
        if event_type in ["topic_refusal", "sensitive_topic_resistance", "passive_noncooperation", "memory_failure"]:
            return False
        text = (answer_text or "").strip()
        if len(text) < 2:
            return False
        qtype = question.get("type")
        if qtype in ["single_choice", "Likert"] and len(text) <= 1:
            return False
        return True

    def load_case(self, benchmark_dir: str) -> BenchmarkCase:
        questionnaire = load_json(os.path.join(benchmark_dir, "questionnaire.json"))
        ground_truth = load_json(os.path.join(benchmark_dir, "ground_truth.json"))
        persona = load_json(os.path.join(benchmark_dir, "persona.json"))
        scenario_plan = {int(k): v for k, v in load_json(os.path.join(benchmark_dir, "scenario_plan.json")).items()}
        meta_path = os.path.join(benchmark_dir, "meta.json")
        meta = load_json(meta_path) if os.path.exists(meta_path) else {}
        mapping_path = os.path.join(benchmark_dir, "mapping.json")
        mapping = load_json(mapping_path) if os.path.exists(mapping_path) else None
        return BenchmarkCase(
            benchmark_dir=benchmark_dir,
            questionnaire=questionnaire,
            ground_truth=ground_truth,
            persona=persona,
            scenario_plan=scenario_plan,
            meta=meta,
            mapping=mapping,
        )

    def run(
        self,
        benchmark_dir: str,
        interviewer_model: str,
        interviewee_model: str,
        max_turns_multiplier: int = 3,
        handling_mode: str = "default",
        ablation_mode: str = "direct",
        compare_fill_modes: bool = False,
        no_event_mode: bool = True,
        event_trigger_prob: float = 0.0,
        free_chat_turn_limit: int = 2,
    ) -> RunResult:
        benchmark_case = self.load_case(benchmark_dir)
        questionnaire = benchmark_case.questionnaire
        ground_truth = benchmark_case.ground_truth
        persona = benchmark_case.persona
        scenario_plan = benchmark_case.scenario_plan
        question_ids = [int(q["id"]) for q in questionnaire.get("questions", [])]
        max_turns = max_turns_multiplier * len(question_ids)
        run_id = uuid.uuid4().hex[:12]

        interviewer = InterviewerAgent(self.config[interviewer_model], handling_mode=handling_mode)
        interviewee = IntervieweeAgent(self.config[interviewee_model], persona, scenario_plan, event_trigger_prob=event_trigger_prob, no_event_mode=no_event_mode)
        filler = QuestionnaireFiller(self.config[interviewer_model], use_summary=(ablation_mode == "summary"))
        filler_direct = QuestionnaireFiller(self.config[interviewer_model], use_summary=False)
        filler_summary = QuestionnaireFiller(self.config[interviewer_model], use_summary=True)
        q_summarizer = QuestionnaireSummarizer(self.config[interviewer_model])
        final_profiler = FinalProfiler(self.config[interviewer_model])
        scorer = Scorer()
        planner = StagePlanner(questionnaire)
        process_evaluator = ProcessEvaluator()
        recovery_engine = RecoveryPolicyEngine()
        state = InterviewState()
        warnings: List[WarningRecord] = []
        errors: List[ErrorRecord] = []
        plan_limit = 2
        max_retry_per_q = 2
        questions_by_id = {int(q["id"]): q for q in questionnaire.get("questions", [])}

        q_sum = q_summarizer.summarize(questionnaire)
        intro = interviewer.generate_intro(q_sum.get("intro_text", ""))
        state.history.append({"role": "interviewer", "content": intro})
        state.history.append({"role": "interviewee", "content": "可以，我愿意参加。"})

        while state.used_turns < max_turns and len(state.answered_ids) < len(question_ids):
            remaining_ids = [qid for qid in question_ids if qid not in state.answered_ids and qid not in state.skipped_ids]
            if remaining_ids:
                primary_ids = [qid for qid in remaining_ids if qid not in state.deferred_ids]
                delayed_ids = [qid for qid in remaining_ids if qid in state.deferred_ids]
                remaining_ids = primary_ids + delayed_ids
            if not remaining_ids:
                break
            stage = planner.plan(state.answered_ids, state.skipped_ids)
            action_obj = interviewer.decide_action(
                answered_ids=state.answered_ids,
                skipped_ids=state.skipped_ids,
                remaining_ids=remaining_ids,
                stage_name=stage["stage_name"],
                stage_goal=stage["stage_goal"],
                stage_candidates=stage["stage_candidates"],
                plan_used=state.plan_used,
                plan_limit=plan_limit,
                max_turns=max_turns,
                used_turns=state.used_turns,
                history=state.history,
            )
            action = action_obj.get("action", "ask_question")
            reason_tag = action_obj.get("reason_tag", "normal")
            note = action_obj.get("note", "")
            raw_target = action_obj.get("target_question_id")
            try:
                target_qid = int(raw_target) if raw_target is not None else remaining_ids[0]
            except (TypeError, ValueError):
                target_qid = remaining_ids[0]
            if target_qid not in question_ids:
                target_qid = remaining_ids[0]

            state.process_logs.append({
                "turn": state.used_turns + 1,
                "stage": stage["stage_name"],
                "remaining_ids": remaining_ids,
                "action_raw": action_obj,
                "action": action,
                "target_question_id": target_qid,
            })

            if action == "plan" and state.plan_used < plan_limit:
                plan = interviewer.generate_plan(state.history)
                state.process_logs.append({"turn": state.used_turns + 1, "stage": stage["stage_name"], "action": "plan", "plan": plan})
                state.plan_used += 1
                state.used_turns += 1
                continue

            if action == "conclude":
                state.terminated_reason = "conclude"
                break

            if action == "skip_question":
                state.skipped_ids.append(target_qid)
                state.decisions.append({
                    "turn": state.used_turns + 1,
                    "action": action,
                    "reason_tag": reason_tag,
                    "note": note,
                    "target_question_id": target_qid,
                    "stage": stage["stage_name"],
                    "event": None,
                })
                state.used_turns += 1
                continue

            question = questions_by_id[target_qid]
            interviewer_utt = interviewer.generate_response(action, reason_tag, question, state.history)
            state.history.append({"role": "interviewer", "content": interviewer_utt})
            interviewee_utt, event = interviewee.respond(target_qid, interviewer_utt, state.history)
            state.history.append({"role": "interviewee", "content": interviewee_utt})
            if event and event.get("event_type") and event.get("event_type") != "none":
                event_type = event.get("event_type")
                state.event_counts[event_type] = state.event_counts.get(event_type, 0) + 1
                state.event_total += 1
            sufficient_now = self._is_answer_sufficient(question, interviewee_utt, event)
            recovery_meta = recovery_engine.apply(target_qid, event, sufficient_now, state.state_tracker)
            state.decisions.append({
                "turn": state.used_turns + 1,
                "action": action,
                "reason_tag": reason_tag,
                "note": note,
                "target_question_id": target_qid,
                "stage": stage["stage_name"],
                "event": event,
                **recovery_meta,
            })
            state.attempt_counter[target_qid] = state.attempt_counter.get(target_qid, 0) + 1
            state.used_turns += 1

            if state.free_chat_used < free_chat_turn_limit and state.used_turns % 5 == 0 and state.used_turns < max_turns:
                free_q = interviewer.generate_free_followup(question, state.history)
                state.history.append({"role": "interviewer", "content": free_q})
                free_a, free_event = interviewee.respond(target_qid, free_q, state.history)
                state.history.append({"role": "interviewee", "content": free_a})
                state.free_chat_used += 1
                state.used_turns += 1
                free_sufficient = self._is_answer_sufficient(question, free_a, free_event)
                free_recovery_meta = recovery_engine.apply(target_qid, free_event, free_sufficient, state.state_tracker)
                if free_event and free_event.get("event_type") and free_event.get("event_type") != "none":
                    event_type = free_event.get("event_type")
                    state.event_counts[event_type] = state.event_counts.get(event_type, 0) + 1
                    state.event_total += 1
                state.decisions.append({
                    "turn": state.used_turns,
                    "action": "free_followup",
                    "reason_tag": "continuity",
                    "note": "free turn",
                    "target_question_id": target_qid,
                    "stage": stage["stage_name"],
                    "event": free_event,
                    **free_recovery_meta,
                })

            if action in ["ask_question", "follow_up", "clarify"]:
                if sufficient_now and target_qid not in state.answered_ids:
                    state.answered_ids.append(target_qid)
                elif not sufficient_now and state.attempt_counter.get(target_qid, 0) >= max_retry_per_q and target_qid not in state.deferred_ids:
                    state.deferred_ids.append(target_qid)

        if state.used_turns >= max_turns:
            state.terminated_reason = "max_turns"

        if not state.terminated_reason:
            state.terminated_reason = "normal"

        filled = filler.fill(questionnaire, state.history)
        score = scorer.score(questionnaire, filled, ground_truth)
        if compare_fill_modes:
            filled_direct = filler_direct.fill(questionnaire, state.history)
            score_direct = scorer.score(questionnaire, filled_direct, ground_truth)
            filled_summary = filler_summary.fill(questionnaire, state.history)
            score_summary = scorer.score(questionnaire, filled_summary, ground_truth)
        else:
            filled_direct = filled if ablation_mode != "summary" else None
            score_direct = score if ablation_mode != "summary" else None
            filled_summary = filled if ablation_mode == "summary" else None
            score_summary = score if ablation_mode == "summary" else None
        final_profile = final_profiler.build(questionnaire, filled, state.history)
        process_metrics = process_evaluator.evaluate(questionnaire, state.history, state.decisions, state.event_total, state.used_turns)
        conversation_record = {
            "run_id": run_id,
            "benchmark_dir": benchmark_dir,
            "survey_name": questionnaire.get("survey_name"),
            "interviewer_model": interviewer_model,
            "interviewee_model": interviewee_model,
            "handling_mode": handling_mode,
            "ablation_mode": ablation_mode,
            "compare_fill_modes": compare_fill_modes,
            "max_turns": max_turns,
            "used_turns": state.used_turns,
            "turn_count": state.used_turns,
            "terminated_reason": state.terminated_reason,
            "no_event_mode": no_event_mode,
            "event_trigger_prob": event_trigger_prob,
            "free_chat_turn_limit": free_chat_turn_limit,
            "free_chat_used": state.free_chat_used,
            "decisions": state.decisions,
            "process_logs": state.process_logs,
            "event_total": state.event_total,
            "event_count": state.event_total,
            "event_counts": state.event_counts,
            "questionnaire_summary": q_sum,
            "final_profile": final_profile,
            "process_metrics": process_metrics,
            "history": state.history,
            "warnings": [warning.to_dict() for warning in warnings],
        }
        questionnaire_record = {
            "run_id": run_id,
            "benchmark_dir": benchmark_dir,
            "survey_name": questionnaire.get("survey_name"),
            "interviewer_model": interviewer_model,
            "interviewee_model": interviewee_model,
            "handling_mode": handling_mode,
            "ablation_mode": ablation_mode,
            "compare_fill_modes": compare_fill_modes,
            "questionnaire": filled,
            "questionnaire_direct": filled_direct,
            "questionnaire_summary_mode": filled_summary,
        }
        score_record = {
            "run_id": run_id,
            "benchmark_dir": benchmark_dir,
            "survey_name": questionnaire.get("survey_name"),
            "interviewer_model": interviewer_model,
            "interviewee_model": interviewee_model,
            "model_name": interviewer_model,
            "handling_mode": handling_mode,
            "ablation_mode": ablation_mode,
            "compare_fill_modes": compare_fill_modes,
            "score": score,
            "score_direct": score_direct,
            "score_summary": score_summary,
            "score_delta_summary_minus_direct": round(score_summary.get("score", 0) - score_direct.get("score", 0), 4) if (score_summary and score_direct) else None,
            "event_total": state.event_total,
            "event_counts": state.event_counts,
            "process_metrics": process_metrics,
        }
        return RunResult(
            conversation_record=conversation_record,
            questionnaire_record=questionnaire_record,
            score_record=score_record,
            final_profile=final_profile,
            process_metrics=process_metrics,
            warnings=warnings,
            errors=errors,
        )
