"""Offline behavioral tests; no external API calls."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from app import run_react_agent
from discord_providers import MockOfflineProvider, GeminiDemoProvider
from tools import read_day, get_message, dispatch_tool_call, TOOLS_SCHEMA

class DemoTests(unittest.TestCase):
    def run_agent(self, query, provider=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_react_agent(query, provider or MockOfflineProvider())

    def test_snapshot_and_sources(self):
        data = read_day("2026-09-13")
        self.assertEqual(len(data["messages"]), 16)
        self.assertFalse(data["complete"])
        self.assertIn("updated", get_message("demo_msg_010")["message"]["content"])

    def test_missing_day_and_arguments(self):
        self.assertEqual(read_day("2026-09-12")["status"], "NO_DATA")
        self.assertEqual(json.loads(dispatch_tool_call("read_day", {"day": "../secret"}))["status"], "INVALID_ARGUMENTS")
        self.assertEqual(json.loads(dispatch_tool_call("read_day", {"day": 123}))["status"], "INVALID_ARGUMENTS")
        self.assertEqual(json.loads(dispatch_tool_call("shell", {}))["status"], "UNKNOWN_TOOL")
        self.assertEqual(get_message("demo_msg_999")["status"], "NOT_FOUND")

    def test_five_cases(self):
        path = Path(__file__).resolve().parents[1] / "config/test_cases.json"
        for case in json.loads(path.read_text(encoding="utf-8")):
            with self.subTest(case=case["id"]):
                result = self.run_agent(case["question"])
                self.assertEqual(result["status"], "SUCCESS")
                self.assertEqual(sum(e["action_type"] == "LLM_RESPONSE" for e in result["events"]), 2)
                self.assertIn("chưa đủ cả ngày", result["answer"])
        self.assertIn("Chưa đủ thông tin", self.run_agent("học phí")["answer"])

    def test_id_lookup(self):
        result = self.run_agent("Đọc demo_msg_010")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("[demo_msg_010]", result["answer"])
        self.assertEqual(result["events"][1]["tool_name"], "get_message")

    def test_invented_source_rejected(self):
        provider = MockOfflineProvider()
        original = provider.respond
        def respond(state, *args, **kwargs):
            if state["observations"]:
                return {"calls": [], "text": "Bịa nguồn [demo_msg_999]", "usage": {}}
            return original(state, *args, **kwargs)
        provider.respond = respond
        self.assertEqual(self.run_agent("Tổng hợp", provider)["status"], "VALIDATION_ERROR")

    def test_loop_budget(self):
        provider = MockOfflineProvider()
        provider.respond = lambda *a, **k: {"calls": [{"name": "read_day", "arguments": {"day": "2026-09-13"}}], "text": ""}
        result = self.run_agent("Tổng hợp", provider)
        self.assertEqual(result["status"], "BUDGET_EXCEEDED")
        self.assertEqual(sum(e["action_type"] == "LLM_RESPONSE" for e in result["events"]), 3)

    def test_gemini_native_roundtrip_without_network(self):
        from google.genai import types
        provider = GeminiDemoProvider.__new__(GeminiDemoProvider)
        provider.types = types
        provider.model_name = "gemini-2.5-flash"
        provider.client = Mock()
        content = types.Content(role="model", parts=[types.Part(
            function_call=types.FunctionCall(name="read_day", args={"day": "2026-09-13"}, id="call1"),
            thought_signature=b"preserve-me")])
        provider.client.models.generate_content.return_value = types.GenerateContentResponse(
            candidates=[types.Candidate(content=content, finish_reason="STOP")])
        state = provider.start("Tổng hợp")
        response = provider.respond(state, TOOLS_SCHEMA, "demo")
        self.assertEqual(state[-1].parts[0].thought_signature, b"preserve-me")
        provider.observe(state, response["calls"], [read_day("2026-09-13")])
        self.assertEqual(state[-1].parts[0].function_response.id, "call1")
        self.assertEqual(state[-1].parts[0].function_response.response["status"], "SUCCESS")

    def test_live_error_does_not_fallback(self):
        from google.genai import types
        provider = GeminiDemoProvider.__new__(GeminiDemoProvider)
        provider.types = types
        provider.model_name = "gemini-2.5-flash"
        provider.client = Mock()
        provider.client.models.generate_content.side_effect = RuntimeError("SECRET must not be logged")
        result = self.run_agent("Tổng hợp", provider)
        self.assertEqual(result["status"], "ERROR")
        self.assertNotIn("SECRET", result["answer"])

if __name__ == "__main__":
    unittest.main()
