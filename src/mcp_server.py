"""In-process lab dispatcher; not a network MCP transport."""
import json
from tools import TOOLS_SCHEMA, dispatch_tool_call
class MCPDiscordServer:
    def __init__(self):
        self.server_name = "discord-demo-tool-server"
        self.version = "1.0.0"
        self.request_id = 0
    def list_tools(self):
        return TOOLS_SCHEMA
    def call_tool(self, tool_name, arguments):
        self.request_id += 1
        return {"jsonrpc": "2.0", "id": self.request_id, "server": self.server_name,
                "tool": tool_name, "result": json.loads(dispatch_tool_call(tool_name, arguments))}
MCPAcademicServer = MCPDiscordServer
if __name__ == "__main__":
    server = MCPDiscordServer()
    result = server.call_tool("read_day", {"day": "2026-09-13"})["result"]
    print(server.server_name, "| tools:", len(server.list_tools()),
          "| status:", result["status"], "| messages:", len(result.get("messages", [])))
