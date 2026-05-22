// site/assets/app.js
// Vue 3 SPA for Knowledge Map — Linear dark theme

const { createApp, ref, computed, onMounted, watch, nextTick } = Vue;
const { createRouter, createWebHistory } = VueRouter;

// ==========================================
// Data Store
// ==========================================
const store = {
  data: ref(null),
  loading: ref(true),
  async load() {
    try {
      const resp = await fetch("/data/data.json");
      store.data.value = await resp.json();
    } catch (e) {
      console.error("Failed to load data:", e);
    } finally {
      store.loading.value = false;
    }
  },
};

// ==========================================
// Components
// ==========================================

// ---- NavBar ----
const NavBar = {
  setup() {
    const searchQuery = ref("");
    const showResults = ref(false);
    const searchInput = ref(null);

    const searchResults = computed(() => {
      if (!searchQuery.value.trim() || !store.data.value) return null;
      const q = searchQuery.value.toLowerCase();
      const d = store.data.value;

      const domains = d.domains.filter(
        (dom) =>
          dom.name.toLowerCase().includes(q) ||
          dom.keywords.some((k) => k.toLowerCase().includes(q))
      );

      const articles = d.domains
        .flatMap((dom) => dom.articles)
        .filter((a) => a.title.toLowerCase().includes(q))
        .slice(0, 8);

      return { domains: domains.slice(0, 5), articles };
    });

    function onSearchFocus() {
      showResults.value = true;
    }

    function onSearchBlur() {
      setTimeout(() => {
        showResults.value = false;
      }, 200);
    }

    function goTo(path) {
      searchQuery.value = "";
      showResults.value = false;
      router.push(path);
    }

    return { searchQuery, showResults, searchInput, searchResults, onSearchFocus, onSearchBlur, goTo };
  },
  template: `
    <nav class="nav-bar">
      <div class="nav-brand">
        <router-link to="/" class="logo">◎ 知识地图</router-link>
        <span class="subtitle">技术文章知识地图</span>
      </div>
      <div style="position:relative">
        <input
          ref="searchInput"
          class="search-input"
          v-model="searchQuery"
          @focus="onSearchFocus"
          @blur="onSearchBlur"
          placeholder="⌘ 搜索文章、领域..."
        />
        <div class="search-results" v-if="showResults && searchResults">
          <div v-if="searchResults.domains.length" class="group-label">领域</div>
          <a
            v-for="d in searchResults.domains"
            :key="'d-'+d.id"
            class="search-item"
            @click="goTo('/domain/' + d.id)"
          >
            {{ d.name }}
            <span class="meta">{{ d.article_count }} 篇</span>
          </a>
          <div v-if="searchResults.articles.length" class="group-label">文章</div>
          <a
            v-for="a in searchResults.articles"
            :key="'a-'+a.id"
            class="search-item"
            @click="goTo('/article/' + a.id)"
          >
            {{ a.title }}
            <span class="meta">{{ a.source }}</span>
          </a>
        </div>
      </div>
    </nav>
  `,
};

