# 设计 Spec：技术文章知识地图 MVP

> 日期：2026-05-21
> 状态：设计完成，待实施计划
> 上游文档：[PRD](../../PRD.md)、[原 architecture.md](../../architecture.md)
> 关系：本 spec 对原 architecture.md 的范围做了大幅收缩，作为 MVP 的权威设计

---

## 0. 为什么需要这个 Spec

原 `architecture.md` 列了 5 个 Phase 跨 ~5 周，覆盖 wecom-cli / WeWe RSS / Playwright / Claude Haiku / SQLite / ChromaDB / FastAPI / Vue 3 / VitePress / APScheduler。在 brainstorming 中暴露出三个问题：

1. **按技术模块分阶段，不按用户价值分阶段**：Phase 1 结束没有任何可感知产物
2. **范围接近产品级，但目标是单用户本地工具**：技术栈过重
3. **最高风险（公众号反爬）被推后到 Phase 2**：风险应前置而不是延后兜底

本 spec 通过 5 个核心决策把范围收缩到 6-8 天 MVP，原方案中 Vue / FastAPI / Playwright / APScheduler 全部砍掉或推到二期。

---

## 1. 核心决策（brainstorming 锁定）

| 维度 | 决策 |
|------|------|
| 核心价值 | 关联与发现（PRD 需求 2 + 5） |
| 交付形态 | 领域知识地图：按领域分组报告 + 领域间联系网络 |
| 领域来源 | AI 自动聚类（不预设分类；现有手工 5 分类只作基线对比） |
| 网络图洞察 | 识别"桥梁领域"（高 betweenness centrality 节点） |
| 动态性 | 馆藏库持续扩充（订阅入库走二期）；地图按需重跑（手动 / cron） |

**隐含结论**：订阅入库与地图生成是**两条解耦管道**，通过 SQLite `articles` 表衔接。MVP 只做地图管道，订阅入库走二期。

---

## 2. 总体架构

```
[输入]                  [处理：Makefile 串联 6 个 stage]              [输出]

articles/*.md ──→ ingest → SQLite ──→ embed → ChromaDB
（53 篇基线）         │                          │
                     │                          ↓
                     │                       cluster (HDBSCAN)
                     │                          ↓
                     │                       name (Claude Haiku 命名)
                     │                          ↓
                     │                       network (betweenness 桥梁)
                     │                          ↓
                     └─────────────────────→ publish ──→ VitePress markdown
                                                              ↓
[二期]                                                  vitepress build
WeWe RSS / wecom-cli ─→ ingest                                ↓
                                                          静态站
```

**设计原则**：

1. **管道而非服务** — Makefile + Python 脚本，不引入常驻进程
2. **SQLite 是单一真理源**，ChromaDB 只是向量缓存（可重建）
3. **聚类结果不入库，直接落 JSON + Markdown** — git diff 即历史
4. **二期入库只新增 ingest 数据源**，下游 pipeline 零改动（已是"读 SQLite → 出地图"的纯函数式形态）
5. **MVP 简化但保留扩展位**：数据层不锁死、stage 可替换为 API、VitePress 可与未来 Web UI 并存

---

## 3. 数据模型

```sql
articles (
  id            INTEGER PRIMARY KEY,
  title         TEXT NOT NULL,
  url           TEXT,                 -- 微信原文 / 转载 URL，可能为空
  source        TEXT,                 -- 'wechat' / 'zhihu' / 'csdn' / ...
  source_name   TEXT,                 -- 公众号名（二期 RSS 入库时填）
  manual_tag    TEXT,                 -- 现有 5 分类的归属（仅迁移时填，作聚类基线）
  summary       TEXT,                 -- 可选，未抓全文时为空
  added_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  embedding_id  TEXT                  -- ChromaDB 文档 ID；NULL=未嵌入；'__failed__'=嵌入失败
)
```

**就这一张表**。cluster / edge / centrality 都是聚类的**输出**，每次重跑重新生成，落 `out/*.json` + VitePress markdown，靠 git 看历史。

