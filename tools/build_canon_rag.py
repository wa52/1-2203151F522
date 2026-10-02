from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path


CHAPTER_RE = re.compile(
    r"^\s*(?P<title>(?:第[零〇一二三四五六七八九十百千万两\d]+章[^\n]*|引子[^\n]*|序章[^\n]*|番外[^\n]*))\s*$"
)
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
CJK_RE = re.compile(r"[\u3400-\u9fff]")

CATEGORY_TERMS = {
    "identity": ["陆辛", "二十三岁", "23岁", "年轻人"],
    "appearance": ["模样", "长相", "脸", "眼睛", "目光", "头发", "身材", "个子", "瘦", "衣服", "衬衫", "外套"],
    "occupation": ["公司", "办公室", "工作", "上班", "同事", "职员", "文员", "工位", "工资", "通勤", "经理"],
    "demeanor": ["礼貌", "客气", "平静", "安静", "认真", "老实", "沉默", "笑", "谨慎", "普通", "低调"],
    "family": ["妹妹", "妈妈", "母亲", "爸爸", "父亲", "家人", "回家", "家里"],
    "social_reaction": ["看他", "看着他", "望着他", "觉得他", "同事", "别人", "旁人"],
    "abnormality": ["异常", "污染", "精神", "怪物", "能力", "异变", "观察", "危险"],
}


@dataclass(slots=True)
class Chapter:
    chapter_id: str
    title: str
    start_line: int
    end_line: int
    paragraphs: list[tuple[int, str]]


@dataclass(slots=True)
class Chunk:
    chunk_id: str
    chapter_id: str
    chapter_title: str
    line_start: int
    line_end: int
    text: str


def split_chapters(text: str) -> list[Chapter]:
    lines = text.splitlines()
    headings: list[tuple[int, str]] = []
    for idx, line in enumerate(lines, start=1):
        match = CHAPTER_RE.match(line)
        if match:
            headings.append((idx, match.group("title").strip()))

    if not headings:
        paragraphs = [(i, line.strip()) for i, line in enumerate(lines, start=1) if line.strip()]
        return [Chapter("ch-0001", "全文", 1, len(lines), paragraphs)]

    chapters: list[Chapter] = []
    for pos, (line_no, title) in enumerate(headings):
        next_line = headings[pos + 1][0] if pos + 1 < len(headings) else len(lines) + 1
        paragraphs = [
            (i, lines[i - 1].strip())
            for i in range(line_no + 1, next_line)
            if lines[i - 1].strip()
        ]
        chapters.append(
            Chapter(
                chapter_id=f"ch-{pos + 1:04d}",
                title=title,
                start_line=line_no,
                end_line=next_line - 1,
                paragraphs=paragraphs,
            )
        )
    return chapters


def chunk_chapter(chapter: Chapter, target_chars: int = 900, overlap_paragraphs: int = 1) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[tuple[int, str]] = []

    def emit() -> None:
        nonlocal current
        if not current:
            return
        idx = len(chunks) + 1
        chunks.append(
            Chunk(
                chunk_id=f"{chapter.chapter_id}-ck-{idx:03d}",
                chapter_id=chapter.chapter_id,
                chapter_title=chapter.title,
                line_start=current[0][0],
                line_end=current[-1][0],
                text="\n".join(p for _, p in current),
            )
        )

    for paragraph in chapter.paragraphs:
        projected = sum(len(p) for _, p in current) + len(paragraph[1])
        if current and projected > target_chars:
            emit()
            current = current[-overlap_paragraphs:] if overlap_paragraphs else []
        current.append(paragraph)
    emit()
    return chunks


def tokenize(text: str) -> list[str]:
    tokens = [m.group(0).lower() for m in ASCII_WORD_RE.finditer(text)]
    cjk = [ch for ch in text if CJK_RE.match(ch)]
    tokens.extend(cjk)
    tokens.extend(a + b for a, b in zip(cjk, cjk[1:]))
    return tokens