// ---- Home Dashboard ----
const HomeView = {
  setup() {
    const data = computed(() => store.data.value);
    return { data };
  },
  template: `
    <div v-if="data">
      <!-- Stats Row -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="label">总文章</div>
          <div class="value">{{ data.stats.total_articles }}</div>
        </div>
        <div class="stat-card">
          <div class="label">领域聚类</div>
          <div class="value">{{ data.stats.total_domains }}</div>
        </div>
        <div class="stat-card">
          <div class="label">桥梁领域</div>
          <div class="value accent">{{ data.stats.bridge_domains }}</div>
        </div>
        <div class="stat-card">
          <div class="label">数据源</div>
          <div class="value">{{ data.stats.sources }} <span style="font-size:13px;color:var(--text-muted)">公众号</span></div>
        </div>
      </div>

      <!-- Main: Network + Domains -->
      <div class="two-col" style="height:520px">
        <div class="card" style="position:relative;overflow:hidden;flex:1">
          <div style="position:absolute;top:12px;left:12px;color:var(--text-muted);font-size:12px">知识图谱</div>
          <div style="position:absolute;bottom:12px;right:12px;z-index:5">
            <router-link to="/graph" class="tag-accent" style="cursor:pointer">全屏展开 →</router-link>
          </div>
          <div id="thumbnail-graph" style="position:absolute;inset:0;z-index:1"></div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;overflow-y:auto;flex:1">
          <div class="section-header">
            <span class="section-title">领域聚类</span>
            <span class="section-subtitle">{{ data.stats.total_domains }} 个领域</span>
          </div>
          <router-link
            v-for="d in data.domains"
            :key="d.id"
            :to="'/domain/' + d.id"
            class="domain-item"
            :class="{ bridge: d.is_bridge }"
          >
            <div>
              <div class="name">
                {{ d.name }}
                <span v-if="d.is_bridge" class="tag-bridge">桥梁</span>
              </div>
              <div class="desc">{{ d.description }}</div>
            </div>
            <div class="count">{{ d.article_count }}</div>
          </router-link>
        </div>
      </div>

      <!-- Recent Articles -->
      <div class="content-area">
        <div class="card">
          <div class="section-header">
            <span class="section-title">最新文章</span>
            <span class="section-subtitle">最近更新</span>
          </div>
          <div v-for="a in data.recent_articles" :key="a.id" class="recent-row">
            <div class="date">{{ a.date.slice(5) }}</div>
            <router-link :to="'/article/' + a.id" class="title">{{ a.title }}</router-link>
            <router-link :to="'/domain/' + a.domain_id" class="tag-accent">{{ a.domain_name }}</router-link>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="loading">加载中...</div>
  `,
  mounted() {
    const render = (data) => {
      requestAnimationFrame(() => renderThumbnail(data.network));
    };
    if (store.data.value) {
      this.$nextTick(() => render(store.data.value));
    }
    watch(
      () => store.data.value,
      (val) => {
        if (val) nextTick(() => render(val));
      }
    );
  },
};

// ---- Domain Detail ----
const DomainView = {
  setup() {
    const route = VueRouter.useRoute();
    const domain = computed(() => {
      if (!store.data.value) return null;
      return store.data.value.domains.find(
        (d) => d.id === Number(route.params.id)
      );
    });
    const sortBy = ref("date");
    const sortedArticles = computed(() => {
      if (!domain.value) return [];
      const arts = [...domain.value.articles];
      if (sortBy.value === "date") {
        return arts.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
      }
      return arts.sort((a, b) => (a.source || "").localeCompare(b.source || ""));
    });
    return { domain, sortBy, sortedArticles };
  },
  template: `
    <div v-if="domain" style="padding:0 24px">
      <!-- Header -->
      <div style="padding-top:24px;border-bottom:1px solid var(--border);padding-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <div v-if="domain.is_bridge" style="margin-bottom:8px">
              <span class="tag-bridge">桥梁领域</span>
              <span style="color:var(--text-muted);font-size:11px;margin-left:8px">betweenness: {{ domain.betweenness.toFixed(4) }}</span>
            </div>
            <div style="font-size:22px;font-weight:700;margin-bottom:6px">{{ domain.name }}</div>
            <div style="color:var(--text-muted);font-size:13px;max-width:600px;line-height:1.5">{{ domain.description }}</div>
          </div>
          <div style="text-align:right">
            <div style="color:var(--accent);font-size:32px;font-weight:700">{{ domain.article_count }}</div>
            <div style="color:var(--text-muted);font-size:12px">篇文章</div>
          </div>
        </div>
        <div class="keywords-row">
          <span v-for="kw in domain.keywords" :key="kw" class="tag">{{ kw }}</span>
        </div>
      </div>

      <!-- Two-column layout -->
      <div class="two-col">
        <!-- Articles -->
        <div class="main">
          <div class="section-header">
            <span class="section-title">全部文章</span>
            <div class="sort-tabs">
              <span class="sort-tab" :class="{ active: sortBy === 'date' }" @click="sortBy = 'date'">按日期</span>
              <span class="sort-tab" :class="{ active: sortBy === 'source' }" @click="sortBy = 'source'">按来源</span>
            </div>
          </div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <router-link
              v-for="a in sortedArticles"
              :key="a.id"
              :to="'/article/' + a.id"
              class="article-card"
              style="text-decoration:none"
            >
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div style="flex:1">
                  <div class="title">{{ a.title }}</div>
                  <div v-if="a.summary" class="summary">{{ a.summary }}</div>
                </div>
                <a v-if="a.url" :href="a.url" target="_blank" class="external-link" @click.stop>↗</a>
              </div>
              <div class="meta">
                <span>{{ a.source }}</span>
                <span>{{ a.date }}</span>
              </div>
            </router-link>
          </div>
        </div>

        <!-- Related Domains -->
        <div class="sidebar">
          <div class="section-title" style="margin-bottom:12px">关联领域</div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <router-link
              v-for="r in domain.related_domains"
              :key="r.id"
              :to="'/domain/' + r.id"
              class="related-card"
              style="text-decoration:none"
            >
              <div class="name">{{ r.name }}</div>
              <div class="info">
                <span>{{ r.name }} 篇文章</span>
                <span class="similarity">{{ (r.similarity * 100).toFixed(0) }}%</span>
              </div>
              <div class="similarity-bar">
                <div class="fill" :style="{ width: (r.similarity * 100) + '%' }"></div>
              </div>
            </router-link>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="loading">加载中...</div>
  `,
};

