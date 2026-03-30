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
    └── growth_report.py
```

## 部署

把整个 `self-care-reboot/` 文件夹拷贝到你的“龙虾/OpenClaw”技能目录下（具体路径以你的平台为准），确保运行时能找到：
- `SKILL.md`
- `scripts/*.py`

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
python scripts/growth_report.py report --args-json "{\"attributes\":{\"confidence\":60,\"discipline\":55,\"emotion\":72,\"talent\":48,\"appearance\":50,\"social\":40},\"days\":15}"
```

