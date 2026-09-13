"""Gemini native tool calling and explicit offline mock; no silent fallback."""
import os
import re
import time
class MockOfflineProvider:
    name = "mock"
    model_name = "deterministic-excerpt-demo"
    def start(self, query):
        return {"query": query, "observations": []}
    def observe(self, state, calls, results):
        state["observations"].extend(results)
    def respond(self, state, schemas, prompt, allow_tools=True):
        if not state["observations"]:
            match = re.search(r"demo_msg_\d{3}", state["query"])
            day = re.search(r"\d{4}-\d{2}-\d{2}", state["query"])
            call = ({"name": "get_message", "arguments": {"message_id": match[0]}} if match else
                    {"name": "read_day", "arguments": {"day": day[0] if day else "2026-09-13"}})
            return {"calls": [call], "text": "", "usage": {}}
        obs = state["observations"][-1]
        if obs["status"] != "SUCCESS":
            answer = obs.get("message", "Không đủ dữ liệu.")
        elif "message" in obs:
            m = obs["message"]
            answer = f'{m["content"]} [{m["id"]}]'
        else:
            query = state["query"].lower()
            if "zoom" in query:
                wanted = {"demo_msg_011", "demo_msg_012"}
            elif "updated" in query:
                wanted = {"demo_msg_007", "demo_msg_010"}
            elif "học phí" in query:
                wanted = set()
            else:
                wanted = {"demo_msg_003", "demo_msg_010", "demo_msg_012", "demo_msg_016"}
            selected = [m for m in obs["messages"] if m["id"] in wanted]
            answer = "\n".join(f'- {m["content"]} [{m["id"]}]' for m in selected)
            if not selected:
                answer = "Chưa đủ thông tin trong dữ liệu để trả lời."
        return {"calls": [], "text": "[MOCK — trích đoạn theo quy tắc, không phải AI]\n" + answer, "usage": {}}

class GeminiDemoProvider:
    name = "gemini"
    def __init__(self):
        from google import genai
        from google.genai import types
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key or key.startswith("your_"):
            raise ValueError("Điền GEMINI_API_KEY trong .env hoặc chạy --provider mock.")
        self.types = types
        self.model_name = os.getenv("LLM_MODEL") or "gemini-flash-lite-latest"
        self.client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=90000))
    def start(self, query):
        return [self.types.Content(role="user", parts=[self.types.Part(text=query)])]
    def observe(self, state, calls, results):
        parts = []
        for call, result in zip(calls, results):
            fields = {"name": call["name"], "response": result}
            if call.get("id"):
                fields["id"] = call["id"]
            parts.append(self.types.Part(function_response=self.types.FunctionResponse(**fields)))
        state.append(self.types.Content(role="user", parts=parts))
    def respond(self, state, schemas, prompt, allow_tools=True):
        types = self.types
        options = dict(system_instruction=prompt, temperature=0.1, max_output_tokens=700,
                       automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        if self.model_name.startswith("gemini-2.5-flash"):
            options["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        if allow_tools:
            options["tools"] = [types.Tool(function_declarations=schemas)]
        for attempt in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name, contents=state, config=types.GenerateContentConfig(**options))
                break
            except Exception as error:
                code = getattr(error, "code", None)
                if code == 429 and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                hint = {400: "Yêu cầu hoặc cấu hình model không hợp lệ.",
                        403: "API key không có quyền gọi model.",
                        404: "Model không khả dụng.",
                        429: "Đã hết hạn mức hoặc bị giới hạn tốc độ; kiểm tra quota Gemini."}.get(code, "Kiểm tra kết nối và cấu hình API.")
                raise RuntimeError(f"Gemini API lỗi {code or type(error).__name__}: {hint} Không chuyển sang mock.") from None
        if not response.candidates or not response.candidates[0].content:
            raise RuntimeError("Gemini không trả nội dung.")
        candidate = response.candidates[0]
        if str(candidate.finish_reason).endswith("MAX_TOKENS"):
            raise RuntimeError("Output đạt giới hạn token, câu trả lời chưa hoàn chỉnh.")
        content = candidate.content
        state.append(content)
        calls, texts = [], []
        for part in content.parts or []:
            if part.function_call:
                fc = part.function_call
                calls.append({"name": fc.name, "arguments": dict(fc.args or {}), "id": fc.id})
            elif part.text and not part.thought:
                texts.append(part.text)
        usage = response.usage_metadata
        return {"calls": calls, "text": "\n".join(texts),
                "usage": {"input_tokens": getattr(usage, "prompt_token_count", None),
                          "output_tokens": getattr(usage, "candidates_token_count", None)}}

def get_demo_provider(name):
    if name == "mock":
        return MockOfflineProvider()
    if name == "gemini":
        return GeminiDemoProvider()
    raise ValueError("Demo hỗ trợ --provider mock hoặc gemini.")
