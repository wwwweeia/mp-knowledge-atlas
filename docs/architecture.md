# 技术方案: 微信公众号技术文章知识管理系统

> 状态: 方案设计中  
> 更新: 2026-05-21

---

## 整体架构

```
输入层                      处理层                    存储层
──────                      ──────                    ──────
企业微信群
  └─ wecom-cli ──┐
                 ├──→ URL 解析 ──→ Playwright 抓全文
微信公众号订阅    │               └──→ Claude Haiku 摘要+标签
  └─ WeWe RSS ──┘                └──→ Embedding 向量化
                                      │
                                 SQLite (元数据)
                                 ChromaDB (向量，本地)

查询层
──────
FastAPI ──→ Web UI（日常使用）
        └──→ VitePress 生成器（团队分享）
```

---

## 技术选型

| 模块 | 选型 | 理由 |
|------|------|------|
| 公众号订阅 | WeWe RSS (Docker) | 唯一可靠的公众号 RSS 方案，本地部署 |
| 全文抓取 | Playwright Python | 微信文章需要登录态，可注入 cookie |
| AI 摘要+标签 | Claude Haiku | 成本低，速度快，足够处理文章摘要 |
| Embedding | `text-embedding-3-small` 或本地 `nomic-embed-text` (Ollama) | 前者质量好，后者离线省钱 |
| 向量库 | ChromaDB (本地) | 零配置，SQLite 底层，完全本地 |
| 元数据 | SQLite | 轻量，无服务进程，够用 |
| 后端 | FastAPI + Uvicorn | Python 生态，开发快 |
| 前端 | Vue 3 + Vite | 轻量，足够 |
| 团队分享 | VitePress | 从 SQLite 生成 Markdown，已有 53 篇基础 |
| 调度 | APScheduler（内嵌 FastAPI） | 不引入额外进程 |
| 进程管理 | PM2 | 与现有工具统一 |

---

## 数据模型

```sql
-- 文章表
articles (
  id           INTEGER PRIMARY KEY,
  title        TEXT NOT NULL,
  url          TEXT,                  -- 微信原文 URL，可能为空
  content      TEXT,                  -- 全文（Playwright 抓取后）
  summary      TEXT,                  -- Claude Haiku 生成的摘要
  tags         TEXT,                  -- JSON 数组，如 ["AI Coding", "Agent"]
  source_id    INTEGER,               -- 关联公众号
  published_at DATETIME,
  added_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  embedding_id TEXT                   -- ChromaDB 中的文档 ID
)

-- 公众号订阅表
sources (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,        -- 公众号名称
  wechat_id     TEXT,                 -- 公众号微信 ID（biz）
  rss_url       TEXT,                 -- WeWe RSS 生成的 RSS URL
  subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

---

## 目录结构（规划）

```
tech-articles-collector/
├── articles/              # 现有 Markdown 索引（保留，作为数据迁移源）
├── docs/                  # 文档（本文件所在）
│   ├── PRD.md
│   └── architecture.md
├── src/
│   ├── collector/         # 数据采集
│   │   ├── wecom.py       # wecom-cli 封装，拉取新消息
│   │   └── rss.py         # WeWe RSS 拉取，新文章入库
│   ├── scraper/           # 全文抓取
│   │   └── wechat.py      # Playwright 抓取微信文章正文
│   ├── processor/         # AI 处理
│   │   ├── summarizer.py  # Claude Haiku 摘要 + 标签
│   │   └── embedder.py    # Embedding 生成
│   ├── storage/           # 数据存储
│   │   ├── db.py          # SQLite 操作
│   │   └── vector.py      # ChromaDB 操作
│   ├── api/               # FastAPI 后端
│   │   ├── main.py
│   │   └── routes/
│   └── vitepress/         # VitePress 静态站生成
│       └── generator.py   # SQLite → Markdown → VitePress
├── web/                   # Vue 3 前端
├── scripts/
│   └── migrate.py         # 现有 53 篇 Markdown → SQLite 迁移脚本
└── docker-compose.yml     # WeWe RSS 容器
```

---

## 开发计划

### Phase 1 — 数据地基（目标：1周）
- [ ] SQLite schema 初始化
- [ ] ChromaDB 本地初始化
- [ ] 迁移脚本：53 篇 Markdown 索引 → SQLite
- [ ] Playwright 抓取微信文章全文（注入 cookie）
- [ ] Claude Haiku 生成摘要 + 自动打标签

### Phase 2 — 订阅流水线（目标：1周）
- [ ] WeWe RSS Docker 部署
- [ ] 添加第一批公众号订阅
- [ ] APScheduler 定时拉取 RSS → 新文章入库 → 抓全文 → AI 处理

### Phase 3 — 关联推荐（目标：3天）
- [ ] 文章入库时同步写 embedding 到 ChromaDB
- [ ] 查询接口：给定文章 ID，返回 Top-K 相似文章
- [ ] 新文章入库后自动关联到已有知识图谱领域

### Phase 4 — Web UI（目标：1周）
- [ ] FastAPI CRUD 接口
- [ ] Vue 3 前端：文章列表、搜索、详情页（含关联推荐侧栏）

### Phase 5 — VitePress（目标：3天）
- [ ] 生成脚本：SQLite → Markdown → VitePress build
- [ ] 部署到本地或内网

---

## 风险与注意事项

### 最大风险：微信公众号抓取
微信公众号没有官方 RSS，所有方案依赖逆向工程：

- WeWe RSS 需要微信 PC 端扫码登录，session 会周期性过期
- Playwright 抓取正文需要有效 cookie，需定期刷新

**应对策略**：
- Phase 1 先用 Tavily 补全 URL，Playwright 抓全文作为增强，不阻塞主流程
- WeWe RSS session 过期时发送本地通知提示重新登录

### 现有资产复用

| 现有资产 | 复用方式 |
|----------|----------|
| 53 篇 Markdown 索引 | Phase 1 迁移脚本导入 SQLite |
| wecom-cli | 继续拉新消息标题，触发 Tavily 搜 URL |
| Tavily 搜索 | 继续作为 URL 解析层（覆盖率 57%） |
