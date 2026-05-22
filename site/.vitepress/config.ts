import { defineConfig } from 'vitepress'

export default defineConfig({
  title: '技术文章知识地图',
  description: '53 篇技术文章的领域自动聚类与桥梁分析',
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '领域', link: '/domains/' },
    ],
  },
})
