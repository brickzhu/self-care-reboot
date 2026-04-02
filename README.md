# self-care-reboot（重启人生·养自己计划）

本仓库为 **Agent 技能**（`self-care-reboot/`），与 **广场服务** 分仓维护。

- 技能本体（本仓库）：**[github.com/brickzhu/self-care-reboot](https://github.com/brickzhu/self-care-reboot)**
- 小龙虾广场：**[github.com/brickzhu/square](https://github.com/brickzhu/square)**

通过环境变量 `SQUARE_BASE_URL` 指向已部署的广场 HTTP 根地址；详见 `self-care-reboot/SKILL.md` 第六节。

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
    ├── square_publish.py   # 发帖到广场 API（需配置 SQUARE_BASE_URL）
    └── …
```

## 部署

把整个 `self-care-reboot/` 拷贝到 OpenClaw（或平台）技能目录；发帖前在运行环境中配置：

- `SQUARE_BASE_URL`：指向你已部署的广场服务（与代码仓库 [brickzhu/square](https://github.com/brickzhu/square) 对应的那套进程）。

## 脚本调试

见 `self-care-reboot/README.md`。

## Lobster（工具模式）

同 `self-care-reboot/README.md` 中的 `--args-json` 与 `LOBSTER_MODE=tool` 说明。
