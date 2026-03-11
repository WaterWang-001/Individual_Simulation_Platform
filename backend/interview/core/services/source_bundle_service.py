from __future__ import annotations

import os
from typing import Dict, List, Tuple


class SourceBundleService:
    @staticmethod
    def discover_dataset_pairs(root_dir: str) -> List[Tuple[str, str]]:
        pairs = []
        for dirpath, _, filenames in os.walk(root_dir):
            q_files = [f for f in filenames if f.startswith("questionnaire") or f.startswith("questionaire")]
            s_files = [f for f in filenames if f.startswith("sample")]
            if not q_files or not s_files:
                continue
            for qf in q_files:
                for sf in s_files:
                    pairs.append((os.path.join(dirpath, qf), os.path.join(dirpath, sf)))
                    break
        return pairs

    @staticmethod
    def discover_source_bundles(root_dir: str) -> List[Dict[str, str]]:
        bundles: List[Dict[str, str]] = []
        if not os.path.exists(root_dir):
            return bundles
        for name in sorted(os.listdir(root_dir)):
            bundle_dir = os.path.join(root_dir, name)
            if not os.path.isdir(bundle_dir):
                continue
            template_path = os.path.join(bundle_dir, "questionnaire_template.json")
            records_path = os.path.join(bundle_dir, "records.jsonl")
            meta_path = os.path.join(bundle_dir, "meta.json")
            if os.path.exists(template_path) and os.path.exists(records_path):
                bundles.append(
                    {
                        "dataset_name": name,
                        "template_path": template_path,
                        "records_path": records_path,
                        "meta_path": meta_path,
                    }
                )
        return bundles
