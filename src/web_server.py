"""Local UI server. Run: python src/web_server.py"""
import argparse
import hashlib
import json
import os
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dotenv import load_dotenv
from app import ROOT, DEFAULT_QUERY, run_react_agent, save_results
from discord_providers import get_demo_provider
from prompts import REACT_AGENT_SYSTEM_PROMPT
from tools import DATA_PATH, load_snapshot

load_dotenv(ROOT / ".env", override=True)

CACHE = ROOT / "outputs/private/ui_summary_cache.json"
LOCK = threading.Lock()

def cache_key():
    data_bytes = DATA_PATH.read_bytes().replace(b"\r\n", b"\n")
    prompt_bytes = REACT_AGENT_SYSTEM_PROMPT.replace("\r\n", "\n").encode("utf-8")
    digest = hashlib.sha256(data_bytes + prompt_bytes).hexdigest()
    return digest + ":" + os.getenv("LLM_MODEL", "gemini-flash-lite-latest")

def _load_events_from_trace_folder(folder_name):
    if not folder_name:
        return []
    trace_path = ROOT / "outputs/private" / folder_name / "trace.json"
    if trace_path.exists():
        try:
            raw = json.loads(trace_path.read_text(encoding="utf-8"))
            runs = raw.get("runs", [])
            if runs and "events" in runs[0]:
                return _sanitize_events(runs[0]["events"])
        except Exception:
            pass
    return []

def cached_summary():
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            if data.get("cache_key") == cache_key():
                # Backfill events if missing
                if not data.get("events") and data.get("trace_folder"):
                    data["events"] = _load_events_from_trace_folder(data["trace_folder"])
                if "total_latency_ms" not in data and data.get("events"):
                    data["total_latency_ms"] = round(sum(e.get("latency_ms") or 0 for e in data["events"]), 2)
                return {**data, "cached": True}
        except Exception:
            pass
    return None

def _sanitize_events(events):
    """Extract safe, UI-friendly trace entries from raw events."""
    out = []
    for e in events:
        entry = {"step": e.get("step"), "type": e.get("action_type", "UNKNOWN"),
                 "latency_ms": e.get("latency_ms")}
        act = e.get("action_type")
        if act == "TOOL_EXECUTION":
            entry["tool"] = e.get("tool_name")
            entry["args"] = e.get("arguments", {})
            obs = e.get("observation", {})
            entry["status"] = obs.get("status", "?")
            entry["msg_count"] = len(obs.get("messages", []))
        elif act == "LLM_RESPONSE":
            entry["tool_count"] = e.get("tool_count", 0)
            entry["usage"] = e.get("usage", {})
        elif act == "FINAL_ANSWER":
            entry["source_ids"] = e.get("source_ids", [])
        elif act in ("ERROR", "VALIDATION_ERROR", "BUDGET_EXCEEDED"):
            entry["message"] = e.get("output", "")
        out.append(entry)
    return out

def summarize(query=DEFAULT_QUERY, force=False):
    with LOCK:
        is_default = (query == DEFAULT_QUERY)
        if is_default and not force:
            cached = cached_summary()
            if cached:
                return cached
        if is_default and CACHE.exists():
            try:
                CACHE.unlink()
            except Exception:
                pass

        provider = get_demo_provider("gemini")
        events_raw = []
        try:
            result = run_react_agent(query, provider)
            events_raw = result.get("events", [])
            folder = save_results([{"id": "UI_QUERY" if not is_default else "UI_SUMMARY", "query": query, **result}], provider)
            trace_folder = folder.name
        except Exception as error:
            events_raw.append({"step": 1, "action_type": "ERROR", "output": str(error), "latency_ms": 0})
            sanitized = _sanitize_events(events_raw)
            return {
                "success": False,
                "error": f"Lỗi thực thi: {str(error)}",
                "status": "ERROR",
                "events": sanitized,
                "tool_calls": 0,
                "cached": False
            }
        finally:
            if hasattr(provider, "client") and hasattr(provider.client, "close"):
                try:
                    provider.client.close()
                except Exception:
                    pass

        sanitized_events = _sanitize_events(events_raw)
        tool_count = sum(e.get("action_type") == "TOOL_EXECUTION" for e in events_raw)
        total_latency_ms = round(sum(e.get("latency_ms") or 0 for e in sanitized_events), 2)

        if result.get("status") != "SUCCESS":
            return {
                "success": False,
                "error": result.get("answer", "Quá trình thực thi không thành công."),
                "status": result.get("status"),
                "events": sanitized_events,
                "tool_calls": tool_count,
                "total_latency_ms": total_latency_ms,
                "cached": False
            }

        usage = {"input_tokens": 0, "output_tokens": 0}
        for event in events_raw:
            for key in usage:
                usage[key] += (event.get("usage") or {}).get(key) or 0

        data = {
            "success": True,
            "query": query,
            "summary": result["answer"],
            "provider": provider.name,
            "model": provider.model_name,
            "cached": False,
            "cache_key": cache_key() if is_default else None,
            "usage": usage,
            "generated_at": datetime.now().isoformat(),
            "tool_calls": tool_count,
            "total_latency_ms": total_latency_ms,
            "trace_folder": trace_folder,
            "events": sanitized_events
        }
        if is_default:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return data

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def local_request(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        return self.headers.get("Host") in allowed

    def send(self, status, data, kind="application/json; charset=utf-8"):
        body = json.dumps(data, ensure_ascii=False).encode() if kind.startswith("application/json") else data
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.local_request():
            return self.send(403, {"error": "Local access only."})
        if self.path in ("/", "/index.html"):
            return self.send(200, (ROOT / "web/index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/app.js":
            return self.send(200, (ROOT / "web/app.js").read_bytes(), "text/javascript; charset=utf-8")
        if self.path == "/api/data":
            data = load_snapshot()
            key = os.getenv("GEMINI_API_KEY", "")
            return self.send(200, {"snapshot": data, "model": os.getenv("LLM_MODEL"),
                                   "configured": bool(key and not key.startswith("your_"))})
        if self.path == "/api/summary":
            return self.send(200, {"result": cached_summary()})
        return self.send(404, {"error": "Not found."})

    def do_POST(self):
        origin = self.headers.get("Origin")
        allowed_origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if not self.local_request() or origin not in allowed_origins:
            return self.send(403, {"error": "Origin not allowed."})
        if self.path not in ("/api/summarize", "/api/chat"):
            return self.send(404, {"error": "Not found."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send(415, {"error": "Expected JSON."})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 2048:
                return self.send(400, {"error": "Invalid request size."})
            body = json.loads(self.rfile.read(size)) if size > 0 else {}
            force = body.get("force", False) is True
            query = body.get("query", "").strip() or DEFAULT_QUERY
            
            res = summarize(query=query, force=force)
            return self.send(200, res)
        except Exception as error:
            self.send(500, {
                "error": f"Lỗi server: {str(error)}",
                "events": [{"type": "ERROR", "message": str(error)}]
            })

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(ROOT / ".env", override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Channel Digest: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