**Why so simple**：未来加订阅入库 = 多 insert 行；未来加 Web UI = 读这张表 + ChromaDB。MVP 不引入冗余结构。

**ChromaDB Collection**：`articles_v1`，文档 ID = `articles.embedding_id`，metadata 包含 `article_id, title, manual_tag`。

**现有 Markdown 索引退役**：迁移完成后 `articles/*.md` 保留为只读历史快照，新文章只走 SQLite。

---

## 4. 组件清单

```
src/
├── ingest.py        # Markdown 索引解析 → SQLite（articles）
├── embed.py         # SQLite 待嵌入 → OpenAI embedding → ChromaDB（增量）
├── cluster.py       # ChromaDB 向量 → HDBSCAN（或 K-means fallback）→ out/clusters.json
├── name.py          # clusters.json + 簇内 title 列表 → Claude Haiku → out/clusters_named.json
├── network.py       # clusters_named.json → networkx betweenness → out/network.json
├── publish.py       # 三个 json + SQLite → 写 VitePress markdown + network.html
└── lib/
    ├── db.py        # SQLite 连接 + 通用查询
    ├── vec.py       # ChromaDB 客户端封装
    └── llm.py       # Claude Haiku 调用（含重试 / cache）

site/                # VitePress 站点（publish.py 写入此处）
├── docs/
│   ├── index.md     # 主页：嵌入 network.html + Top 桥梁领域 + 领域索引
│   ├── domains/
│   │   └── *.md     # 每个领域一页（领域摘要 + 文章列表 + 关联领域）
│   └── articles/
│       └── *.md     # 每篇文章 stub（标题 + 摘要 + 外链跳转）
└── package.json

out/                 # pipeline 中间产物（gitignore）
├── clusters.json
├── clusters_named.json
└── network.json

scripts/
└── migrate_markdown.py   # 一次性：现有 articles/*.md → SQLite

Makefile
```

**Makefile 目标**：

```
make migrate    # 一次性：现有 articles/*.md → SQLite
make refresh    # ingest → embed → cluster → name → network → publish
make build      # vitepress build
make serve      # vitepress dev（本地预览）
make all        # refresh + build
```

每个 stage 只通过文件交互（SQLite + JSON + Markdown），失败可单点重跑。

---

## 5. 技术选型

| 项目 | 选 | 理由 |
|------|----|------|
| Embedding | OpenAI `text-embedding-3-small` | 53 篇成本 < $0.01；二期 RSS 增量也廉价 |
| 聚类 | HDBSCAN（首选）+ K-means fallback | HDBSCAN 自动 k；噪音过多时降级 K-means(k=`round(sqrt(N/2))`) |
| 桥梁分析 | networkx `betweenness_centrality` | 53 节点零压力，Python 标配 |
| LLM 命名 | Claude Haiku 4.5 | 任务简单，比 Sonnet 省 90% |
| 向量库 | ChromaDB（本地文件） | 零运维，SQLite 底层 |
| 元数据 | SQLite | 已选，轻量无服务 |
| 网络图 | D3 force-directed graph（静态 HTML） | 静态嵌入 VitePress 简单 |
| 站点 | VitePress | 已选 |
| 包管理 | `uv` + `pnpm` | 速度优先 |

**砍掉的原方案项**：

| 原方案 | 砍掉理由 |
|--------|---------|
| Vue 3 前端 | 单用户 + 静态地图，VitePress 已足够 |
| FastAPI + Uvicorn | batch pipeline 不需要常驻服务 |
| APScheduler | Makefile + cron 已够 |
| PM2 | 没有常驻进程，不需要进程管理 |
| Playwright 抓全文 | MVP 只需 title + manual_tag 做聚类；全文留二期 D |
| WeWe RSS / wecom-cli | 订阅入库推到二期 A |

---

## 6. 数据流（详细）

