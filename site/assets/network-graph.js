// site/assets/network-graph.js
// Cytoscape.js knowledge graph — enhanced visual & interaction

(function () {
  // ---------------------------------------------------------------------------
  // Constants
  // ---------------------------------------------------------------------------

  var DIM_MIN = 28;
  var DIM_MAX = 64;
  var W_MIN = 10;
  var W_MAX = 14;

  // ---------------------------------------------------------------------------
  // SVG gradient backgrounds (precomputed data URIs)
  // ---------------------------------------------------------------------------

  function makeSvg(light, dark) {
    var svg =
      '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">' +
      '<defs><radialGradient id="g" cx="35%" cy="35%">' +
      '<stop offset="0%" stop-color="' + light + '"/>' +
      '<stop offset="100%" stop-color="' + dark + '"/>' +
      '</radialGradient></defs>' +
      '<circle cx="32" cy="32" r="31" fill="url(#g)"/>' +
      '</svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  var SVG_BG = {
    bridge: makeSvg('#8b93e8', '#5e6ad2'),
    large:  makeSvg('#6a70a0', '#3d4a7a'),
    medium: makeSvg('#4a5090', '#2e3348'),
    small:  makeSvg('#3d4250', '#252830')
  };

  // ---------------------------------------------------------------------------
  // Data helpers
  // ---------------------------------------------------------------------------

  function buildElements(networkData, topN) {
    if (topN === undefined) topN = 4;

    var sizes = networkData.nodes.map(function (n) { return n.size; });
    var minS = Math.min.apply(null, sizes);
    var maxS = Math.max.apply(null, sizes);

    var nodes = networkData.nodes.map(function (n) {
      var t = maxS === minS ? 0.5
        : (Math.log(n.size + 1) - Math.log(minS + 1))
        / (Math.log(maxS + 1) - Math.log(minS + 1));
      var dim = Math.round(DIM_MIN + t * (DIM_MAX - DIM_MIN));
      var tier = n.is_bridge ? 'bridge'
        : (n.size >= 20 ? 'large' : (n.size >= 10 ? 'medium' : 'small'));
      var fontSize = dim >= 50 ? 16 : (dim >= 36 ? 13 : 10);
      var nameSize = n.is_bridge ? 12 : (n.size >= 15 ? 11 : 10);
      var nameColor = n.is_bridge ? '#e8e8ed'
        : (n.size >= 15 ? '#9b9da5' : '#6b6e76');
      var borderW = n.is_bridge ? 2.5 : 1;
      var borderC = n.is_bridge ? 'rgba(139,147,232,0.6)'
        : (n.size >= 15 ? 'rgba(94,106,210,0.3)' : '#3d4050');

      return {
        data: {
          id: String(n.id), name: n.name, size: n.size,
          is_bridge: !!n.is_bridge, dim: dim, tier: tier,
          fontSize: fontSize, nameSize: nameSize, nameColor: nameColor,
          borderW: borderW, borderC: borderC,
          svgBg: SVG_BG[tier]
        }
      };
    });

    var bySource = {};
    networkData.edges.forEach(function (e) {
      var key = String(e.source);
      if (!bySource[key]) bySource[key] = [];
      bySource[key].push(e);
    });

    var kept = {};
    Object.keys(bySource).forEach(function (key) {
      var sorted = bySource[key].sort(function (a, b) { return b.weight - a.weight; });
      sorted.slice(0, topN).forEach(function (e) {
        var a = String(e.source), b = String(e.target);
        var pair = a < b ? a + '-' + b : b + '-' + a;
        kept[pair] = e;
      });
    });

    var edges = Object.keys(kept).map(function (pair, i) {
      var e = kept[pair];
      return {
        data: {
          id: 'e' + i, source: String(e.source),
          target: String(e.target), weight: e.weight
        }
      };
    });

    return nodes.concat(edges);
  }

  // ---------------------------------------------------------------------------
  // Cytoscape style
  // ---------------------------------------------------------------------------

  var graphStyle = [
    {
      selector: 'node',
      style: {
        'background-image': 'data(svgBg)',
        'background-fit': 'cover',
        'background-opacity': 1,
        'border-width': 'data(borderW)',
        'border-color': 'data(borderC)',
        width: 'data(dim)',
        height: 'data(dim)',
        label: 'data(size)',
        'text-valign': 'center',
        'text-halign': 'center',
        color: '#ffffff',
        'font-size': 'data(fontSize)px',
        'font-weight': 700,
        'text-outline-color': 'transparent',
        'text-outline-width': 0,
        'overlay-padding': 6,
        'transition-property': 'border-width, border-color, opacity',
        'transition-duration': '0.3s'
      }
    },
    {
      selector: 'node[is_bridge]',
      style: {
        'border-width': 2.5,
        'border-color': 'rgba(139,147,232,0.6)'
      }
    },
    {
      selector: 'edge',
      style: {
        width: 'mapData(weight,' + W_MIN + ',' + W_MAX + ',0.8,3.5)',
        'line-color': 'mapData(weight,' + W_MIN + ',' + W_MAX + ',#353860,#5e6ad2)',
        opacity: 'mapData(weight,' + W_MIN + ',' + W_MAX + ',0.25,0.75)',
        'curve-style': 'bezier',
        'transition-property': 'opacity, line-color, width',
        'transition-duration': '0.3s'
      }
    },
    // --- Hover ---
    {
      selector: 'node.highlighted',
      style: {
        'border-width': 3,
        'border-color': '#9ca3f0'
      }
    },
    {
      selector: 'node.dimmed',
      style: { opacity: 0.08 }
    },
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#7c85e0',
        opacity: 0.9,
        width: 'mapData(weight,' + W_MIN + ',' + W_MAX + ',2,4)'
      }
    },
    {
      selector: 'edge.dimmed',
      style: { opacity: 0.04 }
    }
  ];

  // ---------------------------------------------------------------------------
  // Layout configs
  // ---------------------------------------------------------------------------

  function getLayoutOpts(name) {
    var presets = {
      concentric: {
        name: 'concentric',
        concentric: function (n) { return n.data('is_bridge') ? 200 : n.data('size'); },
        levelWidth: function () { return 5; },
        minNodeSpacing: 40,
        padding: 50,
        startAngle: Math.PI / 6,
        sweep: Math.PI * 2,
        animate: true,
        animationDuration: 800,
        fit: true
      },
      'cose-bilkent': {
        name: 'cose-bilkent',
        animate: true,
        animationDuration: 800,
        fit: true,
        nodeRepulsion: 100000,
        idealEdgeLength: 120,
        gravity: 0.3,
        padding: 50
      },
      circle: {
        name: 'circle',
        padding: 50,
        animate: true,
        animationDuration: 800,
        fit: true,
        spacingFactor: 1.3
      }
    };
    return presets[name] || presets.concentric;
  }

  // ---------------------------------------------------------------------------
  // Core
  // ---------------------------------------------------------------------------

  function createGraph(container, networkData, options) {
    if (!options) options = {};
    var interactive = options.interactive !== false;
    var onClickNode = options.onClickNode || null;
    var topN = options.topN || 4;

    var elements = buildElements(networkData, topN);

    var cy = cytoscape({
      container: container,
      elements: elements,
      style: graphStyle,
      layout: getLayoutOpts('concentric'),
      userPanningEnabled: interactive,
      userZoomingEnabled: interactive,
      boxSelectionEnabled: false,
      autoungrabify: !interactive,
      autounselectify: true,
      minZoom: 0.3,
      maxZoom: 4,
      wheelSensitivity: 0.3
    });

    // --- Node name labels via HTML overlay ---
    cy.nodeHtmlLabel([
      {
        query: 'node',
        valign: 'top',
        halign: 'center',
        valignBox: 'center',
        halignBox: 'center',
        cssClass: 'gn-label',
        tpl: function (d) {
          return '<div class="gn-label-inner" style="position:relative;width:0;height:0">' +
            '<div class="gn-name" data-nid="' + d.id + '" style="' +
            'position:absolute;' +
            'top:' + (d.dim / 2 + 4) + 'px;' +
            'left:50%;' +
            'transform:translateX(-50%);' +
            'white-space:nowrap;' +
            'font-size:' + d.nameSize + 'px;' +
            'color:' + d.nameColor + '">' +
            d.name + '</div></div>';
        }
      }
    ]);

    cy.ready(function () {
      cy.fit(undefined, interactive ? 50 : 16);
    });

    var currentLayout = 'concentric';

    // --- Interactive ---
    if (interactive) {
      var tooltip = document.createElement('div');
      tooltip.className = 'graph-tooltip';
      tooltip.style.display = 'none';
      container.appendChild(tooltip);

      // Label DOM helpers
      function dimAllLabels() {
        container.querySelectorAll('.gn-label').forEach(function (el) {
          el.style.opacity = '0.08';
        });
      }
      function showLabel(nodeId) {
        var inner = container.querySelector('[data-nid="' + nodeId + '"]');
        if (inner) {
          var label = inner.closest('.gn-label') || inner.parentElement;
          label.style.opacity = '1';
        }
      }
      function resetAllLabels() {
        container.querySelectorAll('.gn-label').forEach(function (el) {
          el.style.opacity = '1';
        });
      }

      cy.on('mouseover', 'node', function (e) {
        var node = e.target;
        var hood = node.neighborhood();

        cy.elements().addClass('dimmed');
        node.removeClass('dimmed').addClass('highlighted');
        hood.nodes().removeClass('dimmed').addClass('highlighted');
        hood.edges().removeClass('dimmed').addClass('highlighted');

        dimAllLabels();
        showLabel(node.id());
        hood.nodes().forEach(function (n) { showLabel(n.id()); });

        var pos = node.renderedPosition();
        var d = node.data();
        var related = hood.nodes().slice(0, 4).map(function (n) {
          return n.data('name');
        }).join('、');

        tooltip.style.display = 'block';
        tooltip.innerHTML =
          '<div class="name">' + d.name + '</div>' +
          '<div class="info">' + d.size + ' 篇文章' + (d.is_bridge ? ' · 桥梁领域' : '') + '</div>' +
          '<div class="link">关联: ' + (related || '无') + '</div>';
        var tx = Math.min(pos.x + 14, container.clientWidth - 220);
        var ty = Math.max(pos.y - 70, 10);
        tooltip.style.left = tx + 'px';
        tooltip.style.top = ty + 'px';
      });

      cy.on('mouseout', 'node', function () {
        cy.elements().removeClass('dimmed highlighted');
        tooltip.style.display = 'none';
        resetAllLabels();
      });

      if (onClickNode) {
        cy.on('tap', 'node', function (e) {
          onClickNode({ id: e.target.id() });
        });
      }

      // Drag and fix
      cy.on('grab', 'node', function (e) { e.target.unlock(); });
      cy.on('dragfree', 'node', function (e) { e.target.lock(); });
    }

    // ---------------------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------------------

    return {
      cy: cy,

      search: function (query) {
        if (!query || !query.trim()) {
          cy.elements().removeClass('dimmed highlighted');
          container.querySelectorAll('.gn-label').forEach(function (el) {
            el.style.opacity = '1';
          });
          return;
        }
        var q = query.toLowerCase();
        var hits = cy.nodes().filter(function (n) {
          return n.data('name').toLowerCase().indexOf(q) !== -1;
        });

        cy.elements().removeClass('dimmed highlighted');
        if (hits.length > 0) {
          cy.nodes().not(hits).addClass('dimmed');
          cy.edges().connectedTo(cy.nodes().not(hits)).addClass('dimmed');

          container.querySelectorAll('.gn-label').forEach(function (el) {
            el.style.opacity = '0.08';
          });
          hits.forEach(function (n) {
            var inner = container.querySelector('[data-nid="' + n.id() + '"]');
            if (inner) {
              var label = inner.closest('.gn-label') || inner.parentElement;
              label.style.opacity = '1';
            }
          });

          cy.animate({
            fit: { eles: hits, padding: 120 },
            duration: 500
          });
        }
      },

      setEdgeThreshold: function (pct) {
        var cutoff = W_MIN + (W_MAX - W_MIN) * (pct / 100);
        cy.edges().forEach(function (edge) {
          if (edge.data('weight') < cutoff) {
            edge.hide();
          } else {
            edge.show();
          }
        });
      },

      switchLayout: function (name) {
        currentLayout = name;
        cy.nodes().unlock();
        cy.layout(getLayoutOpts(name)).run();
      },

      resetLayout: function () {
        cy.nodes().unlock();
        cy.layout(getLayoutOpts(currentLayout)).run();
      },

      destroy: function () { cy.destroy(); }
    };
  }

  // ---------------------------------------------------------------------------
  // Public render functions
  // ---------------------------------------------------------------------------

  window.renderThumbnail = function (networkData) {
    var container = document.getElementById('thumbnail-graph');
    if (!container) return null;
    container.innerHTML = '';
    return createGraph(container, networkData, {
      interactive: true,
      topN: 3,
      onClickNode: function (d) {
        if (window.vueRouter) window.vueRouter.push('/domain/' + d.id);
      }
    });
  };

  window.renderFullscreen = function (networkData) {
    var container = document.getElementById('fullscreen-graph');
    if (!container) return null;
    container.innerHTML = '';
    return createGraph(container, networkData, {
      interactive: true,
      topN: 5,
      onClickNode: function (d) {
        if (window.vueRouter) window.vueRouter.push('/domain/' + d.id);
      }
    });
  };
})();
