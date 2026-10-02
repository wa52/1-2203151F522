from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def evidence_refs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs = []
    for item in items:
        refs.append({
            "chapter_id": item["chapter_id"],
            "chapter_title": item["chapter_title"],
            "chunk_id": item["chunk_id"],
            "line_start": item["line_start"],
            "line_end": item["line_end"],
        })
    return refs


def role_context_instruction(profile: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | None:
    role = profile.get("review_categories", {}).get("role_context", {})
    recurring = [
        item for item in role.get("recurring_terms", [])
        if int(item.get("anchor_count", 0)) >= 3
    ]
    if not recurring:
        return None
    terms = [str(item["term"]) for item in recurring[:8]]
    refs = evidence_refs(role.get("evidence", [])[:8])
    instruction = (
        "原著证据中该角色附近跨多个章节反复出现工作/组织语境词："
        + "、".join(terms)
        + "。生成日常形象时应与这一广义职业语境兼容；"
        "这些词只作为场景/气质方向，不能自动推导具体职级、制服、年龄或外貌。"
    )
    return instruction, refs


def build_contract(profile: dict[str, Any], source_profile: str) -> dict[str, Any]:
    raw = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    soft_constraints = []
    role = role_context_instruction(profile)
    if role:
        instruction, refs = role
        soft_constraints.append({
            "feature": "recurring_work_context",
            "instruction": instruction,
            "confidence": 0.68,
            "evidence": refs,
            "evidence_semantics": "lexical-context-only",
        })

    review_categories = {}
    for key in ("demeanor", "appearance", "clothing", "relationship_context"):
        item = profile.get("review_categories", {}).get(key, {})
        review_categories[key] = {
            "status": item.get("status", "SOURCE_REVIEW_REQUIRED"),
            "recurring_terms": list(item.get("recurring_terms", [])),
            "evidence": evidence_refs(item.get("evidence", [])[:12]),
        }

    unresolved = list(profile.get("visual_policy", {}).get("not_yet_locked", []))
    return {
        "schema_version": "character-canon-contract/1",
        "character": {
            "id": profile["character_id"],
            "name": profile["name"],
        },
        "provenance": {
            "source_profile": source_profile,
            "source_profile_schema": profile.get("schema_version"),
            "source_profile_sha256": hashlib.sha256(raw).hexdigest(),
            "contains_novel_passages": False,
        },
        "locked_facts": [],
        "soft_constraints": soft_constraints,
        "unresolved_visual_features": unresolved,
        "review_candidates": review_categories,
        "forbidden_interpretations": list(profile.get("forbidden_inferences", [])),
        "acceptance_rules": [
            "No visual feature is locked from lexical co-occurrence alone.",
            "Soft recurring_work_context is broad staging guidance, not a literal rank or costume fact.",
            "Appearance/clothing/demeanor review candidates require source-chunk review before promotion.",
            "Unresolved visual features remain modifiable.",
            "No novel passages are embedded in this contract; only evidence pointers are exported.",
        ],
    }


def validate(contract: dict[str, Any]) -> None:
    if contract.get("schema_version") != "character-canon-contract/1":
        raise ValueError("unsupported contract schema")
    if contract.get("provenance", {}).get("contains_novel_passages") is not False:
        raise ValueError("contract must remain passage-free")
    if contract.get("locked_facts"):
        raise ValueError("generic lexical review must not create hard locks")
    for item in contract.get("soft_constraints", []):
        if not item.get("evidence"):
            raise ValueError("soft constraint requires evidence anchors")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    contract = build_contract(profile, args.profile.as_posix())
    validate(contract)
    args.output.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "character": contract["character"]["name"],
        "locked_fact_count": 0,
        "soft_constraint_count": len(contract["soft_constraints"]),
        "unresolved_visual_feature_count": len(contract["unresolved_visual_features"]),
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
