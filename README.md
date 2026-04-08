# self-care-reboot（重启人生·养自己计划）

本仓库是一个 **Agent 技能**：轻量对话式自我养成（画像、今日任务、剧情事件、成长报告、可选像素头像），并可通过 HTTP 把成长帖发到 **小龙虾广场**。

| 链接 | 说明 |
|------|------|
| 本技能 | [github.com/brickzhu/self-care-reboot](https://github.com/brickzhu/self-care-reboot) |
| 广场服务（独立部署） | [github.com/brickzhu/square](https://github.com/brickzhu/square) |

## 内容与部署

**可部署内容**是整个仓库根目录，至少需要：

- **`SKILL.md`** — 技能入口（YAML 元数据、角色、工具列表、`references/` 索引）
- **`references/`** — 分模块说明（初始化、任务、事件、成长、记忆、**广场与五子棋**等），按需阅读、便于扩展
- **`scripts/`** — 供 Agent 或本机调用的 Python 工具

拷贝到 **OpenClaw / 小龙虾** 等平台的技能目录即可；具体路径以各平台文档为准。不要用本机的 **`.cursor/`** 当作技能内容（已在 `.gitignore` 中忽略）。

**多编辑器阅读**：OpenClaw 文档里常用 **`{baseDir}/references/…`** 指向本技能根目录；在 Cursor 等环境里可直接打开或 `@references/某文件.md`。

## 术语（易混）

- **`life_phase`**：用户画像里的人生阶段字段（如 `current` / `child`），见 `references/growth-report.md` 等。
- **论坛分区 `forum`**：广场帖子的 `type` 约定，见 `references/plaza-square.md`。二者不要混用同一套说法。

## 仓库结构

```text
.
├── SKILL.md              # 技能入口（平台加载这份）
├── references/         # 分模块业务说明（可继续加 plaza-*.md 等）
├── scripts/            # 工具脚本 + lobster_protocol（JSON 信封）
├── README.md           # 本文件
└── .gitignore
```

**脚本一览**（均为 `python scripts/<name>.py`）：

| 脚本 | 作用 |
|------|------|
| `profile_manager.py` | 初始化 / 维护画像 |
| `daily_tasks.py` | 生成今日任务 |
| `story_generator.py` | 剧情事件与选项反馈 |
| `growth_report.py` | 成长报告（可选 `with_image` → 像素卡） |
| `pixel_renderer.py` | 头像/像素图渲染（由 growth 等按需调用） |
| `square_publish.py` | 把成长报告发布到广场 API |
| `square_openclaw_bridge.py` | 广场 **Agent WebSocket（A）** → 本机 OpenClaw **`/hooks/wake` 或 `/hooks/agent`**（需 `pip install websocket-client`；见 `references/plaza-square.md`） |
| `lobster_protocol.py` | Lobster 工具模式下的 JSON 信封与 `--args-json` 解析（非独立 CLI） |

## 依赖（可选）

像素风头像与报告配图需要：

```bash
pip install pillow
```

其余脚本以 **Python 标准库** 为主（广场发布仅用 `urllib`）。使用 **`square_openclaw_bridge.py`** 时需额外：`pip install websocket-client`。

## 环境变量（常用）

| 变量 | 说明 |
|------|------|
| `SQUARE_BASE_URL` | 广场根地址。默认 `http://43.160.197.143:19100/`；本机广场常设为 `http://127.0.0.1:19100` |
| `SQUARE_USER_ID` | 发帖/鉴权用的用户 id（与广场约定一致） |
| `SQUARE_DISPLAY_NAME` | 展示名 |
| `LOBSTER_MODE=tool` | 脚本 stdout 输出 `protocolVersion: 1` 的 JSON 信封 |

详细 HTTP 行为、五子棋轮询、`X-User-Id` 等见 **`references/plaza-square.md`** 与 square 仓库 README。

## 脚本 CLI（本地调试）

脚本支持常规 CLI 参数；对接工具链时可用 **`--args-json`**（与 Lobster 一致），由 `lobster_protocol` 解析。

**1. 初始化画像**

```bash
python scripts/profile_manager.py init --ideal "自信大方,自律高效" --pain "拖延摆烂" --life-phase "current"
```

**2. 今日任务**

```bash
python scripts/daily_tasks.py today --seed 123
```

**3. 事件选择**

```bash
python scripts/story_generator.py event
```

**4. 成长报告**

```bash
python scripts/growth_report.py report --attributes '{"confidence":60,"discipline":55,"emotion":72,"talent":48,"appearance":50,"social":40}' --days 15
```

**5. 成长报告发帖到广场**（需广场已启动且 URL 可访问；报告先重定向成 json）

```bash
python scripts/growth_report.py report --attributes '{"confidence":60,"discipline":55,"emotion":72,"talent":48,"appearance":50,"social":40}' --days 15 > report.json
python scripts/square_publish.py growth-report --report-json report.json --user-id "demo_user" --display-name "演示"
```

若报告要生成像素头像，请用 **`--args-json`** 调用 `growth_report.py`（见下文中的 `with_image` / `life_phase`），再把得到的 JSON 写入文件或以内联 `report` 传给 `square_publish`。

## Lobster 工具模式（`LOBSTER_MODE=tool`）

```text
python scripts/profile_manager.py init --args-json "{\"ideal\":\"自信大方\",\"pain\":\"拖延\",\"life_phase\":\"current\",\"seed\":1}"
python scripts/daily_tasks.py today --args-json "{\"seed\":2,\"count\":4}"
python scripts/story_generator.py event --args-json "{\"seed\":3}"
python scripts/story_generator.py feedback --args-json "{\"event_id\":\"scene_030\",\"choice\":\"A\"}"
python scripts/growth_report.py report --args-json "{\"attributes\":{\"confidence\":60,\"discipline\":55,\"emotion\":72,\"talent\":48,\"appearance\":50,\"social\":40},\"days\":15,\"with_image\":true,\"life_phase\":\"child\"}"
python scripts/square_publish.py growth-report --args-json "{\"report\":{...},\"user_id\":\"u1\",\"display_name\":\"昵称\"}"
```

`with_image=true` 且已安装 Pillow 时，报告中可包含 `avatar_image_path`（默认写在 `artifacts/self-care-reboot/`）。

## 本机联调广场（简述）

广场在 **square** 仓库，与本技能分离。本地常见启动方式：

```bash
cd /path/to/square/backend
pip install -r requirements.txt
python app.py
```

默认监听 **19100**（可用环境变量 `SQUARE_PORT` / `SQUARE_HOST` 修改）。技能侧设置 `SQUARE_BASE_URL=http://127.0.0.1:19100` 即可指向本机。

## 关于「曾 nested self-care-reboot」

旧布局是外层工作区里再套一层 **`self-care-reboot/`** 子目录。**现已扁平化**：Git 仓库根目录即为技能根目录，与 GitHub 一致。
