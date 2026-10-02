from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path

TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936", "big5")

ZERO_WIDTH = {
    "\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\u00ad"
}
BAD_RANGES = (
    (0x2500, 0x259F),  # box drawing + block elements
    (0xE000, 0xF8FF),  # private-use area
)
HTML_TAG_RE = re.compile(
    r"</?(?:br|p|div|span|font|a|strong|em|b|i)(?:\s+[^>]*)?>",
    re.IGNORECASE,
)
ENTITY_RE = re.compile(r"&(?:nbsp|amp|lt|gt|quot|#\d+|#x[0-9a-f]+);", re.IGNORECASE)
URL_RE = re.compile(
    r"(?:https?://|www\.|(?:^|\s)[\w.-]+\.(?:com|cn|net|org)(?:/|\s|$))",
    re.IGNORECASE,
)
JUNK_LINE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"手机用户请",
        r"请记住本站",
        r"最新网址",
        r"txt\s*下载",
        r"电子书下载",
        r"本书由.{0,40}(?:整理|提供|制作)",
        r"本书来自.{0,60}",
        r"更多.{0,30}请访问",
        r"关注.{0,20}(?:公众号|微信)",
        r"(?:qq群|q群)[:：]?\s*\d{4,}",
    )
]
MOJIBAKE_HINTS = ("锟斤拷", "ï»¿", "鈥", "銆", "脙", "�")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def choose_txt_member(archive: zipfile.ZipFile) -> zipfile.ZipInfo:
    candidates = [
        info for info in archive.infolist()
        if not info.is_dir() and info.filename.lower().endswith(".txt")
    ]
    if not candidates:
        raise RuntimeError("No .txt member found in ZIP")
    return max(candidates, key=lambda item: item.file_size)


def decode_text(data: bytes) -> tuple[str, str]:
    for encoding in TEXT_ENCODINGS:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        # Reject clearly implausible decodes when another encoding may be better.
        cjk = sum("\u3400" <= ch <= "\u9fff" for ch in text[:200_000])
        sample = text[:200_000]
        printable = sum(ch.isprintable() or ch in "\r\n\t" for ch in sample)
        if sample and printable / len(sample) < 0.96:
            continue
        if encoding in {"big5"} and cjk < 100:
            continue
        return text, encoding
    # Last-resort path: GB18030 preserves as much source information as possible.
    return data.decode("gb18030", errors="replace"), "gb18030-replace"


def should_remove_char(ch: str) -> bool:
    cp = ord(ch)
    if ch in ZERO_WIDTH or ch == "\ufffd":
        return True
    if any(start <= cp <= end for start, end in BAD_RANGES):
        return True
    category = unicodedata.category(ch)
    if category in {"Cc", "Cf", "Cs"} and ch not in {"\n", "\t"}:
        return True
    return False


def normalize_line(line: str, stats: Counter) -> str:
    if ENTITY_RE.search(line):
        before = line
        line = html.unescape(line)
        stats["html_entities_decoded"] += before != line

    before = line
    line = HTML_TAG_RE.sub("", line)
    if line != before:
        stats["html_tags_removed"] += 1

    out = []
    for ch in line:
        if ch == "\u00a0":
            out.append(" ")
            stats["nbsp_normalized"] += 1
            continue
        if should_remove_char(ch):
            stats[f"removed_U+{ord(ch):04X}"] += 1
            continue
        out.append(ch)
    return "".join(out).rstrip()


def is_high_confidence_junk_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped:
        return None
    if URL_RE.search(stripped):
        return "url_or_domain"
    for idx, pattern in enumerate(JUNK_LINE_PATTERNS, start=1):
        if pattern.search(stripped):
            return f"junk_pattern_{idx}"
    return None


def remaining_suspicious(line: str) -> list[str]:
    reasons = []
    for hint in MOJIBAKE_HINTS:
        if hint in line:
            reasons.append(f"mojibake:{hint}")
    if any(0x2500 <= ord(ch) <= 0x259F for ch in line):
        reasons.append("box_or_block")
    if any(unicodedata.category(ch) in {"Co", "Cs"} for ch in line):
        reasons.append("private_or_surrogate")
    # Excessive symbol runs often indicate damaged separators or copied-site noise.
    if re.search(r"[^\w\u3400-\u9fff，。！？；：、“”‘’（）《》…—\s]{8,}", line):
        reasons.append("long_symbol_run")
    return reasons


def clean_text(text: str) -> tuple[str, dict, list[dict]]:
    stats: Counter = Counter()
    samples: list[dict] = []
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    cleaned: list[str] = []
    blank_run = 0
    for line_no, raw in enumerate(lines, start=1):
        line = normalize_line(raw, stats)
        reason = is_high_confidence_junk_line(line)
        if reason:
            stats[f"dropped_{reason}"] += 1
            if len(samples) < 80:
                samples.append({
                    "line": line_no,
                    "reason": reason,
                    "sample": line[:180],
                })
            continue

        if not line.strip():
            blank_run += 1
            if blank_run <= 2:
                cleaned.append("")
            else:
                stats["extra_blank_lines_removed"] += 1
            continue
        blank_run = 0

        reasons = remaining_suspicious(line)
        if reasons and len(samples) < 80:
            samples.append({
                "line": line_no,
                "reason": ",".join(reasons),
                "sample": line[:180],
            })
        cleaned.append(line)

    result = "\n".join(cleaned).strip() + "\n"
    return result, dict(stats), samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--out", type=Path, default=Path("cleaned/novel.cleaned.txt"))
    parser.add_argument("--report", type=Path, default=Path("reports/cleaning_report.json"))
    parser.add_argument("--samples", type=Path, default=Path("reports/suspicious_samples.json"))
    args = parser.parse_args()

    zip_bytes = args.zip_path.read_bytes()
    with zipfile.ZipFile(args.zip_path) as archive:
        member = choose_txt_member(archive)
        raw = archive.read(member)

    decoded, encoding = decode_text(raw)
    cleaned, stats, samples = clean_text(decoded)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.samples.parent.mkdir(parents=True, exist_ok=True)

    args.out.write_text(cleaned, encoding="utf-8", newline="\n")
    report = {
        "source_zip": args.zip_path.name,
        "source_zip_sha256": sha256_bytes(zip_bytes),
        "member_name": member.filename,
        "member_bytes": len(raw),
        "detected_encoding": encoding,
        "chars_before": len(decoded),
        "chars_after": len(cleaned),
        "removed_chars_or_lines": stats,
        "suspicious_sample_count": len(samples),
        "output": str(args.out),
        "output_sha256": sha256_bytes(cleaned.encode("utf-8")),
        "policy": "conservative cleanup: source archive unchanged; no story rewriting",
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.samples.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
