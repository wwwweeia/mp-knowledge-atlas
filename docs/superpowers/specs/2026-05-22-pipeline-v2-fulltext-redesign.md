# Pipeline V2：全文驱动的知识地图重设计

> 日期：2026-05-22
> 状态：Draft
> 前置：MVP 已完成（53 篇历史文章，6 阶段 pipeline 跑通）

## 背景

MVP 版本只用了文章标题做嵌入，导致下游聚类粗糙、命名不准、网络图无意义。We-MP-RSS 已采集 437 篇文章（7 个公众号），其中 114 篇有全文内容（HTML 格式，平均 590KB），需要重新设计 pipeline 以充分利用全文。

## 目标

1. 从 We-MP-RSS 导入文章（标题 + 全文 + 元数据）
2. 通过 HTML 清洗 + LLM 摘要提升数据质量
3. 基于高质量摘要重新做嵌入、聚类、网络分析
4. VitePress 站点展示摘要、关键词、原文链接

## 使用场景

- **主要**：个人知识管理（快速查找领域文章）、技术趋势跟踪
- **次要**：团队培训素材、知识共享

## 约束

- 无全文的文章（323 篇）用标题降级处理，不丢弃
- 全文会持续补充（We-MP-RSS 后台抓取）
- 嵌入模型继续用本地 Ollama（nomic-embed-text）
- LLM 用 DeepSeek API（成本低）

## Pipeline 架构

```
We-MP-RSS SQLite
       │
       ▼
   ┌─────────┐
   │ ingest  │ 读取文章（标题+URL+全文HTML+元数据）
   └────┬────┘
        ▼
   ┌──────────┐
   │ clean    │ HTML→纯文本，提取正文
   └────┬─────┘
        ▼
   ┌───────────┐
   │ summarize │ LLM 生成结构化摘要（摘要+关键词）
   └────┬──────┘
        ▼
   ┌─────────┐
   │ embed   │ 标题+摘要 → 向量嵌入
   └────┬────┘
        ▼
   ┌─────────┐
   │ cluster │ 聚类 + 领域命名
   └────┬────┘
        ▼
   ┌─────────┐
   │ network │ 网络分析 + 桥梁检测
   └────┬────┘
        ▼
   ┌─────────┐
   │ publish │ 渲染 VitePress 站点
   └─────────┘
```

## 数据模型

### articles 表

```sql
CREATE TABLE articles (
    id              INTEGER PRIMARY KEY,
    -- 来源
    source_id       TEXT NOT NULL UNIQUE,
    feed_id         TEXT NOT NULL,
    feed_name       TEXT NOT NULL,
    -- 原始内容
    title           TEXT NOT NULL,
    url             TEXT,
    raw_html        TEXT,
    published_at    DATETIME,
    -- 处理产物
    clean_text      TEXT,
    summary         TEXT,
    keywords        TEXT,                   -- JSON 数组字符串
    embedding_id    TEXT,
    -- 元数据
    has_fulltext    BOOLEAN DEFAULT 0,
    pipeline_stage  TEXT DEFAULT 'ingested',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_source ON articles(source_id);
CREATE INDEX idx_pipeline ON articles(pipeline_stage);
CREATE INDEX idx_feed ON articles(feed_id);
CREATE INDEX idx_embedding ON articles(embedding_id);
```

### pipeline_stage 枚举

`ingested` → `cleaned` → `summarized` → `embedded`

每阶段处理成功后推进到下一阶段。失败则停留在当前阶段，下次运行时重试。

### clusters_named.json 结构

```json
{
  "generated_at": "2026-05-22T10:00:00",
  "method": "hdbscan",
  "clusters": [
    {
      "cluster_id": 0,
      "name": "领域名称",
      "description": "一句话描述",
      "keywords": ["关键词1", "关键词2"],
      "article_ids": [1, 5, 12],
      "top_articles": [
        {"id": 1, "title": "...", "summary": "..."}
      ]
    }
  ]
}
```

## 各阶段设计

### Stage 1: ingest

**输入**：We-MP-RSS SQLite（`/Users/wqw/Documents/idea_work/tools/we-mp-rss/data/we_mp_rss.db`）

**逻辑**：
1. 读取 `articles` 表，JOIN `feeds` 表获取公众号名称
2. 用 `source_id`（We-MP-RSS 文章 ID）去重，只导入新文章
3. 设置 `has_fulltext = (content IS NOT NULL AND length(content) > 100)`
4. `raw_html` 存原始 HTML 内容
5. `pipeline_stage = 'ingested'`

**关键 SQL**：
```sql
SELECT a.id, a.title, a.url, a.content, a.publish_time,
       f.name as feed_name, f.id as feed_id
FROM articles a
JOIN feeds f ON a.feed_id = f.id
WHERE a.status = 1
```

### Stage 2: clean

**输入**：本项目 articles.db 中 `pipeline_stage = 'ingested' AND has_fulltext = 1` 的文章

**逻辑**：
1. 用 `readability-lxml` 或 `BeautifulSoup` 提取正文
2. 去除：公众号尾部引导关注、广告、冗余 HTML 标签
3. 保留：正文段落文本、代码块内容
4. `clean_text` 限制最大长度 10000 字符（超长截断）
5. 无全文的文章跳过，`clean_text = NULL`
6. 成功后 `pipeline_stage = 'cleaned'`