// ---- Article Detail ----
const ArticleView = {
  setup() {
    const route = VueRouter.useRoute();
    const article = computed(() => {
      if (!store.data.value) return null;
      const id = Number(route.params.id);
      for (const d of store.data.value.domains) {
        const found = d.articles.find((a) => a.id === id);
        if (found) return { ...found, domain_id: d.id, domain_name: d.name };
      }
      return null;
    });
    const relatedArticles = computed(() => {
      if (!article.value || !store.data.value) return [];
      const dom = store.data.value.domains.find(
        (d) => d.id === article.value.domain_id
      );
      if (!dom) return [];
      return dom.articles
        .filter((a) => a.id !== article.value.id)
        .slice(0, 3);
    });
    return { article, relatedArticles };
  },
  template: `
    <div v-if="article" class="page-content">
      <div class="breadcrumb">
        <router-link to="/">首页</router-link>
        <span>›</span>
        <router-link :to="'/domain/' + article.domain_id">{{ article.domain_name }}</router-link>
        <span>›</span>
        <span>文章详情</span>
      </div>

      <div class="article-detail-title">{{ article.title }}</div>

      <div class="article-meta">
        <span><span class="label">来源</span> {{ article.source }}</span>
        <span><span class="label">日期</span> {{ article.date }}</span>
        <span><span class="label">领域</span> <router-link :to="'/domain/' + article.domain_id">{{ article.domain_name }}</router-link></span>
      </div>

      <div v-if="article.keywords.length" class="keywords-row" style="margin-bottom:16px">
        <span v-for="kw in article.keywords" :key="kw" class="tag">{{ kw }}</span>
      </div>

      <div class="divider"></div>

      <div v-if="article.summary" style="margin-bottom:24px">
        <div style="color:var(--text-muted);font-size:11px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">摘要</div>
        <div class="summary-block">{{ article.summary }}</div>
      </div>

      <div style="margin-bottom:32px">
        <a v-if="article.url" :href="article.url" target="_blank" class="btn-primary">阅读原文 ↗</a>
      </div>

      <div v-if="relatedArticles.length" class="divider" style="padding-top:20px">
        <div class="section-title" style="margin-bottom:12px">同领域文章</div>
        <div style="display:flex;flex-direction:column;gap:8px">
          <router-link
            v-for="a in relatedArticles"
            :key="a.id"
            :to="'/article/' + a.id"
            class="domain-item"
            style="text-decoration:none"
          >
            <div>
              <div class="name">{{ a.title }}</div>
              <div class="desc">{{ a.source }} · {{ a.date }}</div>
            </div>
            <span style="color:var(--text-muted)">→</span>
          </router-link>
        </div>
      </div>
    </div>
    <div v-else class="loading">加载中...</div>
  `,
};

