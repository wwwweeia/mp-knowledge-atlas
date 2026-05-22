# Cytoscape.js 知识图谱视觉与交互优化

## 背景

当前图谱有 18 个领域节点、153 条边（已做 top-N 过滤），使用 concentric 布局。节点是深灰圆形 + 底部截断文字标签，边是灰色细线，视觉和交互体验偏朴素。

## 技术方案

**Cytoscape.js Core + node-html-label 扩展**。保留现有 Cytoscape 架构，通过 HTML overlay 层实现节点渐变、内部数字、发光等效果。新增 `cytoscape-cose-bilkent` CDN 用于力导向布局。

CDN 新增：
- `cytoscape-node-html-label` — 节点 HTML overlay（渐变、内部数字、CSS 动画）
- `cytoscape-cose-bilkent` — 高质量力导向布局

## 视觉设计

### 节点

- **渐变填充**：`linear-gradient(135deg, #3a3f5c, #5e6ad2)` 普通节点，`linear-gradient(135deg, #5e6ad2, #8b5cf6)` 桥梁节点，小节点用 `linear-gradient(135deg, #2a2d3a, #3d4250)`
- **内部数字**：节点中心显示文章数量（白字，按节点尺寸调整字号）
- **尺寸层次**：log scale 映射到 28px-64px（原 20-44px），拉大差距
- **桥梁节点**：更大尺寸、更亮渐变、`box-shadow` 外发光 + CSS `pulse` 脉冲动画
- **标签**：节点下方全名显示（不再截断），`text-shadow` 或半透明背景板保证可读性

### 边

- **三维映射**：粗细 + 色相 + 透明度同时变化
  - 强关联：`stroke-width: 3px`, `color: #5e6ad2`, `opacity: 0.75`
  - 中等：`stroke-width: 1.8px`, `color: #4a5090`, `opacity: 0.45`
  - 弱关联：`stroke-width: 0.8px`, `color: #353860`, `opacity: 0.25`
- 通过 Cytoscape `mapData()` 映射 weight 到 width 和 color

### Hover 效果

- **平滑过渡**：`transition-duration: 0.3s`（原 0.2s）
- **高亮关联边**：相连的边变亮紫色 `#5e6ad2`，opacity 提升到 0.9，宽度增加
- **Dimmed 状态**：非关联节点和边 opacity 降到 0.08（原 0.12/0.04）
- **Rich tooltip**：显示领域名、文章数、桥梁标记、关联领域列表

## 交互功能

### 搜索定位

- 图谱顶部居中添加搜索输入框
- 输入关键词实时匹配节点名称
- 匹配节点高亮闪烁（`animation: flash`），视角自动 pan + animate 到匹配节点
- ESC 清空搜索

### 布局切换

- 右上角三个按钮：同心圆（concentric）/ 力导向（cose-bilkent）/ 环形（circle）
- 切换时 `cy.layout().run()` 带动画过渡
- 当前激活的按钮高亮

### 边权重阈值滑块

- 右侧面板添加 range slider
- 拖动时过滤 weight < threshold 的边（`cy.edges().hide()/.show()`）
- 实时响应

### 节点拖拽固定

- 拖拽后节点位置固定（`node.grabify()` + `node.position()` 保持）
- 底部栏添加「重置布局」按钮，重新运行当前布局算法

### 缩略图交互

- HomeView 缩略图支持 hover 显示节点名称（tooltip）
- 点击节点直接跳转对应领域页

## 文件改动范围

| 文件 | 改动 |
|------|------|
| `site/index.html` | 新增 node-html-label、cose-bilkent CDN |
| `site/assets/network-graph.js` | 重写节点样式、HTML label 模板、hover 逻辑、布局切换、搜索、阈值过滤、拖拽固定 |
| `site/assets/app.js` | GraphView 增加搜索/布局/滑块控件，HomeView 缩略图增加交互 |
| `site/assets/app.css` | 新增节点 HTML label 样式、脉冲动画、搜索框、控件面板样式 |

## 不改动的部分

- Python 后端 pipeline 不动
- data.json 结构不动
- DomainView / ArticleView / NavBar 不动（除非缩略图交互需要微调 HomeView）
- 保持 CDN 引入，不引入构建工具