**降级策略**：`has_fulltext = False` 的文章直接跳到 summarized 阶段（summary = title）

### Stage 3: summarize

**输入**：`pipeline_stage = 'cleaned'`（有全文）或 `pipeline_stage = 'ingested' AND has_fulltext = 0`（无全文）

**逻辑**：
1. 有全文的文章：用 DeepSeek API 生成结构化摘要
2. Prompt 要求输出 JSON：`{"summary": "200字摘要", "keywords": ["词1", "词2", "词3"]}`
3. 关键词 3-5 个，涵盖文章核心主题
4. 无全文的文章：`summary = title`，`keywords = "[]"`
5. 批量处理，每批 10 篇
6. 成功后 `pipeline_stage = 'summarized'`

**LLM Prompt 模板**：
```
请对以下技术文章生成结构化摘要。输出严格的 JSON 格式：
{"summary": "200字以内的中文摘要", "keywords": ["关键词1", "关键词2", "关键词3"]}

要求：
- summary 准确概括文章的核心内容和技术要点
- keywords 是 3-5 个最能代表文章主题的词
- 如果文章是活动/招聘/公告类非技术内容，keywords 中包含"非技术"

文章标题：{title}
文章正文：
{clean_text}
```

### Stage 4: embed

**输入**：`pipeline_stage = 'summarized' AND embedding_id IS NULL` 的文章

**逻辑**：
1. 嵌入文本 = `title + "\n\n" + summary`
2. 用 Ollama `nomic-embed-text:v1.5` 生成向量
3. ChromaDB 存储，metadata 包含 article_id、title、feed_name
4. 增量处理，只嵌入新文章
5. 成功后 `pipeline_stage = 'embedded'`

### Stage 5: cluster

**输入**：ChromaDB 全部向量

**逻辑**：
1. 优先 HDBSCAN（min_cluster_size=5），噪音率 > 30% 时 fallback 到 K-means
2. 聚类后，对每个簇调用 LLM 命名：
   - 输入：簇内文章的标题 + 摘要 + keywords
   - 输出：领域名称 + 一句话描述 + 代表性关键词
3. 选出每个簇的 top 3 代表性文章（最接近簇中心的）
4. 输出 `clusters_named.json`

### Stage 6: network

**输入**：clusters_named.json + ChromaDB 向量

**逻辑**：
1. 与 MVP 相同：计算跨簇语义相似度边、betweenness centrality 桥梁检测
2. 输入质量提升预期会带来更有意义的网络结构

### Stage 7: publish

**输入**：clusters_named.json + network.json + articles.db

**改进**：
1. **文章详情页**：展示摘要、关键词、原文链接（外链到微信）
2. **领域页面**：展示代表性文章、领域关键词
3. **首页**：网络图 iframe + 最新文章列表
4. **网络图**：节点大小按文章数缩放，hover 显示摘要
5. 保留 D3.js + VitePress 方案

## 旧文件清理

以下文件/目录在 V2 完成后删除：
- `articles/*.md`（53 篇历史手工索引）
- `scripts/migrate_markdown.py`
- `src/lib/parse.py`
- `src/lib/tfidf_fallback.py`
- `src/name.py`（合并到 cluster.py）
- `data/articles.db`（旧数据库）
- `data/chroma/`（旧向量数据）

## 目录结构（V2）

```
src/
├── ingest.py        # 从 We-MP-RSS 导入
├── clean.py         # HTML 清洗
├── summarize.py     # LLM 摘要
├── embed.py         # 向量嵌入
├── cluster.py       # 聚类 + 命名（合并）
├── network.py       # 网络分析
├── publish.py       # 渲染站点
└── lib/
    ├── db.py        # 数据库操作
    ├── html.py      # HTML 清洗工具
    ├── llm.py       # LLM 调用
    ├── embedding.py  # 嵌入调用
    └── vec.py       # ChromaDB 操作
```

## 依赖变更

新增：
- `readability-lxml` 或 `beautifulsoup4`（HTML 清洗）
- `lxml`（HTML 解析后端）

移除：
- `jieba`（不再需要 TF-IDF fallback）

## Makefile

```bash
make refresh   # ingest → clean → summarize → embed → cluster → network → publish
make build     # vitepress build
make all       # refresh + build
make serve     # 本地预览
make clean     # 清理所有输出
make test      # pytest
```

## 测试策略

- 每个阶段独立单元测试
- 集成测试：mock LLM/embedding，验证端到端数据流
- 回归测试：新的 snapshot 文件验证聚类稳定性
- HTML 清洗测试：准备有代表性的公众号文章 HTML 样本

## 风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| LLM 摘要 API 成本 | DeepSeek 成本极低；批量处理；无全文跳过 |
| HTML 清洗质量参差 | 保留 raw_html；pipeline_stage 可重跑 |
| 114/437 有全文，数据不够 | We-MP-RSS 持续抓取；无全文文章用标题降级 |
| 旧数据迁移 | 不迁移，从 We-MP-RSS 重新导入 |
