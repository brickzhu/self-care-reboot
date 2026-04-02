# self-care-reboot（重启人生·养自己计划）

一个“无压力、高自由、纯治愈”的轻量级养成式 Agent 技能。

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
    ├── square_publish.py
    ├── lobster_protocol.py
    └── pixel_renderer.py
```

**广场**：独立仓库 **[github.com/brickzhu/square](https://github.com/brickzhu/square)**；发帖前配置 `SQUARE_BASE_URL` 指向广场服务。更新广场代码或 `git push` 前，可先关掉本地 `python app.py`，避免占用端口与文件锁。

## 部署

把整个 `self-care-reboot/` 文件夹拷贝到你的“龙虾/OpenClaw”技能目录下（具体路径以你的平台为准），确保运行时能找到：
- `SKILL.md`
- `scripts/*.py`

推荐安装依赖（像素图需要 Pillow）：

```bash
pip install pillow
```

## 脚本（CLI）用法（便于你调试）

这些脚本默认走 JSON 输入/输出，方便你在平台对接时把结果写入 `memory_space`：

1. 初始化画像
```bash
python scripts/profile_manager.py init --ideal "自信大方,自律高效" --pain "拖延摆烂" --stage "current"
```

2. 生成今日任务
```bash
python scripts/daily_tasks.py today --seed 123
```

3. 生成事件选择
```bash
python scripts/story_generator.py event
```

4. 生成成长报告
```bash
python scripts/growth_report.py report --attributes '{"confidence":60,"discipline":55,"emotion":72,"talent":48,"appearance":50,"social":40}' --days 15
```

如果你把“龙虾”的脚本入参/出参格式发我，我也可以把上述 CLI 调整成完全匹配你平台的调用方式。

## Lobster（工具模式）协议对齐

当 `LOBSTER_MODE=tool` 时，脚本会输出 Lobster `protocolVersion: 1` 的 JSON 信封格式：
- `ok/status/output/requiresApproval` 或 `ok=false/error.message`

并支持 `--args-json` 作为统一入参（可以放在子命令前或后）：

```text
python scripts/profile_manager.py init --args-json "{\"ideal\":\"自信大方\",\"pain\":\"拖延\",\"stage\":\"current\",\"seed\":1}"
python scripts/daily_tasks.py today --args-json "{\"seed\":2,\"count\":4}"
python scripts/story_generator.py event --args-json "{\"seed\":3}"
python scripts/story_generator.py feedback --args-json "{\"event_id\":\"scene_030\",\"choice\":\"A\"}"
python scripts/growth_report.py report --args-json "{\"attributes\":{\"confidence\":60,\"discipline\":55,\"emotion\":72,\"talent\":48,\"appearance\":50,\"social\":40},\"days\":15,\"with_image\":true,\"stage\":\"child\"}"
```

当 `with_image=true` 且正确安装 Pillow 时，`growth_report` 的结果中会多一个：

- `avatar_image_path`: 指向生成的像素风“养成自己”头像卡片 PNG 文件（默认保存在 `artifacts/self-care-reboot/` 下）

