# Canon evidence layer

这个目录只提交**证据元数据**，不提交从小说全文切出来的大段正文。

- `lu_xin.candidates.json`：陆辛相关 chunk 的章节、行号、命中类别和分数。
- 真正包含正文的 `rag/private/chunks.jsonl` 由脚本本地生成并被 `.gitignore` 排除。
- 使用 `tools/build_canon_rag.py search "查询"` 可以在本地全文索引上做 BM25 检索。

下一层 Canon Agent 应读取检索结果后输出：

```json
{
  "fact": "结构化事实",
  "type": "hard_fact | soft_trait | forbidden_interpretation",
  "confidence": 0.0,
  "evidence": {
    "chapter_id": "ch-xxxx",
    "chapter_title": "章节标题",
    "chunk_id": "ch-xxxx-ck-xxx",
    "line_start": 0,
    "line_end": 0
  }
}
```

规则：没有证据锚点的内容不能进入 hard fact；视觉设计推断必须和原著事实分开。
