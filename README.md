# 微信公众号技术文章知识管理系统

从企业微信群聊中收藏技术文章，自动抓取全文、AI 摘要、向量关联推荐，并生成团队分享静态站。

## 文档

- [PRD — 产品需求](docs/PRD.md)
- [技术方案](docs/architecture.md)

## 现有文章索引

53 篇手动整理的文章，作为项目初始数据：

```
articles/
├── index.md                # 总索引
├── ai-coding.md            # AI Coding / Claude Code
├── harness-engineering.md  # Harness / Spec / SDD
├── agent-architecture.md   # Agent 架构 / Skills
├── knowledge-management.md # RAG / Wiki / 记忆
└── industry-insights.md    # 行业思考
```

## 数据来源

- 企业微信群聊转发消息（通过 wecom-cli 读取）
- 微信公众号订阅（通过 WeWe RSS 自动拉取）
