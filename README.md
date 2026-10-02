# 《从红月开始》文本清洗仓库

保留原始 `1-2203151F522.zip` 不动，自动生成适合后续 Canon/RAG 使用的 UTF-8 清洗文本。

## 自动输出

- `cleaned/novel.cleaned.txt`：UTF-8 清洗版
- `reports/cleaning_report.json`：编码、哈希、清洗统计
- `reports/suspicious_samples.json`：仍需人工/第二轮规则检查的可疑行样本

## 第一轮清洗原则

只做保守处理，不改写小说内容：

- 自动识别 ZIP 中最大的 TXT
- 自动识别 UTF-8 / GB18030 / GBK / CP936 等编码
- 转为 UTF-8
- 删除 BOM、零宽字符、控制字符、私用区字符、方框/块状乱码、替换字符
- 解码常见 HTML entity，清掉残留 HTML 标签
- 删除明显下载站 URL / 域名 / 电子书广告行
- 合并过多空行
- 保留原 ZIP，报告所有处理统计

如果报告里仍存在重复乱码模式，再根据报告做第二轮针对性清洗，而不是一次性用激进正则删除正文。
