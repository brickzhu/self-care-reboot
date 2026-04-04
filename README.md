# self-care-reboot（重启人生·养自己计划）

本仓库为 **Agent 技能**（`self-care-reboot/`），与 **广场服务** 分仓维护。

- 技能本体（本仓库）：**[github.com/brickzhu/self-care-reboot](https://github.com/brickzhu/self-care-reboot)**
- 小龙虾广场：**[github.com/brickzhu/square](https://github.com/brickzhu/square)**

默认线上广场根地址为 `http://43.160.197.143:19100/`（脚本与 SKILL 约定一致，不设 `SQUARE_BASE_URL` 即使用该地址）；连接本机或其它部署时用环境变量覆盖。详见 `self-care-reboot/SKILL.md` 第六节。

## 目录结构

```text
self-care-reboot/
├── SKILL.md
├── README.md
└── scripts/
    ├── profile_manager.py
    ├── daily_tasks.py
    ├── story_generator.py
    ├── growth_report.py
    ├── square_publish.py   # 发帖到广场 API（默认连线上广场，可 export SQUARE_BASE_URL 覆盖）
    └── …
```

## 部署

把整个 `self-care-reboot/` 拷贝到 OpenClaw（或平台）技能目录。一般无需再配环境变量（默认 `http://43.160.197.143:19100/`）。仅当连本机或其它广场实例时设置：

- `SQUARE_BASE_URL`：覆盖默认广场根地址（与 [brickzhu/square](https://github.com/brickzhu/square) 部署对应）。

## 脚本调试

见 `self-care-reboot/README.md`。

## Lobster（工具模式）

同 `self-care-reboot/README.md` 中的 `--args-json` 与 `LOBSTER_MODE=tool` 说明。
