# CLAUDE.md

## 项目说明

技术文章收藏与整理项目。文章来源为企业微信群聊转发消息，通过 wecom-cli 读取。

## 目录结构

- `articles/index.md` — 总索引（53 篇文章，含编号、标题、URL、来源、收藏日期）
- `articles/ai-coding.md` — AI Coding / Claude Code（21 篇）
- `articles/harness-engineering.md` — Harness Engineering / Spec Coding / SDD（11 篇）
- `articles/agent-architecture.md` — Agent 架构 / Skills（12 篇）
- `articles/knowledge-management.md` — 知识管理 / RAG / Wiki（4 篇）
- `articles/industry-insights.md` — 行业思考（5 篇）

## 新增文章流程

1. 在企业微信群转发文章（单条转发，不要合并转发）
2. 用 `wecom-cli msg get_message` 拉取新消息
3. 根据标题搜索原始 URL
4. 添加到对应分类索引和总索引

## 后续演进方向

- 抓取文章全文并存储本地副本
- AI 自动生成摘要和关键要点
- 文章间关联关系（知识图谱）
- VitePress 站点生成（团队分享）
- 定期从企微群拉取新文章（自动化流水线）
