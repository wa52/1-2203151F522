from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


NAME_RE = re.compile(r"(?<![一-鿿])([一-鿿]{2,3})(?![一-鿿])")
ACTION_TERMS = (
    "说道", "说着", "问道", "回答", "笑道", "叫道", "喊道", "点头", "摇头",
    "皱眉", "看着", "看向", "走来", "走了过来", "坐下", "站起", "抬头", "低头",
    "开口", "沉默", "笑了", "叹了口气", "转头", "望向",
)
STOPWORDS = {
    "自己", "他们", "她们", "我们", "你们", "这个", "那个", "什么", "怎么", "时候",
    "已经", "还是", "只是", "就是", "因为", "所以", "但是", "然后", "这样", "那样",
    "这里", "那里", "现在", "以前", "之后", "之前", "里面", "外面", "起来", "过去",
    "过来", "下来", "上去", "一下", "一点", "一种", "两个", "三个", "一个", "这些",
    "那些", "没有", "不是", "可以", "可能", "感觉", "知道", "看到", "看见", "听到",
    "声音", "眼睛", "目光", "脑袋", "身体", "脸上", "心里", "手里", "身边", "面前",
    "公司", "办公室", "城市", "世界", "精神", "污染", "能力", "事情", "问题", "任务",
    "先生", "女士", "小姐", "队长", "教授", "医生", "主任", "经理", "组长",
}
BAD_SUFFIXES = (
    "时候", "地方", "东西", "事情", "问题", "感觉", "声音", "眼睛", "目光", "脸上",
    "手里", "心里", "里面", "外面", "身边", "面前", "之后", "之前",
)


def plausible_name(token: str) -> bool:
    if token in STOPWORDS:
        return False
    if any(token.endswith(suffix) for suffix in BAD_SUFFIXES):
        return False
    if len(set(token)) == 1:
        return False
    return 2 <= len(token) <= 3


def action_hits(text: str, name: str, window: int = 24) -> int:
    count = 0
    start = 0
    while True:
        index = text.find(name, start)
        if index < 0:
            return count
        left = max(0, index - window)
        right = min(len(text), index + len(name) + window)
        context = text[left:right]
        if any(term in context for term in ACTION_TERMS):
            count += 1
        start = index + len(name)


def discover(
    chunks_path: Path,
    *,
    min_mentions: int = 20,
    min_chapters: int = 5,
    limit: int = 80,
) -> dict[str, Any]:
    mentions: Counter[str] = Counter()
    chapters: dict[str, set[str]] = defaultdict(set)
    action_contexts: Counter[str] = Counter()
    first_seen: dict[str, dict[str, Any]] = {}

    with chunks_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            text = str(row.get("text", ""))
            chapter_id = str(row.get("chapter_id", ""))
            chapter_title = str(row.get("chapter_title", ""))
            chunk_id = str(row.get("chunk_id", ""))

            local_counts = Counter(
                token
                for token in NAME_RE.findall(text)
                if plausible_name(token)
            )
            for token, count in local_counts.items():
                mentions[token] += count
                chapters[token].add(chapter_id)
                action_contexts[token] += action_hits(text, token)
                first_seen.setdefault(
                    token,
                    {
                        "chapter_id": chapter_id,
                        "chapter_title": chapter_title,
                        "chunk_id": chunk_id,
                    },
                )

    candidates = []
    for token, total in mentions.items():
        spread = len(chapters[token])
        actions = action_contexts[token]
        if total < min_mentions or spread < min_chapters:
            continue

        action_ratio = actions / total if total else 0.0
        # Conservative score: repeated cross-chapter presence matters most;
        # nearby speech/action context increases likelihood that token is a person.
        score = round(
            min(100.0, spread * 0.9 + total * 0.08 + min(actions, 120) * 0.35),
            2,
        )
        candidates.append(
            {
                "name": token,
                "status": "DISCOVERY_CANDIDATE",
                "mention_count": total,
                "chapter_count": spread,
                "action_context_count": actions,
                "action_context_ratio": round(action_ratio, 4),
                "score": score,
                "first_seen": first_seen[token],
                "review_required": True,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["chapter_count"],
            item["action_context_count"],
            item["mention_count"],
        ),
        reverse=True,
    )
    return {
        "schema_version": "character-discovery/1",
        "method": "cross-chapter-name-frequency-plus-nearby-dialogue-action-context",
        "policy": [
            "Discovery output is never Canon.",
            "Every candidate requires Canon review before registry creation.",
            "No novel passages are copied into this public metadata file.",
        ],
        "candidate_count": min(limit, len(candidates)),
        "candidates": candidates[:limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover likely character names from local private RAG chunks.")
    parser.add_argument(
        "--chunks",
        type=Path,
        default=Path("rag/private/chunks.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("canon/character_discovery.json"),
    )
    parser.add_argument("--min-mentions", type=int, default=20)
    parser.add_argument("--min-chapters", type=int, default=5)
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    result = discover(
        args.chunks,
        min_mentions=args.min_mentions,
        min_chapters=args.min_chapters,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_count": result["candidate_count"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