```
[起点] articles/*.md
   ↓
[1. ingest] python -m src.ingest articles/
   解析 Markdown 索引 → SQLite articles 表
   字段：title, url, source, manual_tag
   ↓
[2. embed] python -m src.embed
   读 articles WHERE embedding_id IS NULL OR = '__failed__'
   调用 OpenAI embedding API → 写 ChromaDB
   更新 articles.embedding_id
   ↓
[3. cluster] python -m src.cluster
   从 ChromaDB 拿所有向量 → HDBSCAN
   若噪音点 > 30%：降级 K-means(k=sqrt(N/2))
   输出 out/clusters.json: { article_id → cluster_id }
   ↓
[4. name] python -m src.name
   读 clusters.json + 各簇内 article titles
   调用 Claude Haiku → 输出 out/clusters_named.json:
     [{ cluster_id, name, description, article_ids }]
   ↓
[5. network] python -m src.network
   计算 cluster_edges:
     边权重 = 簇 A 与簇 B 之间所有 article 对的 Top-K 语义相似度之和（K=5）
     即：从簇 A 取所有 article，对每个 article 在簇 B 找最相似的 1 个，累加相似度
     manual_tag 不参与边权重，仅在最终报告里作为"聚类 vs 人工分类对比"的元信息
   计算 betweenness_centrality
   标记 Top-3 桥梁领域
   输出 out/network.json: { nodes, edges, bridges }
   ↓
[6. publish] python -m src.publish
   读三个 JSON + SQLite → 写：
     site/docs/index.md            (主页 + 嵌入 network.html iframe)
     site/docs/network.html        (D3 静态网络图)
     site/docs/domains/*.md        (每个领域一页)
     site/docs/articles/*.md       (每篇文章 stub)
   ↓
[终点] vitepress build → site/.vitepress/dist/
```

---

## 7. 错误处理（每 stage 自治）

| 失败点 | 策略 |
|--------|------|
| Embedding API 429 / 网络抖动 | 指数退避重试 3 次；持续失败标 `'__failed__'`，下次 refresh 自动重试 |
| HDBSCAN 噪音点 > 30% | 降级 K-means(k=`round(sqrt(N/2))`)，warning 记录 |
| LLM 命名失败 / 超时 | fallback 用簇内最高频 title 关键词（jieba 分词 + TF-IDF） |
| 桥梁分析无明显桥梁（最高 betweenness < 阈值） | 输出 warning，仍列出 Top-3，不阻断 |
| 任一 stage 异常 | exit 非零，Makefile 停在此处；中间 JSON 保留供排查 |

---

## 8. 测试策略

- **集成测试为主**：mock 5-8 篇文章 → 跑完整 pipeline → 断言 markdown 输出存在 + 关键字段（领域数、桥梁列表）
- **单元测试**：纯函数模块 — markdown 索引解析、聚类 fallback 触发逻辑、桥梁阈值判定
- **回归基线**：53 篇跑一次锁定聚类 snapshot（领域数 + 桥梁名）→ 后续偏离过大告警，验证聚类稳定性
- **不测**：LLM 生成文本的精确字符串（不稳定）；ChromaDB 内部行为
- **覆盖率目标**：80%，但权重偏向集成测试 + 关键 fallback 逻辑

---

## 9. MVP 阶段切分

### Phase 1 — 数据基线（2-3 天）

任务：

- [ ] `scripts/migrate_markdown.py`：解析现有 5 个 `articles/*.md` 索引 → SQLite
- [ ] `src/embed.py`：跑通 OpenAI embedding → ChromaDB
- [ ] `lib/db.py`、`lib/vec.py`、`lib/llm.py` 基础设施

验收：`SELECT COUNT(*) FROM articles WHERE embedding_id IS NOT NULL AND embedding_id != '__failed__'` = 53

### Phase 2 — 聚类 + 命名 + 桥梁（2-3 天，核心不确定点）

任务：

- [ ] `src/cluster.py`：HDBSCAN + K-means fallback
- [ ] `src/name.py`：Claude Haiku 命名（含 jieba TF-IDF fallback）
- [ ] `src/network.py`：networkx betweenness + 桥梁标记

