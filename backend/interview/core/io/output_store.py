from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_store import append_jsonl, load_jsonl


class OutputStore:
    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_path = self.output_dir / "conversation_result.jsonl"
        self.questionnaire_path = self.output_dir / "questionnaire_result.jsonl"
        self.score_path = self.output_dir / "score_result.jsonl"

    def append_conversation_record(self, record: Dict[str, Any]) -> None:
        append_jsonl(self.conversation_path, record)

    def append_questionnaire_record(self, record: Dict[str, Any]) -> None:
        append_jsonl(self.questionnaire_path, record)

    def append_score_record(self, record: Dict[str, Any]) -> None:
        append_jsonl(self.score_path, record)

    def read_conversation_records(self) -> List[Dict[str, Any]]:
        if not self.conversation_path.exists():
            return []
        return load_jsonl(self.conversation_path)

    def read_questionnaire_records(self) -> List[Dict[str, Any]]:
        if not self.questionnaire_path.exists():
            return []
        return load_jsonl(self.questionnaire_path)

    def read_score_records(self) -> List[Dict[str, Any]]:
        if not self.score_path.exists():
            return []
        return load_jsonl(self.score_path)

    def read_output_record(
        self,
        record_type: str,
        benchmark_dir: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        readers = {
            "conversation": self.read_conversation_records,
            "questionnaire": self.read_questionnaire_records,
            "score": self.read_score_records,
        }
        reader = readers.get(record_type)
        if reader is None:
            return []
        records = reader()
        out: List[Dict[str, Any]] = []
        for row in records:
            if benchmark_dir and row.get("benchmark_dir") != benchmark_dir:
                continue
            row_model = row.get("interviewer_model") or row.get("model_name")
            if model_name and row_model != model_name:
                continue
            out.append(row)
        return out
