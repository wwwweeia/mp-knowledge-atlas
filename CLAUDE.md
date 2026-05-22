# CLAUDE.md

## 项目说明

技术文章知识地图：从微信公众号自动采集文章，通过全文清洗 + LLM 摘要 + embedding + 聚类 + 网络分析生成领域知识地图，发布为 VitePress 静态站。

## 数据源

### We-MP-RSS（主数据源）

微信公众号订阅服务，Docker 部署在本地。

| 项目 | 值 |
|------|-----|
| 位置 | `/Users/wqw/Documents/idea_work/tools/we-mp-rss/` |
| 访问地址 | http://localhost:8001 |
| 数据库 | `data/we_mp_rss.db`（SQLite） |
| 文档 | 见上述目录下的 `README.md` |

通过微信读书扫码登录，自动抓取已订阅公众号的文章（标题、URL、全文），后台持续补抓内容。

当前订阅：10 个公众号，600+ 篇文章（持续增长中）。

**与本项目的衔接**：pipeline 的 `ingest` stage 从 We-MP-RSS 的 SQLite 数据库读取文章数据，支持增量导入和全文回填。

### articles/*.md（历史数据）

手动维护的 53 篇文章索引，保留为只读历史快照。新文章只走 We-MP-RSS。

## Pipeline 架构（V2）

```
We-MP-RSS SQLite
       │
       ▼
   ┌─────────┐
   │ ingest  │ 读取文章（标题+URL+全文HTML+元数据），检测新增和全文回填
   └────┬────┘
        ▼
   ┌──────────┐
   │ clean    │ HTML→纯文本（BeautifulSoup），去除广告/CTA，无全文的跳过
   └────┬─────┘
        ▼
   ┌───────────┐
   │ summarize │ DeepSeek API 生成结构化摘要（summary + keywords JSON）
   └────┬──────┘
        ▼
   ┌─────────┐
   │ embed   │ 标题+摘要 → Ollama nomic-embed-text 向量嵌入 → ChromaDB
   └────┬────┘
        ▼
   ┌─────────┐
   │ cluster │ HDBSCAN / K-means 聚类 + LLM 领域命名（一体化）
   └────┬────┘
        ▼
   ┌─────────┐
   │ network │ 跨簇语义相似度 + betweenness 桥梁检测
   └────┬────┘
        ▼
   ┌─────────┐
   │ publish │ 渲染 VitePress Markdown + D3.js 网络图
   └─────────┘
```

### pipeline_stage 状态机

`ingested` → `cleaned` → `summarized` → `embedded`

每阶段只处理当前 stage 的文章，已完成的自动跳过。失败则停留当前 stage，下次运行重试。

### 关键命令

```bash
make refresh   # 增量刷新：导入新文章 + 回填全文 → 清洗 → 摘要 → 嵌入 → 聚类 → 网络 → 发布
make rebuild   # 全量重跑：清空所有数据 + refresh（耗时较长，首次或调试用）
make build     # VitePress 构建
make all       # refresh + build
make serve     # 本地预览（http://localhost:5173）
make test      # pytest
make clean     # 清理所有输出
```

### 增量机制

| 机制 | 说明 |
|------|------|
| 新文章导入 | `upsert_articles` 用 `source_id` 去重，只插入新文章 |
| 全文回填 | `backfill_fulltext` 检测 `has_fulltext=0` 的文章是否在 We-MP-RSS 中已补到全文，自动重置 `pipeline_stage` 重新处理 |
| 各阶段跳过 | clean/summarize/embed 只处理对应 stage 的文章，已完成的不重复处理 |

**典型耗时**：无新数据时 `make refresh` 约 30 秒；有新文章时取决于 LLM 摘要数量（约 1-3 分钟）。

### 外部服务

| 服务 | 用途 | 配置 |
|------|------|------|
| Ollama | 向量嵌入（nomic-embed-text:v1.5） | 本地 http://localhost:11434 |
| DeepSeek API | LLM 摘要 + 聚类命名 | `.env` 中 `DEEPSEEK_API_KEY` |
| ChromaDB | 向量存储（collection: articles_v2） | 本地 `data/chroma/` |

## 目录结构

```
src/
├── ingest.py        # 从 We-MP-RSS 导入 + 全文回填
├── clean.py         # HTML→纯文本
├── summarize.py     # LLM 结构化摘要
├── embed.py         # 标题+摘要 → 向量嵌入
├── cluster.py       # HDBSCAN/K-means 聚类 + LLM 命名
├── network.py       # betweenness 桥梁分析
├── publish.py       # 渲染 VitePress markdown + 网络图
└── lib/
    ├── db.py        # SQLite 数据层（schema + CRUD）
    ├── html.py      # HTML 清洗工具（BeautifulSoup）
    ├── llm.py       # DeepSeek API 客户端（name_cluster + summarize_article）
    ├── embedding.py  # Ollama 嵌入调用
    └── vec.py       # ChromaDB 操作

site/                # VitePress 站点（publish.py 写入 site/docs）
out/                 # pipeline 中间产物（clusters_named.json, network.json）
data/                # articles.db + chroma/（gitignore）
articles/            # 历史手工索引（只读）
templates/           # Jinja2 模板（article/domain/index/network）
```

## 设计文档

- `docs/superpowers/specs/2026-05-22-pipeline-v2-fulltext-redesign.md` — V2 全文重设计 spec（权威）
- `docs/superpowers/specs/2026-05-21-knowledge-map-mvp-design.md` — MVP 设计 spec（历史参考）
