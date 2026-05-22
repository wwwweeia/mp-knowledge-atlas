// site/assets/network-graph.js
// D3.js force-directed graph — thumbnail + fullscreen

function createGraph(container, networkData, options = {}) {
  const {
    width = container.clientWidth,
    height = container.clientHeight,
    interactive = true,
    onClickNode = null,
  } = options;

  const nodes = networkData.nodes.map((n) => ({ ...n }));
  const edges = networkData.edges.map((e) => ({ ...e }));

  const svg = d3
    .select(container)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const tooltip = d3
    .select(container)
    .append("div")
    .attr("class", "graph-tooltip")
    .style("display", "none");

  const simulation = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(edges)
        .id((d) => d.id)
        .distance(120)
    )
    .force("charge", d3.forceManyBody().strength(-300))
    .force("center", d3.forceCenter(width / 2, height / 2));

  const link = svg
    .append("g")
    .selectAll("line")
    .data(edges)
    .enter()
    .append("line")
    .attr("stroke", "#2a2b2d")
    .attr("stroke-width", (d) => Math.max(1, Math.sqrt(d.weight)));

  const node = svg
    .append("g")
    .selectAll("g")
    .data(nodes)
    .enter()
    .append("g")
    .attr("cursor", interactive ? "pointer" : "default");

  node
    .append("circle")
    .attr("r", (d) => 6 + Math.sqrt(d.size) * 3)
    .attr("fill", (d) => (d.is_bridge ? "#5e6ad2" : "#3d4250"))
    .attr("stroke", (d) => (d.is_bridge ? "#7c85e0" : "none"))
    .attr("stroke-width", (d) => (d.is_bridge ? 2.5 : 0));

  node
    .append("text")
    .attr("dx", (d) => 6 + Math.sqrt(d.size) * 3 + 6)
    .attr("dy", "0.35em")
    .attr("fill", (d) => (d.is_bridge ? "#e8e8ed" : "#9b9da5"))
    .attr("font-size", (d) => (d.is_bridge ? "10px" : "8px"))
    .text((d) => d.name);

  if (interactive) {
    const drag = d3
      .drag()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    node.call(drag);

    node
      .on("mouseover", (event, d) => {
        tooltip
          .style("display", "block")
          .html(
            `<div class="name">${d.name}</div>` +
              `<div class="info">${d.size} 篇文章${d.is_bridge ? " · 桥梁领域" : ""}</div>` +
              `<div class="link">点击查看 →</div>`
          )
          .style("left", event.pageX + 12 + "px")
          .style("top", event.pageY - 30 + "px");
      })
      .on("mouseout", () => {
        tooltip.style("display", "none");
      });

    if (onClickNode) {
      node.on("click", (event, d) => onClickNode(d));
    }

    const zoom = d3
      .zoom()
      .scaleExtent([0.3, 4])
      .on("zoom", (event) => {
        svg.select("g").attr("transform", event.transform);
        link.attr("transform", event.transform);
        node.attr("transform", event.transform);
      });
    svg.call(zoom);
  }

  simulation.on("tick", () => {
    link
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);
    node.attr("transform", (d) => `translate(${d.x},${d.y})`);
  });

  return { svg, simulation, tooltip };
}

function renderThumbnail(networkData) {
  const container = document.getElementById("thumbnail-graph");
  if (!container) return;
  container.innerHTML = "";
  createGraph(container, networkData, {
    interactive: false,
    onClickNode: null,
  });
}

function renderFullscreen(networkData) {
  const container = document.getElementById("fullscreen-graph");
  if (!container) return;
  container.innerHTML = "";
  createGraph(container, networkData, {
    width: window.innerWidth,
    height: window.innerHeight,
    interactive: true,
    onClickNode: (d) => {
      if (window.vueRouter) {
        window.vueRouter.push("/domain/" + d.id);
      }
    },
  });
}