# 《从红月开始》Canon / 角色证据层项目详细说明书

> 仓库：`wa52/1-2203151F522`  
> 基线：main @ `ca7a771766b24c6a12ee1aa95b966732e8bb7532`  
> 项目定位：小说文本清洗、可追溯 Canon 证据层、人物发现、角色 Profile 与角色 Contract  
> 本说明书依据当前 README、canon、tools、tests 与 GitHub Actions 配置整理。

## 1. 项目目标

这个仓库的核心目标，不是直接把小说“变成图片”，而是先建立一层可靠的原著事实基础，避免后续角色设计、漫改、生图 Agent 只凭印象生成。

当前系统做的事情可以概括为：

```text
原始小说 ZIP
  -> 文本清洗
  -> UTF-8 标准文本
  -> 按章节切分
  -> Chunk
  -> 本地 BM25 Canon RAG
  -> 人物候选发现
  -> 人物证据 Profile
  -> Canon Character Contract
  -> 后续角色导演 / 生图系统消费
```

项目强调一个原则：

**任何被锁定为 Canon 的事实，都必须能够追溯到原著章节、Chunk 和行号。**

视觉推断、气质理解和“设计建议”不能冒充原著事实。

## 2. 当前仓库实际完成了什么

当前仓库已经完成的主要能力包括：

- 原始 ZIP 保留；
- 小说文本自动解码和保守清洗；
- UTF-8 标准化；
- 清洗报告；
- 可疑行报告；
- 章节识别；
- Chunk 切分；
- 本地 BM25 检索；
- 指定人物的证据候选筛选；
- 自动人物发现；
- 角色草稿生成；
- 陆辛等角色 Profile；
- Character Contract；
- 多角色通用 Profile / Contract 工具；
- 基本自动测试；
- GitHub Actions 自动构建 / 验证。

目前仓库已经从“文本清洗仓库”扩展成了一个小说 Canon Evidence Layer。

但它仍然不是完整的“角色图片自动迭代系统”。

仓库当前没有完整实现：

- 图像生成模型调度；
- 视觉 Critic；
- 多轮角色图生成与自动评分；
- 角色导演根据图片自动修改 Prompt；
- 最终人物视觉资产管理。

因此准确定位应是：

**它是后续小说漫改角色导演系统的原著证据与角色约束基础层。**

## 3. 原始数据与清洗

仓库保留：

```text
1-2203151F522.zip
```

原始 ZIP 不直接被覆盖。

清洗工具：

```text
tools/clean_novel.py
```

清洗后的标准文本：

```text
cleaned/novel.cleaned.txt
```

### 3.1 清洗策略

第一轮采用保守策略，目标是不修改小说语义。

主要处理：

- 自动选择 ZIP 中最大的 TXT；
- 自动识别 UTF-8 / GB18030 / GBK / CP936 等编码；
- 转换为 UTF-8；
- 删除 BOM；
- 删除零宽字符；
- 删除控制字符；
- 删除私用区字符；
- 删除明显方框 / 块状乱码；
- 删除替换字符；
- 解码常见 HTML Entity；
- 清除残留 HTML 标签；
- 删除明显下载站 URL、域名和电子书广告行；
- 合并连续过多空行。

项目特意避免“一条激进正则把正文一起删除”的方式。

### 3.2 清洗报告

输出：

```text
reports/cleaning_report.json
reports/suspicious_samples.json
```

前者记录编码、哈希和清洗统计。

后者保留仍然可疑的文本样本，便于第二轮针对性规则。

这是一种“先可追踪，再清洗”的工程策略。

## 4. 章节切分与 Chunk

主要实现位于：

```text
tools/build_canon_rag.py
```

章节标题支持识别类似：

- 第X章
- 引子
- 序章
- 番外

章节被转换成结构化 Chapter：

```text
chapter_id
title
start_line
end_line
paragraphs
```

随后再切成 Chunk。

默认 Chunk 目标约 900 字符，并保留少量段落重叠。

Chunk 包含：

```text
chunk_id
chapter_id
chapter_title
line_start
line_end
text
```

这样后续所有事实都可以定位到：

```text
章节 -> Chunk -> 行号
```

## 5. 本地 Canon RAG

为了避免把小说全文和大量正文直接提交到公开仓库，真正包含正文的检索索引默认写入：

```text
rag/private/chunks.jsonl
```

这个目录不公开提交。

公开仓库只保存证据元数据和结果。

### 5.1 BM25

当前检索实现是本地 BM25。

命令思路：

```text
tools/build_canon_rag.py search "查询"
```

BM25 对每个 Chunk 计算相关度。

中文 Token 方案同时使用：

- 单个汉字；
- 相邻双字；
- ASCII 单词。

这不是最先进的语义检索，但优点是：

- 可离线；
- 不需要 Embedding API；
- 不需要向量数据库；
- 结果可解释；
- 适合做第一层证据召回。

## 6. 人物相关证据候选

`build_canon_rag.py` 中针对角色设计了候选类别。

例如陆辛相关维度：

- identity
- appearance
- occupation
- demeanor
- family
- social_reaction
- abnormality

