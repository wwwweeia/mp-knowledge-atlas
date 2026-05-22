# Graph Visual Fix — Handoff Prompt

## 项目

技术文章知识地图，Vue 3 CDN SPA（无构建步骤）。知识图谱使用 Cytoscape.js 渲染 18 个领域节点。

## 当前状态

已完成的知识图谱优化：
- 节点：SVG radial gradient 背景（通过 `background-image: data(svgBg)` 渲染），内部显示文章数量（原生 label），尺寸 28-64px
- 边：粗细+色相+透明度三维映射（`mapData(weight, 10, 14, ...)`）
- 交互：搜索定位、布局切换（concentric/cose-bilkent/circle）、边权重滑块、拖拽固定+重置、hover tooltip
- 控件：顶部搜索框、右上布局切换按钮、右侧图例+滑块、底部统计栏+重置按钮

**全部功能已实现，只有一个视觉 bug 需要修复。**

## Bug：节点名称标签位置错误

### 现象

节点名称标签出现在节点圆的**上方**，而非设计要求的**下方**。

### 原因

使用 `cytoscape-node-html-label` 扩展在节点上叠加 HTML 标签。当前配置：

```javascript
// site/assets/network-graph.js 约第 244 行
cy.nodeHtmlLabel([{
  query: 'node',
  valign: 'top',
  halign: 'center',
  valignBox: 'bottom',   // ← 问题在这里
  halignBox: 'center',
  cssClass: 'gn-label',
  tpl: function(d) {
    return '<div class="gn-name" data-nid="' + d.id + '" style="' +
      'margin-top:4px;' +
      'font-size:' + d.nameSize + 'px;' +
      'color:' + d.nameColor + '">' +
      d.name + '</div>';
  }
}]);
```

`valignBox: 'bottom'` 的实际行为是"标签容器底部对齐节点底部"，导致标签出现在节点上方。

尝试过的方案及结果：
- `valignBox: 'center'` + `margin-top: dim/2 + 6` → 标签在节点内部
- `valignBox: 'center'` + `margin-top: dim + 6` → 标签仍在节点内部（因为标签 div 本身被居中，margin 只调整了 div 内部布局）
- `valignBox: 'bottom'` + `margin-top: 4` → 标签出现在节点上方（当前状态）

### 修复方向

nodeHtmlLabel 的 `valignBox` 参数控制标签容器相对节点的定位：
- `'center'` → 标签容器居中于节点中心
- `'top'` → 标签容器在节点上方
- `'bottom'` → 标签容器底部对齐节点底部（效果是标签在上方）

**推荐修复方案**：用 `valignBox: 'center'` + 在 tpl 中用 CSS 精确控制偏移。关键是要理解：标签 div 被 `transform: translate(-50%, -50%)` 居中在节点上，所以需要计算正确的 margin-top。

数学推导：
- 标签 div 高度 = margin-top + text-height（约 14-16px）
- 标签 div 被 `valignBox: 'center'` 居中：div top = node_center - total_height/2
- 文字起始位置 = node_center - total_height/2 + margin-top = node_center + (margin-top - text_height) / 2
- 要让文字在节点底部（node_center + dim/2）下方 4px：
  margin-top = dim + text_height + 4

所以正确的 margin-top 公式是 `dim + 20`（dim 是节点像素直径，20 = 16px文字高度 + 4px间距）。

或者更简单的方案：直接写一个固定高度的空占位 div 把文字推下去：

```javascript
tpl: function(d) {
  return '<div style="display:flex;flex-direction:column;align-items:center">' +
    '<div style="height:' + (d.dim + 4) + 'px"></div>' +  // 占位，高度=节点直径+间距
    '<div class="gn-name" data-nid="' + d.id + '" style="' +
    'font-size:' + d.nameSize + 'px;' +
    'color:' + d.nameColor + '">' +
    d.name + '</div></div>';
}
```

这个方案的原理：flex 容器总高度 = dim + 4 + text_height。被 valignBox:'center' 居中后：
- flex 容器 top = node_center - (dim + 4 + text_height) / 2
- 占位 div 底部 = node_center - (dim + 4 + text_height)/2 + dim + 4 = node_center + (dim + 4 - text_height)/2
- 对于 dim=64px, text=14px: 底部 = center + 27px，但节点底部在 center + 32px

**这个方案也不对**。因为居中后总高度被平分，占位区域的有效偏移只有 (dim+4-text)/2，不够。

### 最终正确方案

不要试图和 valignBox 居中机制做斗争。**用绝对定位绕过它**：

```javascript
tpl: function(d) {
  // 标签容器被 nodeHtmlLabel 定位在节点位置（通过 transform）
  // 用绝对定位把名称精确放在节点底部下方
  return '<div class="gn-label-inner" style="position:relative;width:0;height:0">' +
    '<div class="gn-name" data-nid="' + d.id + '" style="' +
    'position:absolute;' +
    'top:' + (d.dim / 2 + 4) + 'px;' +  // 节点半径 + 间距
    'left:50%;' +
    'transform:translateX(-50%);' +
    'white-space:nowrap;' +
    'font-size:' + d.nameSize + 'px;' +
    'color:' + d.nameColor + '">' +
    d.name + '</div></div>';
}
```

原理：
- 外层 div `width:0; height:0` → valignBox 无论怎么居中，这个 div 都是 0 尺寸的点，精确在节点中心
- 内层用 `position:absolute` + `top: dim/2 + 4` → 从节点中心往下偏移 半径+4px
- 这个方案和 valignBox 的值无关，用 'center' 即可

## 涉及文件

| 文件 | 改动 |
|------|------|
| `site/assets/network-graph.js` | 修改 nodeHtmlLabel 的 tpl 函数（约第 244-260 行） |

**只改这一处 tpl 函数，其他代码不动。**

## 验证方法

1. `cd /Users/wqw/Documents/idea_work/business-learning/tech-articles-collector/site && python3 -m http.server 5173`
2. 打开 http://localhost:5173 → 点击「全屏展开」
3. 确认节点名称出现在圆的**正下方**，间距约 4px
4. 切换三种布局（同心圆/力导向/环形），确认标签位置在所有布局下都正确
5. 回首页确认缩略图标签也正确
6. hover 节点时标签 dim/highlight 是否正常

## 注意事项

- 保持 CDN 方式，不引入构建工具
- 只改 tpl 函数返回的 HTML，不改 nodeHtmlLabel 的配置参数（query、cssClass 等不要动）
- `data-nid` 属性必须保留（hover 时的 DOM 操作依赖它）
- 项目使用 IIFE 包裹，变量是闭包内的，不要加 export
