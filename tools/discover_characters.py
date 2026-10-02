from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ACTION = (
    r"说道|说着|问道|回答|笑道|叫道|喊道|点头|摇头|皱眉|看向|看着|"
    r"开口|沉默|走来|走了过来|抬头|低头|转头|叹了口气|笑了|答应|拒绝"
)
ADVERB = r"(?:轻轻|微微|缓缓|忽然|突然|认真地|平静地|低声|轻声|冷冷地|笑着)?"
SUBJECT_RE = re.compile(
    rf"(?<![一-鿿])([一-鿿]{{2,3}}){ADVERB}(?=(?:{ACTION}))"
)
INTRO_RE = re.compile(
    r"(?:叫做|名叫|名字叫|自称)([一-鿿]{2,3})(?![一-鿿])"
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
    "那么", "不过", "另外", "当然", "于是", "毕竟", "而且", "好的", "是的", "只不过",
    "当然了", "下一刻", "但如今", "看起来", "或者说", "哗啦",
    "轻声", "低声", "大声", "笑着", "认真", "忽然", "突然", "微微", "缓缓", "冷冷",
    "男人", "女人", "女孩", "男孩", "老人", "年轻人", "对方", "众人", "所有人",
    "一边", "静静的", "猛得", "点了", "认真的", "摇了", "而是", "同时", "然后他",
    "他一边", "慢慢的", "他微微", "立刻", "继续", "他才", "呆呆的", "下意识",
    "好奇的", "他轻轻", "然后才", "微一", "忍不住", "再次", "急忙", "皱了",
    "父亲", "母亲", "爸爸", "妈妈", "妹妹", "哥哥", "姐姐", "弟弟", "孩子",
}

BAD_PREFIXES = ("他", "她", "它", "向", "又", "再", "便", "就", "然后")
BAD_SUFFIX_CHARS = set("的地得了也才忙便就又着")
TITLE_SUFFIXES = ("教授", "博士", "院长", "老师", "队长", "主任", "局长", "先生", "小姐")

VERBISH_SUFFIXES = (
    "说道", "说着", "问道", "笑道", "声道", "低声", "轻声", "点头", "摇头",
    "皱眉", "开口", "抬头", "低头", "转头", "看着", "看向",
)

COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华"
    "金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方"
    "俞任袁柳鲍史唐费岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞"
    "齐康伍余元卜顾孟平黄和穆萧尹姚邵汪祁毛禹狄米贝明臧计伏成"
    "戴宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭"
    "梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪"
    "干解应宗丁宣贲邓郁单杭洪包诸左石崔吉龚程嵇邢滑裴陆荣翁荀"
    "羊甄曲封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬"
    "全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶黎"
    "乔苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍璩桑桂濮牛寿通边扈"
    "燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖"
    "庾终暨居衡步都耿满弘匡国文寇广禄阙东欧利师巩聂晁勾敖融冷"
    "訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖"
    "益桓公万俟司马上官欧阳夏侯诸葛闻人东方赫连皇甫尉迟公羊澹台"
)


def plausible_subject(token: str) -> bool:
    if token in STOPWORDS:
        return False
    if any(token.endswith(suffix) for suffix in VERBISH_SUFFIXES):
        return False
    if any(token.startswith(prefix) and len(token) > len(prefix) for prefix in BAD_PREFIXES):
        return False
    if token[-1] in BAD_SUFFIX_CHARS:
        return False
    if len(set(token)) == 1:
        return False
    return 2 <= len(token) <= 3


