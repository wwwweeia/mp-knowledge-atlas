# CLAUDE.md

## 项目说明

技术文章知识地图：从微信公众号自动采集文章，通过 embedding + 聚类 + 网络分析生成领域知识地图，发布为 VitePress 静态站。

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

当前订阅：10 个公众号，500+ 篇文章（持续增长中）。

**与本项目的衔接**：pipeline 的 `ingest` stage 从 We-MP-RSS 的 SQLite 数据库读取文章数据，取代原来的 `articles/*.md` 手工索引。

### articles/*.md（历史数据）

手动维护的 53 篇文章索引，保留为只读历史快照。新文章只走 We-MP-RSS。

## Pipeline 架构

```
We-MP-RSS SQLite ──→ ingest ──→ embed ──→ cluster ──→ name ──→ network ──→ publish ──→ VitePress
(数据源)              (读DB)    (向量)    (聚类)     (命名)   (桥梁分析)  (渲染MD/HTML)   (静态站)
```

### 关键命令

```bash
make refresh   # embed → cluster → name → network → publish
make build     # vitepress build
make all       # refresh + build
make serve     # 本地预览
```

## 目录结构

```
src/
├── ingest.py        # 从 We-MP-RSS SQLite 读取文章
├── embed.py         # 嵌入 → ChromaDB
├── cluster.py       # HDBSCAN / K-means 聚类
├── name.py          # LLM 命名 + TF-IDF fallback
├── network.py       # betweenness 桥梁分析
├── publish.py       # 渲染 VitePress markdown + 网络图
└── lib/             # db / vec / llm 封装

site/                # VitePress 站点（publish.py 写入）
out/                 # pipeline 中间产物（gitignore）
articles/            # 历史手工索引（只读）
```

## 设计文档

- `docs/PRD.md` — 产品需求文档
- `docs/architecture.md` — 原始技术方案（已收缩）
- `docs/superpowers/specs/2026-05-21-knowledge-map-mvp-design.md` — MVP 设计 spec（权威）
