#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import threading
import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / "Py+Linux" / "Scripts" / "seo_index_toolkit.py"
spec = importlib.util.spec_from_file_location("seo_index_toolkit", CORE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        host = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/":
            body = f"""<!doctype html><html><head>
<title>Fixture page</title>
<meta name="description" content="Fixture description">
<meta name="robots" content="index, follow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="{host}/">
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebPage"}}</script>
</head><body><h1>Fixture</h1><p>{'crawlable text ' * 40}</p></body></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/robots.txt":
            body = f"User-agent: *\nAllow: /\nSitemap: {host}/sitemap.xml\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/sitemap.xml":
            body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{host}/</loc><lastmod>2026-07-29</lastmod></url>
</urlset>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/fixture-key.txt":
            body = b"abcdef1234567890"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


class ToolkitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_snapshot_and_scores(self):
        snapshot = module.build_snapshot(
            self.origin + "/",
            self.origin + "/sitemap.xml",
            self.origin + "/fixture-key.txt",
            5,
            "test-agent",
        )
        profiles = module.load_profiles()
        google = module.calculate_score(
            "google",
            profiles["google"],
            module.evaluate_factors(snapshot, "google", profiles["google"]["crawler"]),
        )
        bing = module.calculate_score(
            "bing",
            profiles["bing"],
            module.evaluate_factors(snapshot, "bing", profiles["bing"]["crawler"]),
        )
        self.assertGreaterEqual(google.normalized_score, 90)
        self.assertGreaterEqual(bing.normalized_score, 85)
        self.assertEqual(snapshot.sitemap_entry.lastmod, "2026-07-29")

    def test_snapshot_is_json_serializable(self):
        snapshot = module.build_snapshot(self.origin + "/", None, None, 5, "test-agent")
        json.dumps(module.snapshot_to_dict(snapshot))

    def test_sitemap_collection(self):
        collection = module.fetch_sitemaps([self.origin + "/sitemap.xml"], 5, "test-agent")
        self.assertEqual(len(collection.entries), 1)
        self.assertFalse(collection.errors)


if __name__ == "__main__":
    unittest.main()