def discover(
    chunks_path: Path,
    *,
    min_mentions: int = 8,
    min_chapters: int = 3,
    min_subject_hits: int = 2,
    limit: int = 80,
) -> dict[str, Any]:
    rows = []
    subject_hits: Counter[str] = Counter()
    intro_hits: Counter[str] = Counter()
    first_seen: dict[str, dict[str, Any]] = {}

    with chunks_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            rows.append(row)
            text = str(row.get("text", ""))
            tokens = list(SUBJECT_RE.findall(text))
            intros = list(INTRO_RE.findall(text))
            for token in tokens:
                if not plausible_subject(token):
                    continue
                subject_hits[token] += 1
                first_seen.setdefault(
                    token,
                    {
                        "chapter_id": str(row.get("chapter_id", "")),
                        "chapter_title": str(row.get("chapter_title", "")),
                        "chunk_id": str(row.get("chunk_id", "")),
                    },
                )
            for token in intros:
                if not plausible_subject(token):
                    continue
                intro_hits[token] += 1
                first_seen.setdefault(
                    token,
                    {
                        "chapter_id": str(row.get("chapter_id", "")),
                        "chapter_title": str(row.get("chapter_title", "")),
                        "chunk_id": str(row.get("chunk_id", "")),
                    },
                )

    seed_names = {
        name for name, hits in subject_hits.items() if hits >= min_subject_hits
    } | {
        name for name, hits in intro_hits.items() if hits >= 1
    }

    mentions: Counter[str] = Counter()
    chapters: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        text = str(row.get("text", ""))
        chapter_id = str(row.get("chapter_id", ""))
        for name in seed_names:
            count = text.count(name)
            if count:
                mentions[name] += count
                chapters[name].add(chapter_id)

    candidates = []
    for name in seed_names:
        total = mentions[name]
        spread = len(chapters[name])
        subjects = subject_hits[name]
        intros = intro_hits[name]
        if total < min_mentions or spread < min_chapters:
            continue

        surname_like = name[0] in COMMON_SURNAMES
        title_like = any(name.endswith(suffix) for suffix in TITLE_SUFFIXES)
        candidate_kind = "personal_name" if surname_like else ("title_or_role_name" if title_like else "alias_or_codename")
        # Direct subject-attribution evidence is more important than raw frequency.
        score = round(
            min(
                100.0,
                subjects * 2.0
                + intros * 8.0
                + min(spread, 60) * 0.7
                + min(total, 200) * 0.08
                + (6.0 if surname_like else 0.0),
            ),
            2,
        )
        recommended = (
            (candidate_kind == "personal_name" and subjects >= 5 and score >= 70)
            or (candidate_kind == "title_or_role_name" and subjects >= 5 and score >= 65)
            or (candidate_kind == "alias_or_codename" and subjects >= 15 and spread >= 10 and score >= 70)
        )
        candidates.append(
            {
                "name": name,
                "status": "DISCOVERY_CANDIDATE",
                "mention_count": total,
                "chapter_count": spread,
                "subject_action_hits": subjects,
                "self_intro_hits": intros,
                "surname_like": surname_like,
                "candidate_kind": candidate_kind,
                "score": score,
                "first_seen": first_seen[name],
                "review_required": True,
                "recommended_for_canon_review": recommended,
            }
        )

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["subject_action_hits"],
            item["chapter_count"],
            item["mention_count"],
        ),
        reverse=True,
    )
    return {
        "schema_version": "character-discovery/2",
        "method": "direct-subject-action-or-self-introduction-seed-then-cross-chapter-frequency",
        "policy": [
            "Discovery output is never Canon.",
            "Every candidate requires Canon review before registry creation.",
            "No novel passages are copied into this public metadata file.",
            "Raw 2-3 character frequency alone is not sufficient for character discovery.",
        ],
        "candidate_count": min(limit, len(candidates)),
        "recommended_count": sum(1 for item in candidates[:limit] if item["recommended_for_canon_review"]),
        "candidates": candidates[:limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover likely character names from local private RAG chunks.")
    parser.add_argument("--chunks", type=Path, default=Path("rag/private/chunks.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("canon/character_discovery.json"))
    parser.add_argument("--min-mentions", type=int, default=8)
    parser.add_argument("--min-chapters", type=int, default=3)
    parser.add_argument("--min-subject-hits", type=int, default=2)
    parser.add_argument("--limit", type=int, default=80)
    args = parser.parse_args()

    result = discover(
        args.chunks,
        min_mentions=args.min_mentions,
        min_chapters=args.min_chapters,
        min_subject_hits=args.min_subject_hits,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"], "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
