from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class DictSerializable:
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelConfig(DictSerializable):
    name: str
    api_key: str
    base_url: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        api_key = str(data.get("api_key", "") or "").strip()
        api_key_env = str(data.get("api_key_env", "") or "").strip()
        if api_key_env:
            api_key = os.environ.get(api_key_env, "").strip()
        return cls(
            name=str(data.get("name", "")),
            api_key=api_key,
            base_url=str(data.get("base_url", "")),
        )


@dataclass
class WarningRecord(DictSerializable):
    code: str
    message: str
    detail: Optional[str] = None


@dataclass
class ErrorRecord(DictSerializable):
    code: str
    message: str
    detail: Optional[str] = None
