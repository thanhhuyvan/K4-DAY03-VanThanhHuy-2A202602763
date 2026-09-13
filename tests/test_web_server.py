"""Local HTTP contract checks; mocked summary avoids spending API tokens."""
import json
import sys
import threading
import unittest
from pathlib import Path
from http.client import HTTPConnection
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from web_server import Handler, ThreadingHTTPServer

class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
    def request(self, method, path, body=None, headers=None):
        c = HTTPConnection("127.0.0.1", self.server.server_port)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        result = r.status, r.read()
        c.close()
        return result
    def test_page_and_data(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'/app.js', body)
        status, body = self.request("GET", "/api/data")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(len(data["snapshot"]["messages"]), 16)
        self.assertNotIn("GEMINI_API_KEY", body.decode())
    def test_no_file_access(self):
        self.assertEqual(self.request("GET", "/.env")[0], 404)
        self.assertEqual(self.request("GET", "/../.env")[0], 404)
    def test_untrusted_origin(self):
        self.assertEqual(self.request("POST", "/api/summarize", "{}", {"Origin": "https://example.com", "Content-Type": "application/json"})[0], 403)
    def test_summary_contract(self):
        headers = {"Origin": f"http://127.0.0.1:{self.server.server_port}", "Content-Type": "application/json"}
        with patch("web_server.summarize", return_value={"summary": "ok", "cached": True}) as fn:
            status, body = self.request("POST", "/api/summarize", "{}", headers)
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["cached"])
            fn.assert_called_once()
            self.assertEqual(self.request("POST", "/api/summarize", '{"messages":[]}', headers)[0], 400)
