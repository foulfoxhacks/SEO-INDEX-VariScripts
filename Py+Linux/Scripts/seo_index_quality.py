#!/usr/bin/env python3
"""Comprehensive single-page quality audit for SEO-INDEX VariScripts.

The checks intentionally separate search eligibility from presentation, media,
accessibility, delivery, and browser-security diagnostics. Heuristic length and
size budgets are labelled as such; they are not search-engine ranking rules.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import urljoin, urlsplit

import seo_index_extensions as extensions
import seo_index_toolkit as core


GENERIC_LINK_TEXT = {
    "click here", "continue", "details", "here", "learn more", "link",
    "more", "open", "read more", "this page", "view", "website",
}


@dataclass
class ImageSignal:
    src: str
    alt: str
    alt_present: bool
    width: str = ""
    height: str = ""
    loading: str = ""
    decoding: str = ""
    srcset: str = ""


@dataclass
class PageLinkSignal:
    href: str
    text: str
    accessible_name: str
    rel: list[str] = field(default_factory=list)
    target: str = ""


@dataclass
class QualitySignals:
    metadata: dict[str, list[str]] = field(default_factory=dict)
    resources: dict[str, list[str]] = field(default_factory=dict)
    images: list[ImageSignal] = field(default_factory=list)
    links: list[PageLinkSignal] = field(default_factory=list)
    headings: list[dict[str, Any]] = field(default_factory=list)
    word_count: int = 0


@dataclass
class QualityFinding:
    id: str
    status: str
    label: str
    message: str
    evidence: Any = None


@dataclass
class PageQualityReport:
    schema_version: str
    tool: str
    tool_version: str
    generated_at: str
    requested_url: str
    final_url: str
    summary: dict[str, Any]
    sections: dict[str, list[QualityFinding]]
    signals: QualitySignals

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "tool": self.tool,
            "toolVersion": self.tool_version,
            "generatedAt": self.generated_at,
            "requestedUrl": self.requested_url,
            "finalUrl": self.final_url,
            "summary": self.summary,
            "sections": {
                section: [asdict(finding) for finding in findings]
                for section, findings in self.sections.items()
            },
            "signals": asdict(self.signals),
        }


class QualityHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.metadata: dict[str, list[str]] = {}
        self.resources: dict[str, list[str]] = {}
        self.images: list[ImageSignal] = []
        self.links: list[PageLinkSignal] = []
        self.headings: list[dict[str, Any]] = []
        self.skip_depth = 0
        self.heading_level = 0
        self.heading_parts: list[str] = []
        self.anchor: Optional[dict[str, Any]] = None
        self.anchor_parts: list[str] = []
        self.body_parts: list[str] = []

    @staticmethod
    def _attrs(attrs: list[tuple[str, Optional[str]]]) -> dict[str, str]:
        return {str(key).lower(): (value or "") for key, value in attrs}

    def _add_meta(self, key: str, value: str) -> None:
        if key and value:
            self.metadata.setdefault(key.lower(), []).append(value.strip())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        values = self._attrs(attrs)
        if tag in {"script", "style", "noscript", "template"}:
            self.skip_depth += 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.heading_level = int(tag[1])
            self.heading_parts = []
        elif tag == "meta":
            key = values.get("name", "") or values.get("property", "") or values.get("http-equiv", "")
            self._add_meta(key, values.get("content", ""))
            if values.get("charset"):
                self._add_meta("charset", values["charset"])
        elif tag == "link":
            href = values.get("href", "").strip()
            for rel in values.get("rel", "").lower().split():
                if href:
                    self.resources.setdefault(rel, []).append(urljoin(self.base_url, href))
        elif tag == "img":
            src = values.get("src", "").strip()
            self.images.append(ImageSignal(
                src=urljoin(self.base_url, src) if src else "",
                alt=values.get("alt", ""),
                alt_present="alt" in values,
                width=values.get("width", ""),
                height=values.get("height", ""),
                loading=values.get("loading", "").lower(),
                decoding=values.get("decoding", "").lower(),
                srcset=values.get("srcset", ""),
            ))
        elif tag == "a":
            href = values.get("href", "").strip()
            self.anchor = {
                "href": urljoin(self.base_url, href) if href else "",
                "accessible_name": values.get("aria-label", "").strip() or values.get("title", "").strip(),
                "rel": sorted(set(values.get("rel", "").lower().split())),
                "target": values.get("target", "").lower(),
            }
            self.anchor_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "template"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self.heading_level:
            value = " ".join("".join(self.heading_parts).split())
            if value:
                self.headings.append({"level": self.heading_level, "text": value})
            self.heading_level = 0
            self.heading_parts = []
        elif tag == "a" and self.anchor is not None:
            text = " ".join("".join(self.anchor_parts).split())
            self.links.append(PageLinkSignal(
                href=self.anchor["href"],
                text=text,
                accessible_name=self.anchor["accessible_name"] or text,
                rel=self.anchor["rel"],
                target=self.anchor["target"],
            ))
            self.anchor = None
            self.anchor_parts = []

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = " ".join(data.split())
        if not value:
            return
        self.body_parts.append(value)
        if self.heading_level:
            self.heading_parts.append(value + " ")
        if self.anchor is not None:
            self.anchor_parts.append(value + " ")

    def signals(self) -> QualitySignals:
        body = " ".join(self.body_parts)
        return QualitySignals(
            metadata=self.metadata,
            resources=self.resources,
            images=self.images,
            links=self.links,
            headings=self.headings,
            word_count=len(re.findall(r"\b[\w'-]+\b", body, flags=re.UNICODE)),
        )


def parse_quality_html(fetch: core.FetchResult) -> QualitySignals:
    content_type = fetch.headers.get("content-type", "").lower()
    if fetch.status == 0 or ("html" not in content_type and not fetch.text.lstrip().lower().startswith(("<!doctype html", "<html"))):
        return QualitySignals()
    parser = QualityHTMLParser(fetch.final_url or fetch.requested_url)
    try:
        parser.feed(fetch.text)
        parser.close()
    except Exception:
        return parser.signals()
    return parser.signals()


def _first(signals: QualitySignals, key: str) -> str:
    values = signals.metadata.get(key.lower(), [])
    return values[0] if values else ""


def _add(
    sections: dict[str, list[QualityFinding]],
    section: str,
    finding_id: str,
    status: str,
    label: str,
    message: str,
    evidence: Any = None,
) -> None:
    sections.setdefault(section, []).append(QualityFinding(finding_id, status, label, message, evidence))


def _heading_skips(headings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    skips: list[dict[str, Any]] = []
    previous = 0
    for heading in headings:
        level = int(heading["level"])
        if previous and level > previous + 1:
            skips.append({"from": previous, "to": level, "text": heading["text"]})
        previous = level
    return skips


def analyze_page(fetch: core.FetchResult) -> PageQualityReport:
    basic = core.parse_html(fetch)
    extended = extensions.parse_extended_html(fetch)
    signals = parse_quality_html(fetch)
    sections: dict[str, list[QualityFinding]] = {}
    final_url = fetch.final_url or fetch.requested_url
    content_type = fetch.headers.get("content-type", "").lower()

    _add(sections, "Eligibility", "http-status", "pass" if fetch.status == 200 else "fail", "HTTP status",
         f"Final response is HTTP {fetch.status}." if fetch.status else f"Request failed: {fetch.error or 'network error'}.", fetch.status)
    _add(sections, "Eligibility", "html-content", "pass" if "html" in content_type else "fail", "HTML content type",
         content_type or "No Content-Type header was returned.", content_type)
    directives = set(basic.meta_robots.get("robots", set())) | core.parse_x_robots(fetch.headers, "generic")
    blocked = "noindex" in directives or "none" in directives
    _add(sections, "Eligibility", "index-directives", "fail" if blocked else "pass", "Index directives",
         f"Effective directives: {', '.join(sorted(directives))}." if directives else "No noindex directive was found.", sorted(directives))
    _add(sections, "Eligibility", "https", "pass" if urlsplit(final_url).scheme == "https" else "warn", "HTTPS",
         "The final page uses HTTPS." if urlsplit(final_url).scheme == "https" else "The final page uses HTTP.", final_url)

    title_length = len(basic.title)
    title_status = "fail" if not basic.title else ("pass" if 15 <= title_length <= 70 else "warn")
    _add(sections, "Search presentation", "title", title_status, "Page title",
         "Title is missing." if not basic.title else f"Title is {title_length} characters (the range is a display heuristic, not a ranking rule).", basic.title)
    description_length = len(basic.description)
    description_status = "warn" if not basic.description or not 50 <= description_length <= 170 else "pass"
    _add(sections, "Search presentation", "description", description_status, "Meta description",
         "Meta description is missing." if not basic.description else f"Description is {description_length} characters (a display heuristic).", basic.description)
    if not basic.canonical:
        canonical_status, canonical_message = "warn", "No rel=canonical annotation was found."
    else:
        try:
            matches = core.normalize_url(basic.canonical) == core.normalize_url(final_url)
            canonical_status = "pass" if matches else "fail"
            canonical_message = "Canonical matches the final URL." if matches else "Canonical differs from the final URL."
        except core.ToolkitError:
            canonical_status, canonical_message = "fail", "Canonical is not a valid absolute HTTP(S) URL."
    _add(sections, "Search presentation", "canonical", canonical_status, "Canonical", canonical_message, basic.canonical)
    _add(sections, "Search presentation", "h1", "pass" if basic.h1_count == 1 else ("warn" if basic.h1_count > 1 else "fail"), "H1 count",
         f"Detected {basic.h1_count} H1 element(s).", basic.h1_count)
    _add(sections, "Search presentation", "structured-data", "warn" if basic.json_ld_blocks == 0 else ("pass" if basic.json_ld_valid == basic.json_ld_blocks else "fail"), "JSON-LD",
         f"Parsed {basic.json_ld_valid} of {basic.json_ld_blocks} block(s).", basic.json_ld_errors)

    social_values = {
        "og:title": _first(signals, "og:title"),
        "og:description": _first(signals, "og:description"),
        "og:image": _first(signals, "og:image"),
        "og:url": _first(signals, "og:url"),
    }
    social_present = sum(bool(value) for value in social_values.values())
    _add(sections, "Social previews", "open-graph", "pass" if social_present == 4 else "warn", "Open Graph",
         f"Found {social_present}/4 core Open Graph fields.", social_values)
    twitter_values = {
        "twitter:card": _first(signals, "twitter:card"),
        "twitter:title": _first(signals, "twitter:title"),
        "twitter:description": _first(signals, "twitter:description"),
        "twitter:image": _first(signals, "twitter:image"),
    }
    twitter_present = sum(bool(value) for value in twitter_values.values())
    _add(sections, "Social previews", "twitter-card", "pass" if twitter_present >= 3 else "warn", "Social card metadata",
         f"Found {twitter_present}/4 Twitter/X card fields; Open Graph may provide fallbacks.", twitter_values)

    missing_alt = [image.src for image in signals.images if not image.alt_present]
    missing_dimensions = [image.src for image in signals.images if not image.width or not image.height]
    responsive = [image.src for image in signals.images if image.srcset]
    lazy = [image.src for image in signals.images if image.loading == "lazy"]
    _add(sections, "Images", "image-alt", "fail" if missing_alt else "pass", "Image alternatives",
         f"{len(missing_alt)} of {len(signals.images)} image(s) omit the alt attribute." if missing_alt else f"All {len(signals.images)} image(s) declare alt (empty alt is valid for decorative images).", missing_alt[:50])
    _add(sections, "Images", "image-dimensions", "warn" if missing_dimensions else "pass", "Intrinsic dimensions",
         f"{len(missing_dimensions)} image(s) omit width or height." if missing_dimensions else "All images declare width and height.", missing_dimensions[:50])
    media_status = "pass" if not signals.images or responsive or lazy else ("warn" if len(signals.images) >= 3 else "pass")
    _add(sections, "Images", "image-delivery", media_status, "Responsive and lazy delivery",
         f"Detected {len(responsive)} responsive and {len(lazy)} lazy-loaded image(s) among {len(signals.images)} total.", {"responsive": len(responsive), "lazy": len(lazy)})

    heading_skips = _heading_skips(signals.headings)
    _add(sections, "Content and accessibility", "language", "pass" if extended.lang else "warn", "Document language",
         f"html lang is {extended.lang}." if extended.lang else "The html element has no lang attribute.", extended.lang)
    _add(sections, "Content and accessibility", "viewport", "pass" if basic.viewport else "warn", "Mobile viewport",
         "Viewport metadata is present." if basic.viewport else "Viewport metadata is missing.", basic.viewport)
    _add(sections, "Content and accessibility", "heading-order", "warn" if heading_skips else "pass", "Heading order",
         f"Detected {len(heading_skips)} skipped heading level transition(s)." if heading_skips else "No skipped heading-level transitions were detected.", heading_skips[:30])
    _add(sections, "Content and accessibility", "word-count", "warn" if signals.word_count < 100 else "pass", "Visible text",
         f"Detected approximately {signals.word_count:,} visible word(s).", signals.word_count)
    empty_links = [link.href for link in signals.links if link.href and not link.accessible_name]
    generic_links = [{"href": link.href, "text": link.text} for link in signals.links if link.text.strip().lower() in GENERIC_LINK_TEXT]
    _add(sections, "Content and accessibility", "link-names", "fail" if empty_links else "pass", "Accessible link names",
         f"{len(empty_links)} link(s) have no text, aria-label, or title." if empty_links else "All links with destinations have an accessible text signal.", empty_links[:50])
    _add(sections, "Content and accessibility", "generic-links", "warn" if generic_links else "pass", "Descriptive link text",
         f"Detected {len(generic_links)} generic link label(s)." if generic_links else "No common generic link labels were detected.", generic_links[:50])

    encoding = fetch.headers.get("content-encoding", "").lower()
    _add(sections, "Delivery", "compression", "pass" if encoding in {"gzip", "br", "zstd"} else "warn", "Compression",
         f"Content-Encoding is {encoding}." if encoding else "No response compression was observed.", encoding)
    cache_headers = {name: fetch.headers.get(name, "") for name in ("cache-control", "etag", "last-modified")}
    _add(sections, "Delivery", "caching", "pass" if any(cache_headers.values()) else "warn", "Caching and freshness",
         "At least one caching/freshness header is present." if any(cache_headers.values()) else "Cache-Control, ETag, and Last-Modified are absent.", cache_headers)
    elapsed_status = "pass" if fetch.elapsed_ms <= 1000 else ("warn" if fetch.elapsed_ms <= 2500 else "fail")
    _add(sections, "Delivery", "response-time", elapsed_status, "Observed response time",
         f"One server-side fetch completed in {fetch.elapsed_ms:,} ms; this is not a Core Web Vitals measurement.", fetch.elapsed_ms)
    size = len(fetch.data)
    size_status = "pass" if size <= 200_000 else ("warn" if size <= 1_000_000 else "fail")
    _add(sections, "Delivery", "html-size", size_status, "Decoded HTML size",
         f"Response body is {size:,} bytes against diagnostic budgets of 200 KB/1 MB.", size)

    headers = fetch.headers
    security_checks = [
        ("content-security-policy", "Content-Security-Policy", bool(headers.get("content-security-policy"))),
        ("nosniff", "X-Content-Type-Options", headers.get("x-content-type-options", "").lower() == "nosniff"),
        ("referrer-policy", "Referrer-Policy", bool(headers.get("referrer-policy"))),
        ("frame-protection", "Frame embedding protection", bool(headers.get("x-frame-options")) or "frame-ancestors" in headers.get("content-security-policy", "").lower()),
    ]
    if urlsplit(final_url).scheme == "https":
        security_checks.append(("hsts", "Strict-Transport-Security", bool(headers.get("strict-transport-security"))))
    for finding_id, label, present in security_checks:
        _add(sections, "Browser security", finding_id, "pass" if present else "warn", label,
             f"{label} is present." if present else f"{label} was not observed.", headers.get(label.lower(), ""))

    all_findings = [finding for findings in sections.values() for finding in findings]
    counts = {status: sum(finding.status == status for finding in all_findings) for status in ("pass", "warn", "fail")}
    score = round((counts["pass"] + counts["warn"] * 0.5) / max(1, len(all_findings)) * 100)
    summary = {
        "qualityScore": score,
        "checks": len(all_findings),
        "passed": counts["pass"],
        "warnings": counts["warn"],
        "failures": counts["fail"],
        "images": len(signals.images),
        "links": len(signals.links),
        "wordCount": signals.word_count,
        "elapsedMs": fetch.elapsed_ms,
        "htmlBytes": size,
    }
    return PageQualityReport(
        schema_version="1.0",
        tool="page-quality",
        tool_version=core.VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        requested_url=fetch.requested_url,
        final_url=final_url,
        summary=summary,
        sections=sections,
        signals=signals,
    )


def audit_page(
    url: str,
    timeout: int,
    user_agent: str,
    url_validator: Optional[Callable[[str], None]] = None,
) -> PageQualityReport:
    return analyze_page(core.fetch_url(url, timeout, user_agent, url_validator=url_validator))


def write_markdown(report: PageQualityReport, path: str) -> None:
    lines = [
        "# Page Quality Audit",
        "",
        f"- URL: {report.final_url}",
        f"- Generated: {report.generated_at}",
        f"- Quality score: {report.summary['qualityScore']}/100",
        f"- Results: {report.summary['passed']} pass, {report.summary['warnings']} warn, {report.summary['failures']} fail",
        "",
        "> Diagnostic heuristics only. This report does not predict ranking, indexing, traffic, or Core Web Vitals.",
        "",
    ]
    for section, findings in report.sections.items():
        lines.extend([f"## {section}", "", "| Status | Check | Result |", "|---|---|---|"])
        for finding in findings:
            message = finding.message.replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {finding.status.upper()} | {finding.label} | {message} |")
        lines.append("")
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def run_page(args: argparse.Namespace, console: core.Console) -> int:
    report = audit_page(args.url, args.timeout, args.user_agent)
    print(console.paint("Page Quality Audit", core.Style.BOLD, core.Style.CYAN))
    print(f"  Page:  {report.final_url}")
    print(f"  Score: {report.summary['qualityScore']}/100 · {report.summary['passed']} pass · {report.summary['warnings']} warn · {report.summary['failures']} fail")
    print("  Heuristic diagnostics; response timing is not a Core Web Vitals measurement.\n")
    for section, findings in report.sections.items():
        print(console.paint(section, core.Style.BOLD, core.Style.WHITE))
        for finding in findings:
            print(f"  {console.status(finding.status)}  {finding.label:28s} {finding.message}")
        print()
    if args.json:
        core.write_json(args.json, report.to_dict())
        print(f"JSON report written to {args.json}")
    if args.markdown:
        write_markdown(report, args.markdown)
        print(f"Markdown report written to {args.markdown}")
    if args.fail_on == "warning" and (report.summary["warnings"] or report.summary["failures"]):
        return 2
    if args.fail_on == "critical" and report.summary["failures"]:
        return 2
    return 0