系统会在人物名字附近检查相关词，并计算候选分数。

公开输出只保存：

- chunk_id
- chapter_id
- chapter_title
- line_start
- line_end
- 类别
- 分数
- 提及次数

不会把整段小说正文直接复制到公开 JSON。

## 7. 人物自动发现

工具：

```text
tools/discover_characters.py
```

目标是从全文中自动找可能的角色名，而不是所有人物都人工输入。

### 7.1 发现方法

目前使用：

```text
动作主语 / 自我介绍
  -> 人名种子
  -> 跨章节出现频率
  -> 候选打分
```

例如系统会寻找：

```text
某某说道
某某问道
某某抬头
某某走过来
名叫某某
自称某某
```

再结合：

- mention_count
- chapter_count
- subject_action_hits
- self_intro_hits
- 姓氏特征
- 角色名 / 称谓类型

计算候选分数。

### 7.2 输出不是 Canon

人物自动发现结果必须明确标记：

```text
DISCOVERY_CANDIDATE
```

仓库规则规定：

- Discovery output 永远不能直接成为 Canon；
- 每个角色需要经过 Canon Review；
- 纯 2～3 字高频词不能直接当人物；
- 公开文件不复制小说原文。

这可以防止“自动统计错误 -> 错误角色事实一路传到生图”。

## 8. Canon Profile

仓库当前已经生成多个人物 Profile，例如：

```text
canon/lu_xin.profile.json
canon/chen_jing.profile.json
canon/han_bing.profile.json
canon/bi_hu.profile.json
```

Profile 用来保存角色相关的结构化证据和解释层。

其内容可以分为：

- hard_facts
- performance_evidence
- visual_evidence_candidates
- forbidden_inferences

### 8.1 Hard Fact

Hard Fact 是可以由原文明确支持的事实。

例如：

- 年龄；
- 身份 / 工作环境；
- 明确关系；
- 明确行为事实。

每一项必须带 Evidence。

### 8.2 Soft Trait / Performance Evidence

例如：

- 某些场景中表现平静；
- 日常气质克制；
- 在办公室场景表现普通。

这些可以用于角色导演，但不能被直接转换成固定长相。

例如：

```text
“普通”
!=
“必须长成某种固定脸型”
```

### 8.3 Forbidden Inference

这是项目很重要的一层。

它用来明确禁止：

- 把气质描述硬翻译成具体五官；
- 用后续影视化印象覆盖原著；
- 把读者脑补当 Canon；
- 把没有证据的发色、脸型、身高、服装细节锁死。

## 9. Character Contract

工具：

```text
tools/export_character_contract.py
tools/export_generic_character_contract.py
```

输出：

```text
canon/*.character_contract.json
```

Contract 的作用，是把复杂 Profile 转成后续角色设计 Agent 可以直接消费的稳定契约。

### 9.1 Contract 主要内容

```text
character
provenance
locked_facts
soft_constraints
unresolved_visual_features
forbidden_interpretations
acceptance_rules
```

### 9.2 Locked Facts

只有存在 Evidence Anchor 的事实才允许被锁定。

证据必须包含：

```text
chapter_id
chapter_title
chunk_id
line_start
line_end
```

如果缺少 Evidence，Contract 校验会报错。

### 9.3 Unresolved Visual Features

原著没有明确写的视觉信息会进入：

```text
unresolved_visual_features
```

它们保持开放。

这非常适合后续生图迭代，因为导演可以在不违背原著的范围内探索。

### 9.4 Soft Constraints

Soft Constraint 是“表演方向”或“气质边界”。

例如：

```text
日常形象应保持普通、低主角光环
```

这种约束可以影响：

- 服装；
- 表情；
- 镜头语言；
- 姿态；
- 整体角色气质。

但不会自动变成固定五官。

## 10. 当前角色数据

仓库目前公开包含多个角色 Contract / Profile。

例如：

- 陆辛
- 陈菁
- 韩冰
- 壁虎

同时还有：

```text
canon/character_discovery.json
canon/character_drafts.json
```

说明系统已经开始从单一主角扩展到多角色基础层。

## 11. 数据隐私与版权设计

仓库采用“公开元数据 + 私有正文索引”结构。

公开提交：

- 原始来源文件；
- 清洗文本；
- 报告；
- 证据定位；
- Profile；
- Contract；
- 测试。

真正用于检索的全文 Chunk 索引默认放在：

```text
rag/private/
```

不会直接提交。

Canon README 明确提出：

**公共 Contract 中不应嵌入小说长段正文，只保存证据指针。**

这有利于：

- 减少仓库体积；
- 避免每个结构化文件重复全文；
- 保持证据可追溯；
- 后续 Agent 需要时再本地检索。

## 12. GitHub Actions

仓库已经有自动化工作流：

```text
.github/workflows/clean-novel.yml
.github/workflows/build-canon-rag.yml
```

主要用于验证清洗和 Canon 数据构建流程。

## 13. 自动测试

当前测试包括：

```text
tests/test_character_drafts.py
tests/test_discover_characters.py
tests/test_generic_character_contract.py
```

