from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


def slug(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    ascii_part = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return ascii_part or f"char-{digest}"


def build_drafts(discovery: dict[str, Any]) -> dict[str, Any]:
    drafts = []
    for item in discovery.get("candidates", []):
        if not item.get("recommended_for_canon_review"):
            continue
        name = str(item["name"])
        drafts.append(
            {
                "draft_id": slug(name),
                "name": name,
                "candidate_kind": item.get("candidate_kind"),
                "status": "CANON_REVIEW_REQUIRED",
                "discovery_score": item.get("score"),
                "mention_count": item.get("mention_count"),
                "chapter_count": item.get("chapter_count"),
                "subject_action_hits": item.get("subject_action_hits"),
                "self_intro_hits": item.get("self_intro_hits"),
                "first_seen": item.get("first_seen"),
                "canon_contract": None,
                "base_state": None,
                "registry_ready": False,
                "next_action": "Build an evidence-bound Canon Profile/Contract before character generation.",
            }
        )
    return {
        "schema_version": "character-drafts/1",
        "source_schema": discovery.get("schema_version"),
        "policy": [
            "Drafts are discovery metadata, not Canon.",
            "No appearance or personality fact is created from frequency statistics.",
            "registry_ready remains false until an evidence-bound Canon Contract exists.",
        ],
        "draft_count": len(drafts),
        "drafts": drafts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discovery",
        type=Path,
        default=Path("canon/character_discovery.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("canon/character_drafts.json"),
    )
    args = parser.parse_args()

    discovery = json.loads(args.discovery.read_text(encoding="utf-8"))
    result = build_drafts(discovery)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"draft_count": result["draft_count"], "output": str(args.output)},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
