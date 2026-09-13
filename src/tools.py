"""Read-only tools for the Discord screenshot demo."""
import json
from datetime import date
from pathlib import Path
DATA_PATH = Path(__file__).resolve().parents[1] / "data/private/discord_demo_2026-09-13/messages.json"
TOOLS_SCHEMA = [
    {"name": "read_day", "description": "Đọc tin ngày YYYY-MM-DD từ ảnh chụp kênh demo. Có ngày 2026-09-13.",
     "parameters": {"type": "object", "properties": {"day": {"type": "string"}}, "required": ["day"]}},
    {"name": "get_message", "description": "Đọc tin theo ID demo_msg_NNN và nguồn ảnh để đối chiếu.",
     "parameters": {"type": "object", "properties": {"message_id": {"type": "string"}}, "required": ["message_id"]}},
]
def load_snapshot():
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))
def read_day(day):
    date.fromisoformat(day)
    data = load_snapshot()
    if day != data["date"]:
        return {"status": "NO_DATA", "message": "Không có bản dữ liệu ngày này; không có nghĩa Discord không có tin."}
    return {"status": "SUCCESS", "day": day, "source": data["source_type"],
            "complete": data["complete"], "coverage_start": data["coverage_start"],
            "coverage_end": data["coverage_end"],
            "messages": [{k: m.get(k) for k in ("id", "author", "timestamp", "content", "reply_to")}
                         for m in data["messages"]]}
def get_message(message_id):
    for m in load_snapshot()["messages"]:
        if m["id"] == message_id:
            return {"status": "SUCCESS", "message": m}
    return {"status": "NOT_FOUND", "message": "Không tìm thấy ID trong dữ liệu demo."}
TOOL_ROUTER = {"read_day": read_day, "get_message": get_message}
def dispatch_tool_call(tool_name, arguments):
    if tool_name not in TOOL_ROUTER:
        result = {"status": "UNKNOWN_TOOL"}
    else:
        schema = next(t["parameters"] for t in TOOLS_SCHEMA if t["name"] == tool_name)
        if (not isinstance(arguments, dict) or set(arguments) != set(schema["required"])
                or not all(isinstance(v, str) for v in arguments.values())):
            result = {"status": "INVALID_ARGUMENTS"}
        else:
            try:
                result = TOOL_ROUTER[tool_name](**arguments)
            except (ValueError, TypeError):
                result = {"status": "INVALID_ARGUMENTS"}
            except OSError:
                result = {"status": "DATA_UNAVAILABLE"}
    return json.dumps(result, ensure_ascii=False)