def write_index(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for chunk in chunks:
            row = asdict(chunk)
            row["token_counts"] = dict(Counter(tokenize(chunk.text)))
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def index_report(chapters: list[Chapter], chunks: list[Chunk]) -> dict:
    lengths = [len(chunk.text) for chunk in chunks]
    return {
        "chapter_count": len(chapters),
        "chunk_count": len(chunks),
        "first_chapter": chapters[0].title if chapters else None,
        "last_chapter": chapters[-1].title if chapters else None,
        "chunk_chars": {
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "avg": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        },
        "index_path": "rag/private/chunks.jsonl",
        "index_committed": False,
    }


def build_character_candidates(chunks: list[Chunk], character: str, limit: int = 120) -> dict:
    rows = []
    for chunk in chunks:
        if character not in chunk.text:
            continue
        matched = {}
        score = chunk.text.count(character) * 4
        for category, terms in CATEGORY_TERMS.items():
            hits = sorted({term for term in terms if term in chunk.text})
            if hits:
                matched[category] = hits
                score += len(hits) * (3 if category != "identity" else 1)

        rows.append({
            "chunk_id": chunk.chunk_id,
            "chapter_id": chunk.chapter_id,
            "chapter_title": chunk.chapter_title,
            "line_start": chunk.line_start,
            "line_end": chunk.line_end,
            "character_mentions": chunk.text.count(character),
            "categories": matched,
            "score": score,
        })

    rows.sort(key=lambda row: (row["score"], row["character_mentions"]), reverse=True)
    category_counts = Counter()
    for row in rows:
        category_counts.update(row["categories"].keys())

    return {
        "character": character,
        "candidate_count": len(rows),
        "returned": min(limit, len(rows)),
        "category_chunk_counts": dict(category_counts),
        "candidates": rows[:limit],
        "note": "Metadata only: no novel passages are copied into this public candidate report.",
    }


def load_index(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def bm25_search(index_path: Path, query: str, top_k: int = 8) -> list[dict]:
    docs = load_index(index_path)
    if not docs:
        return []
    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    lengths = [sum(row["token_counts"].values()) for row in docs]
    avgdl = sum(lengths) / len(lengths)
    df = Counter()
    for row in docs:
        df.update(row["token_counts"].keys())

    scores = []
    k1, b = 1.5, 0.75
    n_docs = len(docs)
    for row, dl in zip(docs, lengths):
        counts = row["token_counts"]
        score = 0.0
        for token in query_tokens:
            tf = counts.get(token, 0)
            if not tf:
                continue
            token_df = df[token]
            idf = math.log(1 + (n_docs - token_df + 0.5) / (token_df + 0.5))
            denom = tf + k1 * (1 - b + b * dl / avgdl)
            score += idf * tf * (k1 + 1) / denom
        if score > 0:
            scores.append({
                "chunk_id": row["chunk_id"],
                "chapter_id": row["chapter_id"],
                "chapter_title": row["chapter_title"],
                "line_start": row["line_start"],
                "line_end": row["line_end"],
                "score": round(score, 4),
                "text": row["text"],
            })

    scores.sort(key=lambda row: row["score"], reverse=True)
    return scores[:top_k]


def cmd_build(args: argparse.Namespace) -> None:
    text = args.input.read_text(encoding="utf-8")
    chapters = split_chapters(text)
    chunks = [
        chunk
        for chapter in chapters
        for chunk in chunk_chapter(chapter, args.chunk_chars, args.overlap_paragraphs)
    ]
    write_index(chunks, args.index)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(index_report(chapters, chunks), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    candidates = build_character_candidates(chunks, args.character, args.limit)
    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    args.candidates.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "chapter_count": len(chapters),
        "chunk_count": len(chunks),
        "character_candidates": candidates["candidate_count"],
    }, ensure_ascii=False))


def cmd_show(args: argparse.Namespace) -> None:
    for row in load_index(args.index):
        if row["chunk_id"] != args.chunk_id:
            continue
        text = row["text"].replace("\n", " ")
        if args.focus:
            pos = text.find(args.focus)
            if pos >= 0:
                half = max(80, args.preview_chars // 2)
                start = max(0, pos - half)
                end = min(len(text), pos + len(args.focus) + half)
                text = text[start:end]
        else:
            text = text[: args.preview_chars]
        print(
            f'{row["chunk_id"]} {row["chapter_title"]} '
            f'L{row["line_start"]}-{row["line_end"]}'
        )
        print(text[: args.preview_chars])
        return
    raise SystemExit(f"chunk not found: {args.chunk_id}")


def cmd_search(args: argparse.Namespace) -> None:
    results = bm25_search(args.index, args.query, args.top_k)
    for row in results:
        print(
            f'[{row["score"]:>7}] {row["chunk_id"]} '
            f'{row["chapter_title"]} L{row["line_start"]}-{row["line_end"]}'
        )
        print(row["text"][: args.preview_chars].replace("\n", " "))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Canon RAG builder/searcher")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--input", type=Path, default=Path("cleaned/novel.cleaned.txt"))
    build.add_argument("--index", type=Path, default=Path("rag/private/chunks.jsonl"))
    build.add_argument("--report", type=Path, default=Path("reports/canon_index_report.json"))
    build.add_argument("--candidates", type=Path, default=Path("canon/lu_xin.candidates.json"))
    build.add_argument("--character", default="陆辛")
    build.add_argument("--chunk-chars", type=int, default=900)
    build.add_argument("--overlap-paragraphs", type=int, default=1)
    build.add_argument("--limit", type=int, default=120)
    build.set_defaults(func=cmd_build)

    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--index", type=Path, default=Path("rag/private/chunks.jsonl"))
    search.add_argument("--top-k", type=int, default=8)
    search.add_argument("--preview-chars", type=int, default=220)
    search.set_defaults(func=cmd_search)

    show = sub.add_parser("show")
    show.add_argument("chunk_id")
    show.add_argument("--index", type=Path, default=Path("rag/private/chunks.jsonl"))
    show.add_argument("--focus", default="陆辛")
    show.add_argument("--preview-chars", type=int, default=420)
    show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