// ---- Full-screen Graph ----
const GraphView = {
  setup() {
    const searchQuery = ref('');
    const activeLayout = ref('concentric');
    const edgeThreshold = ref(0);
    const graphApi = ref(null);

    function onSearchInput() {
      if (graphApi.value) graphApi.value.search(searchQuery.value);
    }
    function onLayoutClick(name) {
      activeLayout.value = name;
      if (graphApi.value) graphApi.value.switchLayout(name);
    }
    function onThresholdChange() {
      if (graphApi.value) graphApi.value.setEdgeThreshold(edgeThreshold.value);
    }
    function onResetLayout() {
      if (graphApi.value) graphApi.value.resetLayout();
    }

    return {
      store, searchQuery, activeLayout, edgeThreshold, graphApi,
      onSearchInput, onLayoutClick, onThresholdChange, onResetLayout
    };
  },
  template: `
    <div class="graph-page">
      <!-- Top-left: close + title -->
      <div class="graph-tl">
        <router-link to="/" class="graph-overlay">✕ 关闭</router-link>
        <span class="graph-overlay title">知识图谱</span>
      </div>

      <!-- Top-center: search -->
      <div class="graph-search">
        <span class="graph-search-icon">⌘</span>
        <input
          v-model="searchQuery"
          @input="onSearchInput"
          class="graph-search-input"
          placeholder="搜索领域..."
        />
      </div>

      <!-- Top-right: layout switcher -->
      <div class="graph-layouts">
        <button class="graph-layout-btn" :class="{ active: activeLayout === 'concentric' }" @click="onLayoutClick('concentric')">⊙ 同心圆</button>
        <button class="graph-layout-btn" :class="{ active: activeLayout === 'cose-bilkent' }" @click="onLayoutClick('cose-bilkent')">∘ 力导向</button>
        <button class="graph-layout-btn" :class="{ active: activeLayout === 'circle' }" @click="onLayoutClick('circle')">○ 环形</button>
      </div>

      <!-- Right: legend + slider -->
      <div class="graph-right">
        <div class="graph-legend">
          <div class="legend-title">图例</div>
          <div class="legend-item">
            <div class="dot" style="width:12px;height:12px;border-radius:50%;background:linear-gradient(135deg,#5e6ad2,#8b5cf6);box-shadow:0 0 6px rgba(94,106,210,0.4)"></div>
            <span>桥梁领域</span>
          </div>
          <div class="legend-item">
            <div class="dot" style="width:10px;height:10px;border-radius:50%;background:linear-gradient(135deg,#3a3f5c,#5e6ad2)"></div>
            <span>普通领域</span>
          </div>
          <div class="legend-item">
            <svg width="20" height="4"><line x1="0" y1="2" x2="20" y2="2" stroke="#5e6ad2" stroke-width="2" opacity="0.6"/></svg>
            <span>关联强度</span>
          </div>
        </div>
        <div class="graph-slider-panel">
          <div class="graph-slider-label">边权重阈值</div>
          <input type="range" min="0" max="80" v-model.number="edgeThreshold" @input="onThresholdChange" class="graph-slider" />
          <div class="graph-slider-range"><span>全部</span><span>强关联</span></div>
        </div>
      </div>

      <div id="fullscreen-graph" style="width:100%;height:100%"></div>

      <!-- Bottom bar -->
      <div class="graph-bottom-bar">
        <span>{{ store.data.value ? store.data.value.stats.total_domains : '' }} 个领域</span>
        <span>{{ store.data.value ? store.data.value.stats.total_articles : '' }} 篇文章</span>
        <span class="graph-bottom-sep">|</span>
        <span>拖拽节点 · 滚轮缩放 · 点击进入</span>
        <span class="graph-reset-btn" @click="onResetLayout">↺ 重置布局</span>
      </div>
    </div>
  `,
  mounted() {
    const doRender = () => {
      if (!store.data.value) return;
      var el = document.getElementById("fullscreen-graph");
      if (el && el.clientWidth > 0 && el.clientHeight > 0) {
        this.graphApi = renderFullscreen(store.data.value.network);
      } else {
        requestAnimationFrame(doRender);
      }
    };
    this.$nextTick(() => requestAnimationFrame(doRender));
    watch(
      () => store.data.value,
      (val) => {
        if (val) nextTick(() => requestAnimationFrame(doRender));
      }
    );
  },
};

// ==========================================
// Router
// ==========================================
const routes = [
  { path: "/", component: HomeView },
  { path: "/domain/:id", component: DomainView },
  { path: "/article/:id", component: ArticleView },
  { path: "/graph", component: GraphView },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

window.vueRouter = router;

// ==========================================
// App
// ==========================================
const app = createApp({
  setup() {
    onMounted(() => store.load());
  },
  template: `
    <nav-bar></nav-bar>
    <router-view v-slot="{ Component }">
      <transition name="fade" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
  `,
});

app.component("nav-bar", NavBar);
app.use(router);
app.mount("#app");