验收：

1. 跑完整 pipeline 到 `out/*.json`
2. **人工 review 聚类结果**，与 manual_tag 做基线对比：
   - 若 AI 聚类只是 manual_tag 的复刻 → 调整 HDBSCAN 参数：
     - 减小 `min_cluster_size`（默认 5 → 试 3）让小子领域显现
     - 减小 `min_samples` 让边界点更易归簇
     - 或改用 cosine 距离 metric（如默认是 euclidean）
   - 若调参 2-3 轮后仍无新洞察 → 产品假设不成立，暂停 Phase 3，重新讨论方向
3. Top-3 桥梁领域符合直觉（你能解释"为什么这个领域是桥梁"）

### Phase 3 — VitePress 发布（1-2 天）

任务：

- [ ] `src/publish.py`：模板渲染（领域页 + 网络图 HTML）
- [ ] VitePress 最小主题配置
- [ ] `Makefile` 串联所有 stage

验收：`make all` 一键跑通；本地 `make serve` 能交互看网络图，点节点跳领域页。

### MVP 完成线

把 VitePress 站放本地浏览，**用一周时间问自己**：这张地图有没有改变我找文章 / 选下一篇读什么的方式？

- 有 → 进入二期
- 没有 → 重新讨论核心价值假设，可能要换交付形态

---

## 10. 二期路线图（按需排，不预先承诺）

| 二期项 | 触发条件 | 预估 |
|--------|---------|------|
| A. 订阅入库（WeWe RSS + wecom-cli） | 手动添加新文章成为负担时 | 1-2 周（含反爬风险） |
| B. 地图 cron 定时重跑 | A 完成后馆藏库持续增长时 | 1 天 |
| C. Web UI（Vue 3 + FastAPI） | VitePress 静态站真的不够用时 | 1-2 周 |
| D. 全文抓取 + LLM 摘要 | title 级聚类质量不够时 | 1 周（含 Playwright cookie 维护） |
| E. 关联推荐 API | 二期 C 时一起做 | 含在 C 内 |

---

## 11. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| 53 篇样本太小，聚类不稳定 | 中 | 高（产品假设破产） | Phase 2 验收门槛卡住；不通过则暂停 Phase 3 |
| OpenAI API 配额 / 网络抖动 | 低 | 低 | 指数退避 + 失败标记，下次重试 |
| Claude Haiku 命名质量差 | 中 | 中 | jieba TF-IDF fallback 兜底，至少可用 |
| 网络图 D3 调参耗时 | 中 | 低 | 用现成模板，不追求精美 |
| 二期 A 的微信反爬虫 | 高 | 中 | 已隔离到二期，不阻塞 MVP |

---

## 12. 验收标准（MVP 完成判定）

1. `make all` 一键跑通 53 篇文章 → VitePress 静态站
2. 站点首页能交互看网络图（D3 force-directed），节点可点击
3. 每个领域一页 markdown，含：领域名、领域描述、文章列表、关联领域
4. 桥梁领域 Top-3 标记清晰，能解释为什么是桥梁
5. 聚类回归 snapshot 已锁定，重复跑结果稳定（领域数偏移 ≤ ±1，桥梁列表 ≥ 2/3 重合）
6. 集成测试通过，单元测试覆盖率 ≥ 80%（核心模块）

---

## 13. 不做的事（明确范围边界）

- Web UI（Vue 3 / FastAPI / Uvicorn）
- 常驻服务 / APScheduler / PM2
- Playwright 抓全文（MVP 用 title + manual_tag 就够）
- WeWe RSS / wecom-cli 订阅入库（推到二期 A）
- 多用户 / 移动端 / 企业微信机器人（PRD 已声明非目标）
- 全网文章推荐（PRD 已声明留第二期）
- 聚类历史版本管理（git diff 即历史）
- 关联推荐 API（推到二期 E）
