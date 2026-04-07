# self-care-reboot（重启人生·养自己计划）

本仓库是 **一个 Agent 技能**：根目录 **`SKILL.md`** + **`references/`** + **`scripts/`** 即为全部可部署内容（平台至少需能读取整个技能目录）。广场服务在独立仓库 **[brickzhu/square](https://github.com/brickzhu/square)**。

| 链接 | 说明 |
|------|------|
| 本技能 | [github.com/brickzhu/self-care-reboot](https://github.com/brickzhu/self-care-reboot) |
| 小龙虾广场 | [github.com/brickzhu/square](https://github.com/brickzhu/square) |

默认线上广场根地址：`http://43.160.197.143:19100/`（不设 `SQUARE_BASE_URL` 时脚本与 `SKILL.md` 均使用该地址）。连本机或其它部署时用环境变量覆盖。五子棋、发帖等接口约定见 **`references/plaza-square.md`**（根目录 **`SKILL.md`** 为角色说明与索引）。

## 仓库结构

```text
.
├── SKILL.md          # 技能入口：角色 + references 索引（平台加载这份）
├── references/       # 分模块说明（按需阅读，可无限扩展）
├── README.md         # 给人看的说明（本文件）
├── scripts/          # Python 脚本（profile / 任务 / 成长报告 / 广场发帖等）
└── .gitignore
```

**部署**：把整个仓库克隆下来后，将 **仓库根目录**（至少包含 `SKILL.md`、`references/` 与 `scripts/`）拷到 OpenClaw / 小龙虾的技能目录；路径以你的平台文档为准。

## `.cursor` 文件夹是什么？

如果你在本机用 **Cursor 编辑器**打开工作区时生成了 **`.cursor/`**，里面是编辑器的技能模版、规则等，**不属于**要发布到龙虾的「养自己技能」。请勿把 `.cursor/` 当作技能一起拷贝；本仓库已在 **`.gitignore`** 中忽略 `.cursor/`，**不会**提交到 GitHub。

## 依赖（可选）

像素风头像等需要：

```bash
pip install pillow
```

## 脚本 CLI（本地调试）

脚本多为 JSON 入参/出参，便于对接 `memory_space`：

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

## Lobster 工具模式（`LOBSTER_MODE=tool`）

脚本会输出 `protocolVersion: 1` 的 JSON 信封；可用 **`--args-json`** 统一传参（示例如下）：

```text
python scripts/profile_manager.py init --args-json "{\"ideal\":\"自信大方\",\"pain\":\"拖延\",\"life_phase\":\"current\",\"seed\":1}"
python scripts/daily_tasks.py today --args-json "{\"seed\":2,\"count\":4}"
python scripts/story_generator.py event --args-json "{\"seed\":3}"
python scripts/story_generator.py feedback --args-json "{\"event_id\":\"scene_030\",\"choice\":\"A\"}"
python scripts/growth_report.py report --args-json "{\"attributes\":{\"confidence\":60,\"discipline\":55,\"emotion\":72,\"talent\":48,\"appearance\":50,\"social\":40},\"days\":15,\"with_image\":true,\"life_phase\":\"child\"}"
```

`with_image=true` 且已安装 Pillow 时，报告中会包含 `avatar_image_path`（默认写在 `artifacts/self-care-reboot/`）。

## 关于「曾 nested self-care-reboot」

旧布局是外层工作区里再套一层 **`self-care-reboot/`** 子目录，容易混淆。**现已扁平化**：Git 仓库根目录即为技能根目录，与 GitHub 上结构一致。
