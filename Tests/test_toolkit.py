#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "Py+Linux" / "Scripts"
CORE = SCRIPTS / "seo_index_toolkit.py"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("seo_index_toolkit", CORE)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)
import seo_index_extensions as extensions
import seo_index_site as site


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        host = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/redirect":
            self.send_response(301)
            self.send_header("Location", host + "/")
            self.end_headers()
            return
        if self.path == "/fr/":
            body = f"""<!doctype html><html lang="fr"><head>
<title>Page de test SEO</title><meta name="description" content="Description de test">
<link rel="canonical" href="{host}/fr/"><link rel="alternate" hreflang="fr" href="{host}/fr/">
<link rel="alternate" hreflang="en" href="{host}/">
</head><body><h1>Page de test</h1><p>{'texte indexable ' * 40}</p></body></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=60")
            self.end_headers(); self.wfile.write(body); return
        if self.path == "/":
            body = f"""<!doctype html><html lang="en"><head>
<title>Fixture page for SEO testing</title>
<meta name="description" content="Fixture description for deterministic toolkit tests.">
<meta name="robots" content="index, follow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta property="og:url" content="{host}/">
<meta name="author" content="Fixture Author">
<link rel="canonical" href="{host}/">
<link rel="alternate" hreflang="en" href="{host}/">
<link rel="alternate" hreflang="fr" href="{host}/fr/">
<script type="application/ld+json">{{
 "@context":"https://schema.org","@graph":[
 {{"@type":"WebSite","@id":"{host}/#website","url":"{host}/","name":"Fixture"}},
 {{"@type":"Organization","@id":"{host}/#org","name":"Fixture Org","sameAs":["https://example.social/fixture"]}},
 {{"@type":"WebPage","@id":"{host}/#page","url":"{host}/","dateModified":"2026-07-29","author":{{"@type":"Person","name":"Fixture Author"}},"breadcrumb":{{"@type":"BreadcrumbList"}}}},
 {{"@type":"FAQPage","mainEntity":[{{"@type":"Question","name":"What is this fixture?","acceptedAnswer":{{"@type":"Answer","text":"A deterministic test page."}}}}]}}
 ]}}</script>
</head><body>
<nav><a href="{host}/about">About</a><a href="{host}/contact">Contact</a><a href="{host}/missing">Read more</a></nav>
<main><h1>Fixture</h1><h2>What is this fixture?</h2><p>{'This is a concise crawlable answer with useful text. ' * 9}</p>
<h2>How does it work?</h2><p>{'The toolkit inspects machine-readable and human-readable signals. ' * 8}</p>
<ul><li>One</li><li>Two</li></ul><p><a href="https://schema.org/WebPage">Source documentation</a></p></main>
</body></html>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=60")
            self.send_header("ETag", '"fixture"')
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/robots.txt":
            body = f"User-agent: *\nAllow: /\nSitemap: {host}/sitemap.xml\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/sitemap.xml":
            body = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>{host}/</loc><lastmod>2026-07-29</lastmod></url>
<url><loc>{host}/fr/</loc><lastmod>2026-07-29</lastmod></url>
</urlset>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers(); self.wfile.write(body)
        elif self.path == "/fixture-key.txt":
            body = b"abcdef1234567890"
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(body)
        elif self.path == "/llms.txt":
            body = b"# Fixture\nA deterministic test site for SEO-INDEX VariScripts.\n"
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers(); self.wfile.write(body)
        elif self.path in {"/about", "/contact"}:
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(b"<html><body>About</body></html>")
        else:
            self.send_response(404); self.end_headers()


class ToolkitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close()

    def factors_for(self, engine: str):
        profiles = module.load_profiles()
        snapshot = module.build_snapshot(self.origin + "/", self.origin + "/sitemap.xml", self.origin + "/fixture-key.txt", 5, "test-agent")
        factors = module.evaluate_factors(snapshot, engine, profiles[engine]["crawler"])
        factors.update(extensions.enhance_factors(snapshot, engine, profiles[engine]["crawler"], 5, "test-agent"))
        return snapshot, profiles, factors

    def test_category_profiles_and_assurance(self):
        snapshot, profiles, factors = self.factors_for("google")
        google = module.calculate_score("google", profiles["google"], factors)
        self.assertGreaterEqual(google.verified_score, 80)
        self.assertLessEqual(google.assured_score, google.verified_score)
        self.assertGreaterEqual(google.coverage, 90)
        self.assertIn("eligibility", google.categories)
        self.assertEqual(snapshot.sitemap_entry.lastmod, "2026-07-29")
        self.assertIn("geo", profiles)
        self.assertIn("aeo", profiles)

    def test_geo_and_aeo_profiles(self):
        for profile_name in ("geo", "aeo"):
            _, profiles, factors = self.factors_for(profile_name)
            result = module.calculate_score(profile_name, profiles[profile_name], factors)
            self.assertGreaterEqual(result.assured_score, 70)
            self.assertGreater(len(result.categories), 3)

    def test_redirect_trace(self):
        report = extensions.trace_redirects(self.origin + "/redirect", 5, "test-agent")
        self.assertEqual(report.hops[0].status, 301)
        self.assertEqual(report.final_status, 200)
        self.assertEqual(extensions.redirect_factor(report).status, "pass")

    def test_extended_html_and_hreflang(self):
        page = module.fetch_url(self.origin + "/", 5, "test-agent")
        signals = extensions.parse_extended_html(page)
        self.assertIn("Organization", signals.schema_type_set)
        self.assertGreaterEqual(signals.question_headings, 2)
        self.assertEqual(len(signals.hreflang), 2)
        self.assertTrue(signals.same_as)

    def test_snapshot_is_json_serializable(self):
        snapshot = module.build_snapshot(self.origin + "/", None, None, 5, "test-agent")
        json.dumps(module.snapshot_to_dict(snapshot))

    def test_sitemap_collection(self):
        collection = module.fetch_sitemaps([self.origin + "/sitemap.xml"], 5, "test-agent")
        self.assertEqual(len(collection.entries), 2)
        self.assertFalse(collection.errors)

    def test_internal_link_graph(self):
        report = site.crawl_internal_links(
            self.origin + "/",
            sitemap=self.origin + "/sitemap.xml",
            max_pages=20,
            max_depth=3,
            timeout=5,
            user_agent="test-agent",
            robots_agent="Googlebot",
            delay_ms=0,
        )
        self.assertGreaterEqual(report.summary["pagesCrawled"], 4)
        self.assertGreaterEqual(report.summary["internalEdges"], 3)
        self.assertEqual(report.summary["brokenPages"], 1)
        self.assertIn(self.origin + "/fr/", report.findings["orphanCandidates"])
        self.assertTrue(report.findings["genericAnchors"])

    def test_internal_link_graph_html(self):
        report = site.crawl_internal_links(
            self.origin + "/", max_pages=10, max_depth=2, timeout=5,
            user_agent="test-agent", delay_ms=0,
        )
        output = Path(__file__).with_name("_link_graph_report.html")
        try:
            site.write_link_report_html(report, str(output))
            content = output.read_text(encoding="utf-8")
            self.assertIn("Internal Link Graph", content)
            self.assertIn('type="application/json"', content)
        finally:
            output.unlink(missing_ok=True)

    def test_private_target_detection(self):
        self.assertTrue(site._is_private_target(self.origin + "/"))


if __name__ == "__main__":
    unittest.main()
