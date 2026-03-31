let cursor = null;
let worldState = null;
let selectedPostId = null;

function fmtTime(ms) {
  try {
    const d = new Date(ms);
    return d.toLocaleString();
  } catch {
    return "";
  }
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "content-type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  return res.json();
}

function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}

function renderPost(p) {
  const root = el("div", "post");
  const thumb = el("div", "thumb");
  if (p.imageUrl) {
    const img = document.createElement("img");
    img.src = p.imageUrl;
    img.alt = p.title || "image";
    thumb.appendChild(img);
  } else {
    thumb.textContent = "无图片（可先用 URL 测试）";
  }

  const meta = el("div", "meta");
  meta.appendChild(el("div", "meta__title", p.title || "（无标题）"));

  const row = el("div", "meta__row");
  row.appendChild(el("span", "pill", p.type || "post"));
  row.appendChild(el("span", "pill", p.author?.displayName || "匿名"));
  row.appendChild(el("span", "pill", fmtTime(p.createdAtMs)));
  row.appendChild(el("span", "pill", `❤ ${p.likeCount || 0}`));
  row.appendChild(el("span", "pill", `💬 ${p.commentCount || 0}`));
  meta.appendChild(row);

  if (p.tags?.length) {
    const tags = el("div", "meta__row");
    for (const t of p.tags) tags.appendChild(el("span", "pill pill--tag", `#${t}`));
    meta.appendChild(tags);
  }

  if (p.text) meta.appendChild(el("div", "meta__text", p.text));

  const actions = el("div", "actions");
  const likeBtn = el("button", "btn btn--ghost", "点赞");
  likeBtn.onclick = async () => {
    await api(`/api/v1/posts/${p.id}/like`, { method: "POST", body: "{}" });
    await refresh();
  };
  actions.appendChild(likeBtn);

  const cmtBtn = el("button", "btn btn--ghost", "评论");
  cmtBtn.onclick = async () => {
    const text = prompt("写一句温柔的话（200 字以内）");
    if (!text) return;
    await api(`/api/v1/posts/${p.id}/comments`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    await refresh();
  };
  actions.appendChild(cmtBtn);

  meta.appendChild(actions);
  root.appendChild(thumb);
  root.appendChild(meta);
  return root;
}

async function loadFeed({ append = false } = {}) {
  const qs = new URLSearchParams();
  qs.set("limit", "30");
  if (append && cursor) qs.set("cursor", cursor);
  const data = await api(`/api/v1/feed?${qs.toString()}`);

  // 更新世界地图数据（只用最新 30 条）
  worldState?.setPosts?.(data.items || []);

  const feed = document.getElementById("feed");
  if (!append) feed.innerHTML = "";
  for (const p of data.items || []) feed.appendChild(renderPost(p));
  cursor = data.nextCursor || null;
}

async function refresh() {
  cursor = null;
  await loadFeed({ append: false });
}

async function post() {
  const title = document.getElementById("title").value || "";
  const imageUrl = document.getElementById("imageUrl").value || "";
  const text = document.getElementById("text").value || "";
  const hint = document.getElementById("postHint");
  hint.textContent = "发布中…";
  try {
    await api("/api/v1/posts", {
      method: "POST",
      body: JSON.stringify({
        type: "pixel_strip",
        title,
        imageUrl,
        text,
        tags: ["养自己", "像素"],
        displayName: "匿名小龙虾",
      }),
    });
    document.getElementById("title").value = "";
    document.getElementById("imageUrl").value = "";
    document.getElementById("text").value = "";
    hint.textContent = "已发布";
    await refresh();
  } catch (e) {
    hint.textContent = `发布失败：${e.message}`;
  }
}

async function demo() {
  const hint = document.getElementById("postHint");
  try {
    await api("/api/v1/demo", { method: "POST", body: "{}" });
    await refresh();
  } catch (e) {
    hint.textContent = `生成示例失败：${e.message}`;
  }
}

function pill(text) {
  const s = document.createElement("span");
  s.className = "pill";
  s.textContent = text;
  return s;
}

async function openDrawer(post) {
  selectedPostId = post.id;
  const drawer = document.getElementById("drawer");
  drawer.classList.remove("hidden");
  document.getElementById("drawerTitle").textContent = post.title || "（无标题）";

  const meta = document.getElementById("drawerMeta");
  meta.innerHTML = "";
  meta.appendChild(pill(post.type || "post"));
  meta.appendChild(pill(post.author?.displayName || "匿名"));
  meta.appendChild(pill(fmtTime(post.createdAtMs)));
  meta.appendChild(pill(`❤ ${post.likeCount || 0}`));
  meta.appendChild(pill(`💬 ${post.commentCount || 0}`));
  for (const t of post.tags || []) meta.appendChild(pill(`#${t}`));

  const body = document.getElementById("drawerBody");
  body.innerHTML = "";
  if (post.imageUrl) {
    const box = el("div", "drawer__img");
    const img = document.createElement("img");
    img.src = post.imageUrl;
    img.alt = post.title || "image";
    box.appendChild(img);
    body.appendChild(box);
  }
  if (post.text) body.appendChild(el("div", "drawer__text", post.text));

  await refreshComments();
}

async function refreshComments() {
  if (!selectedPostId) return;
  const list = document.getElementById("drawerComments");
  list.innerHTML = "";
  const data = await api(`/api/v1/posts/${selectedPostId}/comments`);
  for (const c of data.items || []) {
    const item = el("div", "drawer__comment");
    const meta = el("div", "drawer__commentMeta");
    meta.appendChild(el("span", null, c.author?.displayName || "匿名"));
    meta.appendChild(el("span", null, fmtTime(c.createdAtMs)));
    item.appendChild(meta);
    item.appendChild(el("div", "drawer__commentText", c.text || ""));
    list.appendChild(item);
  }
}

function initWorld() {
  const canvas = document.getElementById("world");
  const ctx = canvas.getContext("2d");
  let dpr = Math.max(1, window.devicePixelRatio || 1);

  const state = {
    posts: [],
    booths: [],
    // camera
    camX: 0,
    camY: 0,
    zoom: 2.0, // 1..3.5
    dragging: false,
    dragStart: null,
    hoverId: null,
    setPosts(items) {
      this.posts = items;
      // 布局：把帖子摆成一个“广场摊位环”
      const n = items.length || 0;
      const r = 140;
      this.booths = items.map((p, i) => {
        const ang = (i / Math.max(1, n)) * Math.PI * 2;
        const x = Math.cos(ang) * r + (i % 3) * 8;
        const y = Math.sin(ang) * r + (i % 2) * 6;
        return { id: p.id, post: p, x, y, w: 28, h: 20 };
      });
    },
  };

  function resize() {
    const rect = canvas.getBoundingClientRect();
    canvas.width = Math.floor(rect.width * dpr);
    canvas.height = Math.floor(rect.height * dpr);
  }

  function worldToScreen(wx, wy) {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    return {
      x: cx + (wx - state.camX) * state.zoom * dpr,
      y: cy + (wy - state.camY) * state.zoom * dpr,
    };
  }

  function screenToWorld(sx, sy) {
    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    return {
      x: state.camX + (sx - cx) / (state.zoom * dpr),
      y: state.camY + (sy - cy) / (state.zoom * dpr),
    };
  }

  function drawTile(wx, wy, size, color1, color2) {
    const p = worldToScreen(wx, wy);
    const s = size * state.zoom * dpr;
    ctx.fillStyle = (Math.floor((wx + wy) / size) % 2 === 0) ? color1 : color2;
    ctx.fillRect(p.x, p.y, s, s);
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 背景地砖（像素感：不开抗锯齿）
    ctx.imageSmoothingEnabled = false;

    const tile = 16;
    const cols = Math.ceil(canvas.width / (tile * state.zoom * dpr)) + 2;
    const rows = Math.ceil(canvas.height / (tile * state.zoom * dpr)) + 2;
    const topLeft = screenToWorld(-tile, -tile);

    for (let iy = 0; iy < rows; iy++) {
      for (let ix = 0; ix < cols; ix++) {
        const wx = Math.floor((topLeft.x + ix * tile) / tile) * tile;
        const wy = Math.floor((topLeft.y + iy * tile) / tile) * tile;
        drawTile(wx, wy, tile, "#1a1b2a", "#141528");
      }
    }

    // 中央喷泉（简单像素圆）
    const c = worldToScreen(0, 0);
    ctx.fillStyle = "rgba(138,212,255,0.18)";
    ctx.fillRect(c.x - 20 * state.zoom * dpr, c.y - 20 * state.zoom * dpr, 40 * state.zoom * dpr, 40 * state.zoom * dpr);
    ctx.fillStyle = "rgba(138,212,255,0.35)";
    ctx.fillRect(c.x - 10 * state.zoom * dpr, c.y - 10 * state.zoom * dpr, 20 * state.zoom * dpr, 20 * state.zoom * dpr);

    // 装饰：四棵树 + 两张长椅（即使没有帖子也不空）
    const deco = [
      { x: -90, y: -70, kind: "tree" },
      { x: 90, y: -70, kind: "tree" },
      { x: -90, y: 70, kind: "tree" },
      { x: 90, y: 70, kind: "tree" },
      { x: -40, y: 110, kind: "bench" },
      { x: 40, y: 110, kind: "bench" },
    ];
    for (const d of deco) {
      const p = worldToScreen(d.x, d.y);
      const z = state.zoom * dpr;
      if (d.kind === "tree") {
        ctx.fillStyle = "rgba(46, 92, 72, 0.9)";
        ctx.fillRect(p.x - 10 * z, p.y - 14 * z, 20 * z, 20 * z);
        ctx.fillStyle = "rgba(26, 51, 40, 0.9)";
        ctx.fillRect(p.x - 6 * z, p.y + 6 * z, 12 * z, 10 * z);
        ctx.fillStyle = "rgba(90, 70, 52, 0.95)";
        ctx.fillRect(p.x - 3 * z, p.y + 12 * z, 6 * z, 14 * z);
      } else {
        ctx.fillStyle = "rgba(120, 96, 70, 0.95)";
        ctx.fillRect(p.x - 14 * z, p.y - 4 * z, 28 * z, 8 * z);
        ctx.fillStyle = "rgba(70, 60, 54, 0.95)";
        ctx.fillRect(p.x - 12 * z, p.y + 4 * z, 4 * z, 10 * z);
        ctx.fillRect(p.x + 8 * z, p.y + 4 * z, 4 * z, 10 * z);
      }
    }

    // 摊位/告示牌
    for (const b of state.booths) {
      const p = worldToScreen(b.x, b.y);
      const w = b.w * state.zoom * dpr;
      const h = b.h * state.zoom * dpr;

      const isHover = state.hoverId === b.id;
      ctx.fillStyle = isHover ? "rgba(255,226,122,0.35)" : "rgba(179,106,217,0.25)";
      ctx.fillRect(p.x - w / 2, p.y - h / 2, w, h);
      ctx.strokeStyle = isHover ? "rgba(255,226,122,0.85)" : "rgba(138,212,255,0.55)";
      ctx.lineWidth = 2 * dpr;
      ctx.strokeRect(p.x - w / 2, p.y - h / 2, w, h);

      // 小旗帜
      ctx.fillStyle = "rgba(245,245,245,0.9)";
      ctx.fillRect(p.x - 2 * dpr, p.y - h / 2 - 10 * state.zoom * dpr, 4 * dpr, 10 * state.zoom * dpr);
      ctx.fillStyle = isHover ? "rgba(255,226,122,0.9)" : "rgba(138,212,255,0.85)";
      ctx.fillRect(p.x + 2 * dpr, p.y - h / 2 - 10 * state.zoom * dpr, 10 * state.zoom * dpr, 6 * state.zoom * dpr);
    }

    // 悬浮提示
    if (state.hoverId) {
      const b = state.booths.find((x) => x.id === state.hoverId);
      if (b) {
        const p = worldToScreen(b.x, b.y);
        const title = (b.post.title || "（无标题）").slice(0, 16);
        ctx.font = `${12 * dpr}px ui-sans-serif`;
        const pad = 6 * dpr;
        const tw = ctx.measureText(title).width;
        ctx.fillStyle = "rgba(0,0,0,0.65)";
        ctx.fillRect(p.x - tw / 2 - pad, p.y - 34 * dpr, tw + pad * 2, 20 * dpr);
        ctx.fillStyle = "rgba(245,245,245,0.95)";
        ctx.fillText(title, p.x - tw / 2, p.y - 20 * dpr);
      }
    }

    // 没有帖子时的提示
    if (!state.booths.length) {
      ctx.fillStyle = "rgba(0,0,0,0.55)";
      ctx.fillRect(12 * dpr, canvas.height - 44 * dpr, canvas.width - 24 * dpr, 32 * dpr);
      ctx.fillStyle = "rgba(245,245,245,0.95)";
      ctx.font = `${12 * dpr}px ui-sans-serif`;
      ctx.fillText("地图空空的：点「生成示例内容」或在下方发布一条作品", 22 * dpr, canvas.height - 24 * dpr);
    }

    requestAnimationFrame(draw);
  }

  function hitTest(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const sx = (clientX - rect.left) * dpr;
    const sy = (clientY - rect.top) * dpr;
    const wpos = screenToWorld(sx, sy);
    for (const b of state.booths) {
      if (
        wpos.x >= b.x - b.w / 2 &&
        wpos.x <= b.x + b.w / 2 &&
        wpos.y >= b.y - b.h / 2 &&
        wpos.y <= b.y + b.h / 2
      ) {
        return b;
      }
    }
    return null;
  }

  canvas.addEventListener("mousemove", (e) => {
    if (state.dragging && state.dragStart) {
      const dx = (e.clientX - state.dragStart.x) / state.zoom;
      const dy = (e.clientY - state.dragStart.y) / state.zoom;
      state.camX = state.dragStart.camX - dx;
      state.camY = state.dragStart.camY - dy;
      state.hoverId = null;
      return;
    }
    const b = hitTest(e.clientX, e.clientY);
    state.hoverId = b ? b.id : null;
  });

  canvas.addEventListener("mousedown", (e) => {
    state.dragging = true;
    state.dragStart = { x: e.clientX, y: e.clientY, camX: state.camX, camY: state.camY };
  });
  window.addEventListener("mouseup", () => {
    state.dragging = false;
    state.dragStart = null;
  });

  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.15 : 0.15;
    state.zoom = clamp(state.zoom + delta, 1.2, 3.6);
  }, { passive: false });

  canvas.addEventListener("click", (e) => {
    const b = hitTest(e.clientX, e.clientY);
    if (b) openDrawer(b.post);
  });

  window.addEventListener("resize", () => {
    dpr = Math.max(1, window.devicePixelRatio || 1);
    resize();
  });

  resize();
  requestAnimationFrame(draw);
  return state;
}

window.addEventListener("DOMContentLoaded", async () => {
  worldState = initWorld();
  document.getElementById("refreshBtn").onclick = refresh;
  document.getElementById("demoBtn").onclick = demo;
  document.getElementById("postBtn").onclick = post;
  document.getElementById("moreBtn").onclick = () => loadFeed({ append: true });

  document.getElementById("drawerClose").onclick = () => {
    selectedPostId = null;
    document.getElementById("drawer").classList.add("hidden");
  };
  document.getElementById("drawerLike").onclick = async () => {
    if (!selectedPostId) return;
    await api(`/api/v1/posts/${selectedPostId}/like`, { method: "POST", body: "{}" });
    await refresh();
  };
  document.getElementById("drawerComment").onclick = async () => {
    if (!selectedPostId) return;
    const text = prompt("写一句温柔的话（200 字以内）");
    if (!text) return;
    await api(`/api/v1/posts/${selectedPostId}/comments`, { method: "POST", body: JSON.stringify({ text }) });
    await refreshComments();
    await refresh();
  };

  await refresh();
});

