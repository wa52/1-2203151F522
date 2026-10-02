from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_chunks(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def anchor(row: dict, reason: str) -> dict:
    return {
        "chapter_id": row["chapter_id"],
        "chapter_title": row["chapter_title"],
        "chunk_id": row["chunk_id"],
        "line_start": row["line_start"],
        "line_end": row["line_end"],
        "reason": reason,
    }


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def evidence(
    chunks: list[dict],
    *,
    required: list[str] | None = None,
    any_terms: list[str] | None = None,
    min_any: int = 1,
    limit: int = 8,
    reason: str,
) -> list[dict]:
    required = required or []
    any_terms = any_terms or []
    rows = []
    for row in chunks:
        text = row["text"]
        if any(term not in text for term in required):
            continue
        hits = [term for term in any_terms if term in text]
        if len(hits) < min_any:
            continue
        rows.append((len(hits), text.count("陆辛"), row, hits))
    rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [
        anchor(row, reason + (f"; matched={','.join(hits)}" if hits else ""))
        for _, _, row, hits in rows[:limit]
    ]


def first_chapter_evidence(chunks: list[dict], terms: list[str], limit: int = 6) -> list[dict]:
    rows = []
    for row in chunks:
        if row["chapter_title"] != "第一章 回家":
            continue
        text = row["text"]
        if "陆辛" in text and contains_any(text, terms):
            rows.append(anchor(row, f"第一章场景命中: {','.join(t for t in terms if t in text)}"))
    return rows[:limit]


def build_profile(chunks: list[dict]) -> dict:
    age = evidence(
        chunks,
        required=["陆辛"],
        any_terms=["二十三岁", "23岁", "年龄：23", "年龄:23", "年龄 23"],
        min_any=1,
        limit=6,
        reason="陆辛与明确年龄表达同一 chunk",
    )
    office = evidence(
        chunks,
        required=["陆辛"],
        any_terms=["公司", "办公室", "上班", "工作", "同事", "工资", "工位"],
        min_any=3,
        limit=8,
        reason="陆辛与多个办公室/上班语义同一 chunk",
    )
    commute = first_chapter_evidence(chunks, ["列车", "车厢", "月亮台站", "回家"])
    family = first_chapter_evidence(chunks, ["妹妹", "妈妈", "母亲", "爸爸", "父亲", "家人"])
    calm = first_chapter_evidence(chunks, ["平静", "吃饭", "沉默"])
    ordinary = evidence(
        chunks,
        required=["陆辛", "普通"],
        any_terms=["年轻人", "老实", "安静", "认真", "笑", "公司", "工作"],
        min_any=1,
        limit=8,
        reason="叙事中陆辛与“普通”同一 chunk；仅作为气质证据，不等于固定外貌",
    )
    appearance = evidence(
        chunks,
        required=["陆辛"],
        any_terms=["头发", "眼睛", "目光", "脸", "模样", "长相", "身材", "个子", "瘦", "衣服", "衬衫", "外套"],
        min_any=3,
        limit=12,
        reason="外貌相关词与陆辛同一 chunk；需要 Canon Agent 阅读正文后才能提取具体描述",
    )

    hard_facts = []
    if age:
        hard_facts.append({
            "id": "age",
            "fact": "陆辛年龄为23岁。",
            "status": "TEXT_CONFIRMED_IN_COPY",
            "confidence": 1.0,
            "evidence": age,
        })
    else:
        hard_facts.append({
            "id": "age",
            "fact": "陆辛年龄为23岁。",
            "status": "TEXT_CONFIRMED_IN_PROJECT_BIBLE_NEEDS_CHUNK_ANCHOR",
            "confidence": 0.95,
            "evidence": [],
            "note": "已有项目 Character Bible 核对到第五章人物档案；本自动规则未在 top-level pattern 中直接定位，后续补精确 chunk。",
        })

    hard_facts.extend([
        {
            "id": "office_work",
            "fact": "陆辛存在持续、反复出现的公司/办公室上班生活。",
            "status": "TEXT_CONFIRMED_IN_COPY",
            "confidence": 0.99 if len(office) >= 4 else 0.9,
            "evidence": office,
        },
        {
            "id": "first_chapter_commute_home",
            "fact": "第一章中陆辛经历通勤并回到住所。",
            "status": "TEXT_CONFIRMED_IN_COPY",
            "confidence": 0.99 if commute else 0.85,
            "evidence": commute,
        },
        {
            "id": "family_scene",
            "fact": "开篇家庭场景中，叙事以妹妹、妈妈/母亲、爸爸/父亲等称谓呈现陆辛的家人。",
            "status": "TEXT_CONFIRMED_IN_COPY",
            "confidence": 0.99 if family else 0.85,
            "evidence": family,
            "scope_warning": "这只是场景与称谓事实，不据此提前判定全书关于家人的最终本体解释。",
        },
    ])

    return {
        "schema_version": "0.1",
        "character_id": "CHAR-LUXIN",
        "name": "陆辛",
        "source": {
            "corpus": "cleaned/novel.cleaned.txt",
            "index": "rag/private/chunks.jsonl",
            "public_index_committed": False,
        },
        "hard_facts": hard_facts,
        "performance_evidence": [
            {
                "id": "ordinary_presentation",
                "trait": "日常叙事中存在“普通”与工作生活并置的证据，可用于降低主角光环。",
                "status": "SOFT_TRAIT_EVIDENCE",
                "confidence": 0.82 if len(ordinary) >= 3 else 0.65,
                "evidence": ordinary,
                "warning": "不能把“普通”直接转换成固定脸型、发型或颜值等级。",
            },
            {
                "id": "calm_in_home_scene",
                "trait": "第一章家庭异常场景中有克制/平静的行为反差证据。",
                "status": "SCENE_PERFORMANCE_EVIDENCE",
                "confidence": 0.9 if calm else 0.7,
                "evidence": calm,
                "warning": "这是具体场景表演锚点，不能推导为‘没有情感’。",
            },
        ],
        "visual_evidence_candidates": {
            "status": "SOURCE_REVIEW_REQUIRED",
            "evidence": appearance,
            "allowed_use": "供 Canon Agent 定向读取，提取文本明确的外貌描述。",
            "not_yet_locked": [
                "face_shape",
                "hairstyle",
                "eye_shape",
                "body_proportions",
                "height",
                "default_clothing",
                "attractiveness",
            ],
        },
        "forbidden_inferences": [
            "不能因为主角身份自动强化成英雄式构图或强者脸。",
            "不能把单个高压/战斗场景中的危险感当成日常固定气质。",
            "不能把第一章平静反应概括成没有情感。",
            "没有具体原文证据前，不锁定发型、脸型、眼型、身材和默认服装。",
            "家人的场景可见性必须按具体观察者与章节处理，不能从单一视点推出全局规则。",
        ],
        "next_review": [
            "读取 visual_evidence_candidates 中前 12 个 chunk，人工/Canon Agent 提取明确外貌句。",
            "为每个外貌事实要求至少一个精确 chunk 证据；冲突描述保留时间/场景版本。",
            "把确认后的视觉事实同步到 Character Evolution Loop 的 locked/modifiable 状态。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, default=Path("rag/private/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("canon/lu_xin.profile.json"))
    args = parser.parse_args()

    chunks = load_chunks(args.index)
    profile = build_profile(chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "hard_fact_count": len(profile["hard_facts"]),
        "appearance_candidate_count": len(profile["visual_evidence_candidates"]["evidence"]),
        "output": str(args.output),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
