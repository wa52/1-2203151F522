from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


LOCKED_FACT_MAP = {
    "age": ("age", 23),
    "office_work": ("daily_role_context", "company_office_worker"),
}

SOFT_MAP = {
    "ordinary_presentation": "日常形象应保持普通、低主角光环；不能把“普通”直接翻译成固定脸型或颜值等级。",
    "calm_in_home_scene": "家庭异常场景中的表演应偏克制、平静；这不是“没有情感”。",
}


def evidence_refs(item: dict[str, Any]) -> list[dict[str, Any]]:
    refs = []
    for ev in item.get("evidence", []):
        refs.append({
            "chapter_id": ev["chapter_id"],
            "chapter_title": ev["chapter_title"],
            "chunk_id": ev["chunk_id"],
            "line_start": ev["line_start"],
            "line_end": ev["line_end"],
        })
    return refs


def build_contract(profile: dict[str, Any]) -> dict[str, Any]:
    hard_by_id = {item["id"]: item for item in profile.get("hard_facts", [])}
    soft_by_id = {item["id"]: item for item in profile.get("performance_evidence", [])}

    locked_facts = []
    for source_id, (feature, value) in LOCKED_FACT_MAP.items():
        item = hard_by_id.get(source_id)
        if not item:
            continue
        refs = evidence_refs(item)
        if not refs:
            raise ValueError(f"locked fact {source_id!r} has no evidence anchors")
        locked_facts.append({
            "feature": feature,
            "value": value,
            "source_fact_id": source_id,
            "confidence": item.get("confidence", 0.0),
            "evidence": refs,
        })

    soft_constraints = []
    for source_id, instruction in SOFT_MAP.items():
        item = soft_by_id.get(source_id)
        if not item:
            continue
        soft_constraints.append({
            "feature": source_id,
            "instruction": instruction,
            "confidence": item.get("confidence", 0.0),
            "evidence": evidence_refs(item),
        })

    visual = profile.get("visual_evidence_candidates", {})
    unresolved = list(visual.get("not_yet_locked", []))

    locked_names = {item["feature"] for item in locked_facts}
    conflict = locked_names.intersection(unresolved)
    if conflict:
        raise ValueError(f"features cannot be both locked and unresolved: {sorted(conflict)}")

    raw = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return {
        "schema_version": "character-canon-contract/1",
        "character": {
            "id": profile["character_id"],
            "name": profile["name"],
        },
        "provenance": {
            "source_profile": "canon/lu_xin.profile.json",
            "source_profile_schema": profile.get("schema_version"),
            "source_profile_sha256": hashlib.sha256(raw).hexdigest(),
            "contains_novel_passages": False,
        },
        "locked_facts": locked_facts,
        "soft_constraints": soft_constraints,
        "unresolved_visual_features": unresolved,
        "forbidden_interpretations": list(profile.get("forbidden_inferences", [])),
        "acceptance_rules": [
            "Every locked fact must retain at least one chapter/chunk/line evidence anchor.",
            "Unresolved visual features remain modifiable until a reviewed Canon fact locks them.",
            "Soft constraints guide visual direction but never become literal appearance facts automatically.",
            "No novel passages are embedded in this contract; only evidence pointers are exported.",
        ],
    }


def validate_contract(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "character-canon-contract/1":
        raise ValueError("unsupported contract schema")
    if contract.get("provenance", {}).get("contains_novel_passages") is not False:
        raise ValueError("contract must not contain novel passages")
    for item in contract.get("locked_facts", []):
        if not item.get("evidence"):
            raise ValueError(f"locked feature {item.get('feature')} lacks evidence")
        for ref in item["evidence"]:
            for key in ("chapter_id", "chapter_title", "chunk_id", "line_start", "line_end"):
                if key not in ref:
                    raise ValueError(f"evidence anchor missing {key}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a public, passage-free character Canon contract.")
    parser.add_argument("--profile", type=Path, default=Path("canon/lu_xin.profile.json"))
    parser.add_argument("--output", type=Path, default=Path("canon/lu_xin.character_contract.json"))
    args = parser.parse_args()

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    contract = build_contract(profile)
    validate_contract(contract)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "character": contract["character"]["name"],
        "locked_fact_count": len(contract["locked_facts"]),
        "soft_constraint_count": len(contract["soft_constraints"]),
        "unresolved_visual_feature_count": len(contract["unresolved_visual_features"]),
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
