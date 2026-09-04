#!/usr/bin/env python3
"""从 CPA error-v1-chat-completions-*.log 提取失败请求 JSON，打印诊断摘要。

用法:
  python3 extract_cpa_request.py [-o /tmp/replay.json] [logfile]

不带 logfile 时自动取 ~/cliproxyapi/logs/ 下最新的 error-v1-chat-completions-*.log。
带 -o 时把请求体写入文件供 curl -d @file 原样重放，同时输出诊断摘要。

典型重放: curl -s -m 120 http://127.0.0.1:8317/v1/chat/completions \
  -H "Authorization: Bearer $(grep -oP 'sk-\\S+' ~/cliproxyapi/keys.txt | head -1)" \
  -H "Content-Type: application/json" -d @/tmp/replay.json
"""
import argparse
import glob
import json
import os
import sys


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logfile", nargs="?", help="CPA error log 路径（默认取最新一份）")
    ap.add_argument("-o", "--output", default=None, help="把请求体 JSON 写入该文件（供 curl 重放）")
    args = ap.parse_args()

    if args.logfile:
        f = args.logfile
    else:
        candidates = sorted(
            glob.glob(os.path.expanduser("~/cliproxyapi/logs/error-v1-chat-completions-*.log"))
        )
        if not candidates:
            sys.exit("未找到 CPA error log: ~/cliproxyapi/logs/error-v1-chat-completions-*.log")
        f = candidates[-1]

    txt = open(f, encoding="utf-8", errors="replace").read()
    if "=== REQUEST BODY ===" not in txt:
        sys.exit(f"该文件没有 REQUEST BODY 段（可能不是 chat/completions 错误日志）: {f}")

    body = txt.split("=== REQUEST BODY ===", 1)[1].split("=== API REQUEST", 1)[0].strip()
    start = body.find("{")
    if start < 0:
        sys.exit(f"REQUEST BODY 段无 JSON: {f}")
    req = json.loads(body[start:])

    print("# 来源:", os.path.basename(f))
    print("# model:", req.get("model"))
    print("# 顶层参数:", list(req.keys()))
    print("# 消息角色:", [m.get("role") for m in req.get("messages") or []])
    tools = req.get("tools") or []
    print("# tools:", [t.get("function", {}).get("name") for t in tools])
    tc = sum(
        1 for m in req.get("messages") or [] if m.get("role") == "assistant" and m.get("tool_calls")
    )
    tm = sum(1 for m in req.get("messages") or [] if m.get("role") == "tool")
    print(f"# assistant.tool_calls 消息数: {tc} | tool 消息数: {tm}（应配对）")

    if args.output:
        json.dump(req, open(args.output, "w", encoding="utf-8"), ensure_ascii=False)
        print("# 已写入:", args.output)
    else:
        print(json.dumps(req, ensure_ascii=False))


if __name__ == "__main__":
    main()