测试重点不是“角色像不像”，而是基础数据管线是否可靠：

- 人物发现输出结构；
- 人物草稿；
- 通用 Contract；
- Evidence 约束；
- Schema 行为。

## 14. 典型运行流程

第一步，清洗小说：

```bash
python tools/clean_novel.py
```

第二步，构建本地 Canon RAG：

```bash
python tools/build_canon_rag.py build
```

第三步，搜索原著：

```bash
python tools/build_canon_rag.py search "陆辛 公司 普通"
```

第四步，发现人物：

```bash
python tools/discover_characters.py
```

第五步，构建人物 Profile：

```bash
python tools/build_lu_xin_profile.py
```

或使用通用角色 Profile 工具：

```bash
python tools/build_generic_character_profile.py
```

第六步，导出 Character Contract：

```bash
python tools/export_character_contract.py
```

或：

```bash
python tools/export_generic_character_contract.py
```

最终后续视觉系统读取：

```text
canon/<character>.character_contract.json
```

## 15. 推荐的后续角色导演架构

当前仓库最适合继续向下接：

```text
Canon RAG
  ->
Character Contract
  ->
Character Director Agent
  ->
Prompt / Scene Spec
  ->
Image Generation Model
  ->
Visual Critic
  ->
Canon Consistency Review
  ->
Revision
  ->
下一轮
```

角色导演必须区分三层信息：

### A. 原著锁定事实

不能修改。

### B. 原著软约束

允许不同视觉表达，但不能违反整体方向。

### C. 未定义视觉特征

允许生成模型探索。

这三层是后续“人物不像想象”的关键解决方案。

## 16. 后续 Visual Critic 应检查什么

未来 Visual Critic 不应只问“好不好看”，而应该分别检查：

### Canon 一致性

- 是否违反 locked fact；
- 是否把 unresolved 特征错误锁死；
- 是否出现 forbidden interpretation。

### 角色气质

- 表情；
- 姿态；
- 日常感；
- 普通 / 主角光环比例；
- 场景表现。

### 视觉连续性

同一个人物多轮图像：

- 脸部结构稳定；
- 发型稳定；
- 服装逻辑稳定；
- 年龄稳定；
- 身材比例稳定；
- 角色识别度稳定。

### 美术表现

- 2D / 动漫风格一致；
- 不过度偶像化；
- 镜头语言符合原著；
- 光线和场景服务人物，而不是抢角色。

## 17. 当前完成度判断

如果把最终目标定义成：

**“让 AI 根据《从红月开始》原著持续迭代角色形象，直到接近原著与用户想象。”**

那么当前仓库大致完成的是：

```text
原著数据层          已有
文本清洗            已有
Canon RAG           已有
人物发现            已有
Profile             已有
Character Contract  已有
角色导演 Agent       尚未完整接入
生图模型             尚未完整接入
视觉 Critic          尚未完整接入
自动反馈迭代         尚未完整接入
最终角色资产管理      尚未完整接入
```

因此这不是一个“已经完成的 AI 漫改系统”，而是它最重要的数据与 Canon 基础层。

## 18. 验收标准

当前 Canon 层可以按以下标准验收：

1. 原始 ZIP 不被修改；
2. 清洗文本 UTF-8 可稳定读取；
3. 清洗过程有统计报告；
4. 可疑内容有单独报告；
5. 章节识别可追溯；
6. Chunk 保留章节与行号；
7. BM25 能返回原文相关 Chunk；
8. 公共证据文件不复制长段正文；
9. 人物发现结果不能直接成为 Canon；
10. Hard Fact 必须有 Evidence Anchor；
11. Soft Trait 不自动变成视觉事实；
12. 未明确视觉特征保持 unresolved；
13. Contract 中 forbidden interpretation 可阻止错误推断；
14. 自动测试通过。

只有这些成立，后续角色导演才有可靠输入。

## 19. 当前主要不足

当前最主要的不足不是 RAG，而是“证据层还没有和视觉闭环真正接起来”。

下一阶段最有价值的开发不是继续堆更多 JSON，而是：

```text
Character Contract
  -> 自动 Prompt Compiler
  -> 图像生成
  -> Visual Critic
  -> Canon Reviewer
  -> Feedback Patch
  -> 下一轮
```

同时需要保存每一轮：

- Prompt；
- Seed；
- Model；
- 图片；
- Critic 结论；
- Canon 冲突；
- 改动建议；
- 用户反馈；
- 最终选中角色版本。

这样才能形成真正的“角色进化记录”。

## 20. 项目价值

这个项目的价值不只适用于《从红月开始》。

同样的 Canon Evidence Layer 可以用于：

- 小说漫改；
- 游戏角色设定；
- IP 角色一致性；
- 长篇小说问答；
- 剧本角色卡；
- 漫画人物设计；
- AI 视频角色连续性。

只要底层输入换成其他小说，就可以复用大部分架构。

---

这份说明书描述当前 GitHub 主分支实际能力。仓库 `README.md`、`canon/README.md`、`tools/*.py`、`canon/*.profile.json`、`canon/*.character_contract.json` 和测试文件仍是当前实现事实的最终依据。
