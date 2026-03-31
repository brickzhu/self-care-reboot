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
  const container = document.getElementById("world");
  container.innerHTML = "";

  const state = {
    posts: [],
    setPosts(items) {
      this.posts = items || [];
      sceneRef?.refreshBooths?.(this.posts);
    },
  };

  let sceneRef = null;

  function makeTexture(scene, key, w, h, painter) {
    const g = scene.make.graphics({ x: 0, y: 0, add: false });
    painter(g);
    g.generateTexture(key, w, h);
    g.destroy();
  }

  class PlazaScene extends Phaser.Scene {
    constructor() {
      super("plaza");
      this.booths = [];
      this.cat = null;
      this.tipText = null;
    }

    preload() {}

    create() {
      sceneRef = this;
      this.cameras.main.setBackgroundColor("#0b0c12");
      this.cameras.main.setZoom(2);
      this.cameras.main.roundPixels = true;

      // textures (procedural pixel)
      makeTexture(this, "tileA", 16, 16, (g) => {
        g.fillStyle(0x1a1b2a, 1).fillRect(0, 0, 16, 16);
        g.fillStyle(0x141528, 1).fillRect(0, 0, 16, 2);
        g.fillStyle(0x141528, 1).fillRect(0, 14, 16, 2);
      });
      makeTexture(this, "tileB", 16, 16, (g) => {
        g.fillStyle(0x141528, 1).fillRect(0, 0, 16, 16);
        g.fillStyle(0x1a1b2a, 1).fillRect(0, 0, 16, 2);
        g.fillStyle(0x1a1b2a, 1).fillRect(0, 14, 16, 2);
      });
      makeTexture(this, "fountain", 32, 32, (g) => {
        g.fillStyle(0x8ad4ff, 0.22).fillRect(0, 0, 32, 32);
        g.fillStyle(0x8ad4ff, 0.45).fillRect(8, 8, 16, 16);
        g.fillStyle(0xffffff, 0.2).fillRect(10, 10, 4, 4);
      });
      makeTexture(this, "tree", 24, 32, (g) => {
        g.fillStyle(0x2e5c48, 1).fillRect(2, 0, 20, 18);
        g.fillStyle(0x1a3328, 1).fillRect(6, 14, 12, 10);
        g.fillStyle(0x5a4634, 1).fillRect(10, 22, 4, 10);
      });
      makeTexture(this, "bench", 32, 20, (g) => {
        g.fillStyle(0x786046, 1).fillRect(2, 6, 28, 6);
        g.fillStyle(0x463c36, 1).fillRect(6, 12, 4, 8);
        g.fillStyle(0x463c36, 1).fillRect(22, 12, 4, 8);
      });
      makeTexture(this, "booth", 28, 20, (g) => {
        g.fillStyle(0xb36ad9, 0.35).fillRect(0, 2, 28, 18);
        g.lineStyle(2, 0x8ad4ff, 0.7).strokeRect(1, 3, 26, 16);
        g.fillStyle(0xf5f5f5, 0.9).fillRect(12, 0, 4, 6);
        g.fillStyle(0x8ad4ff, 0.85).fillRect(16, 0, 10, 4);
      });
      makeTexture(this, "cat", 24, 18, (g) => {
        // body
        g.fillStyle(0xf0c86a, 1).fillRect(6, 8, 12, 8);
        // head
        g.fillRect(2, 4, 8, 8);
        // ears
        g.fillStyle(0xd6a84f, 1).fillRect(2, 2, 2, 2);
        g.fillRect(8, 2, 2, 2);
        // eyes
        g.fillStyle(0x222222, 1).fillRect(4, 7, 1, 1);
        g.fillRect(7, 7, 1, 1);
        // tail
        g.fillStyle(0xd6a84f, 1).fillRect(18, 10, 4, 2);
      });

      // tilemap (procedural grid)
      const worldW = 60 * 16;
      const worldH = 40 * 16;
      for (let y = -worldH / 2; y < worldH / 2; y += 16) {
        for (let x = -worldW / 2; x < worldW / 2; x += 16) {
          const k = ((x + y) / 16) % 2 === 0 ? "tileA" : "tileB";
          this.add.image(x, y, k).setOrigin(0, 0).setDepth(0);
        }
      }

      // center fountain
      this.add.image(0, 0, "fountain").setOrigin(0.5).setDepth(2);

      // decorations
      const deco = [
        { x: -90, y: -70, key: "tree" },
        { x: 90, y: -70, key: "tree" },
        { x: -90, y: 70, key: "tree" },
        { x: 90, y: 70, key: "tree" },
        { x: -40, y: 110, key: "bench" },
        { x: 40, y: 110, key: "bench" },
      ];
      for (const d of deco) this.add.image(d.x, d.y, d.key).setOrigin(0.5).setDepth(3);

      // cat wandering
      this.cat = this.add.image(-120, 90, "cat").setOrigin(0.5).setDepth(10);
      this.tweens.add({
        targets: this.cat,
        x: 120,
        y: 90,
        duration: 4500,
        yoyo: true,
        repeat: -1,
        ease: "Sine.inOut",
      });

      // camera controls
      this.input.on("wheel", (pointer, go, dx, dy) => {
        const cam = this.cameras.main;
        cam.setZoom(clamp(cam.zoom + (dy > 0 ? -0.15 : 0.15), 1.2, 3.6));
      });

      this.input.on("pointermove", (p) => {
        if (!p.isDown) return;
        const cam = this.cameras.main;
        cam.scrollX -= (p.position.x - p.prevPosition.x) / cam.zoom;
        cam.scrollY -= (p.position.y - p.prevPosition.y) / cam.zoom;
      });

      // hint
      this.tipText = this.add
        .text(12, 480, "地图空空的：点「生成示例内容」或在下方发布一条作品", {
          fontFamily: "ui-sans-serif",
          fontSize: "12px",
          color: "#f5f5f5",
          backgroundColor: "rgba(0,0,0,0.55)",
          padding: { x: 10, y: 6 },
        })
        .setScrollFactor(0)
        .setDepth(1000);

      this.refreshBooths(state.posts);
    }

    refreshBooths(posts) {
      for (const b of this.booths) b.destroy();
      this.booths = [];

      const items = posts || [];
      const n = items.length;
      this.tipText.setVisible(n === 0);
      if (!n) return;

      const r = 140;
      for (let i = 0; i < n; i++) {
        const p = items[i];
        const ang = (i / n) * Math.PI * 2;
        const x = Math.cos(ang) * r + (i % 3) * 10;
        const y = Math.sin(ang) * r + (i % 2) * 8;
        const booth = this.add.image(x, y, "booth").setOrigin(0.5).setDepth(6).setInteractive({ useHandCursor: true });
        booth.on("pointerdown", () => openDrawer(p));
        booth.on("pointerover", () => booth.setTint(0xffe27a));
        booth.on("pointerout", () => booth.clearTint());
        this.booths.push(booth);
      }
    }
  }

  const config = {
    type: Phaser.AUTO,
    parent: "world",
    width: container.clientWidth || 980,
    height: container.clientHeight || 520,
    pixelArt: true,
    backgroundColor: "#0b0c12",
    scene: [PlazaScene],
    scale: {
      mode: Phaser.Scale.RESIZE,
      autoCenter: Phaser.Scale.CENTER_BOTH,
    },
  };

  // eslint-disable-next-line no-undef
  new Phaser.Game(config);
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

