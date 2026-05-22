# mp-knowledge-atlas

> 微信公众号知识地图生成器：自动采集技术文章，通过 AI 摘要 + 向量嵌入 + 聚类 + 网络分析，生成可交互的领域知识地图，发布为 Vue 3 SPA 静态站。

## 效果预览

- **知识地图**：技术领域自动分簇，可视化展示各领域文章分布及跨域关联
- **全文检索**：支持按标题 / 关键词搜索，实时过滤
- **网络图**：Cytoscape.js 渲染文章间语义相似度关系图，突出显示跨领域桥接节点

## 架构概览

```
We-MP-RSS (Docker 本地)
       │  微信公众号订阅源
       ▼
   ingest   →  clean   →  summarize   →  embed   →  cluster   →  network   →  publish
    读取          HTML         DeepSeek      Ollama      HDBSCAN       语义            data.json
   SQLite         清洗          摘要+关键词   向量嵌入     聚类+命名      桥梁分析
                                                        ChromaDB
                                                           │
                                                           ▼
                                                    Vue 3 SPA 前端
```

### 外部服务

| 服务 | 用途 |
|------|------|
| [We-MP-RSS](https://github.com/hao-ai-lab/we-mp-rss) | 微信公众号文章抓取（Docker 本地部署） |
| Ollama `nomic-embed-text:v1.5` | 向量嵌入（本地） |
| DeepSeek API | LLM 摘要生成 + 聚类命名 |
| ChromaDB | 向量存储（本地 `data/chroma/`） |

## 快速开始

### 依赖

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- [Ollama](https://ollama.com)（需拉取 `nomic-embed-text:v1.5`）
- DeepSeek API Key
- We-MP-RSS 本地实例（见其 README）

### 安装

```bash
git clone https://github.com/wwwweeia/mp-knowledge-atlas.git
cd mp-knowledge-atlas

# 安装依赖
uv sync

# 配置
cp .env.example .env
# 编辑 .env 填写 DEEPSEEK_API_KEY 等
```

### 运行 Pipeline

```bash
make refresh   # 增量刷新（推荐日常使用）
make rebuild   # 全量重建（首次或调试）
make serve     # 本地预览 http://localhost:5173
make test      # 运行测试
```

`refresh` 流程：从 We-MP-RSS SQLite 读取新文章 → HTML 清洗 → DeepSeek 摘要 → Ollama 向量嵌入 → HDBSCAN 聚类 → betweenness 桥梁分析 → 生成 `data.json`。

典型耗时：无新数据约 30 秒；有新文章取决于 LLM 摘要数量（约 1–3 分钟）。

## 目录结构

```
src/
├── ingest.py        # 从 We-MP-RSS 导入 + 全文回填
├── clean.py         # HTML → 纯文本
├── summarize.py     # DeepSeek 结构化摘要
├── embed.py         # 向量嵌入 → ChromaDB
├── cluster.py       # HDBSCAN/K-means 聚类 + LLM 命名
├── network.py       # betweenness 桥梁分析
├── publish.py       # 聚合数据 → data.json
└── lib/             # 工具库（db、html、llm、embedding、vec）

site/                # Vue 3 SPA 前端（CDN 引入，无构建步骤）
├── index.html
├── assets/
│   ├── app.js            # Vue 3 路由 + 组件
│   ├── app.css           # Linear 暗色主题
│   └── network-graph.js  # Cytoscape.js 网络图
└── data/
    └── data.json         # publish.py 生成的聚合数据

articles/            # 53 篇历史手工索引（只读快照）
tests/               # pytest 集成测试
```

## Pipeline 状态机

每篇文章经历以下 stage：

```
ingested → cleaned → summarized → embedded
```

各阶段幂等——已完成的自动跳过，失败则停留当前 stage 等待下次重试。

## 配置

`.env` 参考 `.env.example`：

```env
DEEPSEEK_API_KEY=your_key_here
WEMPRSS_DB_PATH=/path/to/we_mp_rss.db  # We-MP-RSS SQLite 路径
```

## License

MIT
