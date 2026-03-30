from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any


PROTOCOL_VERSION = 1


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def is_lobster_tool_mode() -> bool:
    return (os.environ.get("LOBSTER_MODE") or "").strip().lower() == "tool"


def loads_args_json(s: str | None) -> dict[str, Any]:
    if not s:
        return {}
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        # 兼容某些 Windows/PowerShell 传参把引号“吃掉”的情况。
        # 先尝试把“未加引号的 key”补上引号（支持嵌套对象），再重新 json.loads。
        text = s.strip()
        try:
            # {ideal:xx, attributes:{confidence:60}} -> {"ideal":xx, "attributes":{"confidence":60}}
            text2 = re.sub(r'([\\{,])\\s*([A-Za-z_][A-Za-z0-9_]*)\\s*:', r'\\1"\\2":', text)
            # 把一些裸字符串值（非数字/true/false/null/对象/数组）补引号：
            # "k":abc -> "k":"abc"
            # 只匹配到下一个 `, } ]` 之前，避免跨层级吞字符
            text2 = re.sub(
                r':\\s*([A-Za-z_\\u4e00-\\u9fff][A-Za-z0-9_\\u4e00-\\u9fff\\- ]*)\\s*(?=,|\\}|\\])',
                lambda m: ":" + json.dumps(m.group(1).strip(), ensure_ascii=False),
                text2,
            )
            data = json.loads(text2)
        except Exception:
            # 再退一步：仅支持顶层 k:v 的简单解析
            if text.startswith("{") and text.endswith("}"):
                inner = text[1:-1].strip()
                if not inner:
                    return {}
                out: dict[str, Any] = {}
                parts = [p.strip() for p in inner.split(",") if p.strip()]
                for part in parts:
                    if ":" not in part:
                        continue
                    k, v = part.split(":", 1)
                    k = k.strip().strip("\"'")
                    v = v.strip()
                    if v.lower() in {"true", "false", "null"}:
                        out[k] = {"true": True, "false": False, "null": None}[v.lower()]
                        continue
                    try:
                        if "." in v:
                            out[k] = float(v)
                        else:
                            out[k] = int(v)
                        continue
                    except ValueError:
                        pass
                    out[k] = v.strip("\"'")
                return out
            raise
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("--args-json must be a JSON object")
    return data


def envelope_ok(
    *,
    status: str = "ok",
    output: list[dict[str, Any]] | None = None,
    requires_approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "ok": True,
        "status": status,
        "output": output or [],
        "requiresApproval": requires_approval,
    }


def envelope_error(message: str) -> dict[str, Any]:
    return {
        "protocolVersion": PROTOCOL_VERSION,
        "ok": False,
        "error": {"message": message},
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False))


def extract_args_json_anywhere(argv: list[str]) -> tuple[list[str], str | None]:
    """
    允许 `--args-json` 出现在子命令前或后：
    - script.py --args-json '{}' init ...
    - script.py init --args-json '{}' ...
    返回： (clean_argv, args_json_string)
    """
    if not argv:
        return argv, None
    clean: list[str] = []
    args_json: str | None = None
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--args-json":
            if i + 1 >= len(argv):
                raise ValueError("--args-json requires a value")
            args_json = argv[i + 1]
            i += 2
            continue
        clean.append(tok)
        i += 1
    return clean, args_json


