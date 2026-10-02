from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


CATEGORIES = {
    "role_context": [
        "组长", "队长", "部长", "教授", "博士", "领导", "主管", "负责人",
        "特别行动组", "特清部", "总部", "调查", "联络", "信息", "办公室",
        "工作", "任务", "训练", "培训", "会议", "命令", "报告",
    ],
    "demeanor": [
        "冷静", "平静", "严肃", "认真", "谨慎", "果断", "温和", "礼貌",
        "客气", "沉默", "微笑", "笑", "皱眉", "冷淡", "紧张", "警惕",
    ],
    "appearance": [
        "模样", "长相", "脸", "脸庞", "眼睛", "目光", "头发", "发型",
        "身材", "个子", "高挑", "瘦", "胖", "漂亮", "美丽", "年轻",
        "年纪", "年龄", "男人", "女人", "女孩", "青年",
    ],
    "clothing": [
        "衣服", "衣着", "衬衫", "外套", "风衣", "制服", "西装", "裙子",
        "长裙", "短裙", "裤子", "鞋", "高跟鞋", "眼镜", "帽子",
    ],
    "relationship_context": [
        "陆辛", "同事", "朋友", "队友", "下属", "上司", "领导", "同伴",
        "哥哥", "姐姐", "妹妹", "父亲", "母亲", "家人",
    ],
}


def load_chunks(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def nearby_hits(text: str, subject: str, terms: list[str], radius: int = 160) -> list[str]:
    hits = set()
    start = 0
    while True:
        pos = text.find(subject, start)
        if pos < 0:
            break
        window = text[max(0, pos-radius):min(len(text), pos+len(subject)+radius)]
        hits.update(term for term in terms if term in window)
        start = pos + len(subject)
    return sorted(hits)


def anchor(row: dict[str, Any], *, hits: list[str], reason: str) -> dict[str, Any]:
    return {
        "chapter_id": row["chapter_id"],
        "chapter_title": row["chapter_title"],
        "chunk_id": row["chunk_id"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "matched_terms": hits,
        "reason": reason,
    }


def category_evidence(
    chunks: list[dict[str, Any]],
    character: str,
    terms: list[str],
    *,
    min_hits: int = 1,
    limit: int = 10,
    reason: str,
) -> list[dict[str, Any]]:
    ranked = []
    for row in chunks:
        text = str(row.get("text", ""))
        if character not in text:
            continue
        hits = nearby_hits(text, character, terms)
        if len(hits) < min_hits:
            continue
        ranked.append((len(hits), text.count(character), row, hits))
    ranked.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [
        anchor(row, hits=hits, reason=reason)
        for _, _, row, hits in ranked[:limit]
    ]


def identity_evidence(chunks: list[dict[str, Any]], character: str, limit: int = 8) -> list[dict[str, Any]]:
    ranked = []
    for row in chunks:
        text = str(row.get("text", ""))
        count = text.count(character)
        if count:
            ranked.append((count, row))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [
        anchor(row, hits=[character], reason="角色名在该 chunk 中重复出现")
        for _, row in ranked[:limit]
    ]


def recurring_terms(evidence: list[dict[str, Any]], minimum_anchors: int = 3) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in evidence:
        for term in set(item.get("matched_terms", [])):
            counts[term] = counts.get(term, 0) + 1
    return [
        {"term": term, "anchor_count": count}
        for term, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        if count >= minimum_anchors
    ]


def build_profile(
    chunks: list[dict[str, Any]],
    *,
    character: str,
    character_id: str,
    slug: str,
) -> dict[str, Any]:
    evidence_map = {
        key: category_evidence(
            chunks,
            character,
            terms,
            min_hits=2 if key in {"role_context", "appearance"} else 1,
            limit=12 if key == "appearance" else 10,
            reason=f"{character}附近出现{key}相关词；仅作为定向 Canon 审查证据",
        )
        for key, terms in CATEGORIES.items()
    }
    recurring = {
        key: recurring_terms(items, minimum_anchors=3)
        for key, items in evidence_map.items()
    }

    return {
        "schema_version": "generic-character-profile/1",
        "character_id": character_id,
        "name": character,
        "source": {
            "corpus": "cleaned/novel.cleaned.txt",
            "index": "rag/private/chunks.jsonl",
            "contains_novel_passages": False,
        },
        "identity_presence": {
            "status": "TEXT_CONFIRMED_IN_COPY",
            "evidence": identity_evidence(chunks, character),
        },
        "review_categories": {
            key: {
                "status": "SOURCE_REVIEW_REQUIRED",
                "evidence": items,
                "recurring_terms": recurring[key],
            }
            for key, items in evidence_map.items()
        },
        "visual_policy": {
            "not_yet_locked": [
                "age",
                "face_shape",
                "hairstyle",
                "eye_shape",
                "body_proportions",
                "height",
                "default_clothing",
                "attractiveness",
                "default_expression",
                "default_posture",
            ],
            "rule": "No appearance feature becomes Canon from term co-occurrence alone.",
        },
        "forbidden_inferences": [
            "不能从角色重要性推导颜值、英雄感或固定镜头语言。",
            "不能把战斗/异常场景中的临时表演当成默认气质。",
            "不能把职业或组织词直接转换成固定服装，除非正文有明确反复证据。",
            "没有明确正文描述前，不锁定年龄、脸型、发型、眼型、身材、身高和默认服装。",
        ],
        "next_review": [
            "Canon Agent读取 role_context / demeanor / appearance / clothing 最强证据 chunk。",
            "只把正文明确描述、且与角色主体关系清楚的事实提升为 Canon。",
            "冲突描述必须保留章节/时期范围，不能强行合并。",
        ],
        "output_hint": f"canon/{slug}.character_contract.json",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=Path("rag/private/chunks.jsonl"))
    parser.add_argument("--character", required=True)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    profile = build_profile(
        load_chunks(args.index),
        character=args.character,
        character_id=args.character_id,
        slug=args.slug,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "character": args.character,
        "profile_sha256": hashlib.sha256(
            json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
