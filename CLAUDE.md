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

## 链接状态

- 微信公众号原文：30 篇（通过 Tavily `site:mp.weixin.qq.com` 搜索获取）
- 转载链接（fallback）：16 篇（知乎、CSDN、阿里云等平台转载）
- 未找到链接：7 篇

## 待解决问题

### 1. 23 篇文章未找到微信公众号原文 URL

搜索引擎对微信公众号文章的收录率有限（约 57%）。尝试过的方案：
- `site:mp.weixin.qq.com` Google/Bing 搜索
- Tavily `--include-domains mp.weixin.qq.com` 搜索
- 搜狗微信搜索（反爬虫机制，无法自动化）

可能解决方案：
- 用户从微信收藏中手动复制链接补充
- 通过微信读书或微信 PC 端搜索功能找到原文
- 使用浏览器自动化（Playwright）操作搜狗微信搜索，绕过反爬

### 2. 企业微信 API 只返回消息标题，不含 URL

wecom-cli 的 `get_message` API 对文章卡片类消息只返回 `[标题]` 文本，不含原始链接。
合并转发消息只返回 `**多选转发begin****多选转发end**` 标记，内容完全丢失。

## 新增文章流程

1. 在企业微信群转发文章（单条转发，不要合并转发）
2. 用 `wecom-cli msg get_message` 拉取新消息
3. 根据标题用 `tvly search 'site:mp.weixin.qq.com "标题"' --include-domains mp.weixin.qq.com --max-results 3 --json` 搜索 URL
4. 添加到对应分类索引和总索引

## 后续演进方向

- 抓取文章全文并存储本地副本
- AI 自动生成摘要和关键要点
- 文章间关联关系（知识图谱）
- VitePress 站点生成（团队分享）
- 定期从企微群拉取新文章（自动化流水线）
