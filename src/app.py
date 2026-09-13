"""Discord screenshot demo: bounded tool loop, source checks and trace."""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from discord_providers import get_demo_provider
from mcp_server import MCPDiscordServer
from prompts import MAX_ITERATIONS, MAX_TOOL_CALLS, REACT_AGENT_SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]
NOTICE = "Dữ liệu ảnh chụp 13/09/2026, 00:08–12:31 (giờ Việt Nam), chưa đủ cả ngày."
DEFAULT_QUERY = "Tổng hợp kênh ngày 2026-09-13: chủ đề chính, hướng dẫn đã xác nhận và câu hỏi còn mở."

def run_react_agent(query, provider, server=None):
    server = server or MCPDiscordServer()
    state = provider.start(query)
    events, known_ids = [], set()
    calls_used = 0
    for step in range(1, MAX_ITERATIONS + 1):
        started = time.perf_counter()
        try:
            response = provider.respond(state, server.list_tools(), REACT_AGENT_SYSTEM_PROMPT,
                                        allow_tools=step < MAX_ITERATIONS)
        except (RuntimeError, ValueError) as error:
            events.append({"step": step, "action_type": "ERROR", "output": str(error),
                           "latency_ms": round((time.perf_counter() - started) * 1000, 2)})
            return {"status": "ERROR", "answer": str(error), "events": events}
        events.append({"step": step, "action_type": "LLM_RESPONSE",
                       "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                       "usage": response.get("usage", {}), "tool_count": len(response["calls"])})
        if response["calls"]:
            if step == MAX_ITERATIONS or calls_used + len(response["calls"]) > MAX_TOOL_CALLS:
                events.append({"step": step, "action_type": "BUDGET_EXCEEDED"})
                return {"status": "BUDGET_EXCEEDED", "answer": "Đã đạt giới hạn gọi tool/LLM.", "events": events}
            results = []
            for call in response["calls"]:
                started = time.perf_counter()
                result = server.call_tool(call["name"], call["arguments"])["result"]
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                results.append(result)
                calls_used += 1
                messages = result.get("messages", [])
                if isinstance(result.get("message"), dict):
                    messages = [result["message"]]
                known_ids.update(m["id"] for m in messages)
                events.append({"step": step, "action_type": "TOOL_EXECUTION",
                               "tool_name": call["name"], "arguments": call["arguments"],
                               "observation": result, "latency_ms": elapsed})
                print(f'  Tool: {call["name"]} {call["arguments"]} -> {result["status"]}')
            provider.observe(state, response["calls"], results)
            continue
        text = response["text"].strip()
        cited = set(re.findall(r"demo_msg_\d+", text))
        if not text or cited - known_ids or calls_used == 0:
            answer = "Câu trả lời chưa hợp lệ: thiếu dữ liệu tool, nội dung rỗng hoặc ID nguồn không có trong dữ liệu đã đọc."
            events.append({"step": step, "action_type": "VALIDATION_ERROR", "output": answer})
            return {"status": "VALIDATION_ERROR", "answer": answer, "events": events}
        answer = NOTICE + "\n\n" + text
        events.append({"step": step, "action_type": "FINAL_ANSWER", "output": answer,
                       "source_ids": sorted(cited)})
        return {"status": "SUCCESS", "answer": answer, "events": events}
    return {"status": "BUDGET_EXCEEDED", "answer": "Chưa hoàn thành trong ngân sách.", "events": events}

def save_results(runs, provider):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = ROOT / "outputs/private" / f"{provider.name}_{stamp}"
    folder.mkdir(parents=True)
    payload = {"provider": provider.name, "model": provider.model_name,
               "is_mock": provider.name == "mock", "data_source": "manual_screenshot_transcription",
               "notice": NOTICE, "runs": runs}
    (folder / "trace.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = "\n\n---\n\n".join(f'### {r["id"]}: {r["query"]}\n\n{r["answer"]}' for r in runs)
    (folder / "summary.md").write_text(f"Provider: {provider.name}\n\n" + report, encoding="utf-8")
    # Lab artifact explicitly labels mock vs live; each full trace also has a unique saved path.
    (ROOT / "docs/trace_waterfall.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã lưu: {folder}")
    return folder

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "gemini"], default=os.getenv("LLM_PROVIDER", "mock"))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--all", action="store_true")
    modes.add_argument("--interactive", action="store_true")
    modes.add_argument("--query")
    args = parser.parse_args()
    try:
        provider = get_demo_provider(args.provider)
    except ValueError as error:
        parser.exit(1, str(error) + "\n")
    print(f"DISCORD DEMO | {provider.name} | {provider.model_name}\n{NOTICE}")
    print("Mock chỉ kiểm tra luồng; Gemini gửi văn bản đã chép cho API để tổng hợp.")
    if args.interactive:
        print("Mỗi câu hỏi là một phiên độc lập. Gõ exit để thoát.")
        while True:
            try:
                query = input("Bạn: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if query.lower() in ("exit", "quit"):
                break
            if not query:
                continue
            result = run_react_agent(query, provider)
            print(result["answer"])
            save_results([{"id": "CHAT", "query": query, **result}], provider)
        return 0
    tests = (json.loads((ROOT / "config/test_cases.json").read_text(encoding="utf-8")) if args.all
             else [{"id": "DEMO", "question": args.query or DEFAULT_QUERY}])
    runs = []
    for test in tests:
        if runs:
            time.sleep(4)
        print(f'\n[{test["id"]}] {test["question"]}')
        result = run_react_agent(test["question"], provider)
        print(result["answer"])
        runs.append({"id": test["id"], "query": test["question"], **result})
        if result["status"] == "ERROR":
            break
    save_results(runs, provider)
    completed = sum(r["status"] == "SUCCESS" for r in runs)
    print(f"Hoàn tất kỹ thuật: {completed}/{len(tests)}; chất lượng nội dung cần đối chiếu nguồn.")
    return 0 if completed == len(tests) else 1

if __name__ == "__main__":
    raise SystemExit(main())
