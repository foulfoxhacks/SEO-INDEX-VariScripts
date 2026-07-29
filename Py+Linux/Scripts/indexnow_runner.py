#!/usr/bin/env python3
"""Public, site-agnostic IndexNow sitemap runner.

Reads XML sitemaps or sitemap indexes recursively, validates a hosted IndexNow
key, normalizes URLs to one canonical host, and submits batches to IndexNow.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, Optional
from urllib.parse import SplitResult, urlsplit, urlunsplit

VERSION = "1.0.0"
DEFAULT_ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9-]{8,128}$")
SUPPORTED_SCHEMES = {"http", "https"}
STATUS_MEANINGS = {
    200: "OK: request received successfully.",
    202: "Accepted: request received; key validation may still be pending.",
    400: "Bad Request: invalid request format.",
    403: "Forbidden: key validation failed.",
    422: "Unprocessable Entity: URL, host, key, or protocol validation failed.",
    429: "Too Many Requests: rate limited.",
}


class RunnerError(RuntimeError):
    """Expected validation or network failure."""


@dataclass(frozen=True)
class FetchResult:
    data: bytes
    final_url: str
    status: int


def normalize_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    if not host:
        raise RunnerError("A hostname cannot be empty.")
    if "://" in host or "/" in host or ":" in host:
        raise RunnerError(
            f"Use a hostname without a scheme, path, or port: {value!r}"
        )
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise RunnerError(f"Invalid hostname {value!r}: {exc}") from exc


def require_http_url(value: str, label: str) -> SplitResult:
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in SUPPORTED_SCHEMES or not parsed.hostname:
        raise RunnerError(f"{label} must be an absolute HTTP or HTTPS URL: {value}")
    if parsed.username or parsed.password:
        raise RunnerError(f"{label} must not contain embedded credentials: {value}")
    return parsed


def fetch_bytes(url: str, timeout: int, user_agent: str) -> FetchResult:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/xml,text/xml,text/plain,*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return FetchResult(
                data=response.read(),
                final_url=response.geturl(),
                status=int(response.status),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = f" Response: {body[:500]}" if body else ""
        raise RunnerError(f"GET {url} failed with HTTP {exc.code}.{detail}") from exc
    except urllib.error.URLError as exc:
        raise RunnerError(f"GET {url} failed: {exc.reason}") from exc


def decode_remote_text(result: FetchResult) -> str:
    data = result.data
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except OSError as exc:
            raise RunnerError(f"Could not decompress GZip response from {result.final_url}") from exc
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("utf-8", errors="replace")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_locations(root: ET.Element, parent_name: str) -> list[str]:
    values: list[str] = []
    for parent in root:
        if local_name(parent.tag) != parent_name:
            continue
        for child in parent:
            if local_name(child.tag) == "loc" and child.text:
                value = child.text.strip()
                if value:
                    values.append(value)
    return values


def collect_sitemap_urls(
    sitemap_urls: Iterable[str],
    timeout: int,
    user_agent: str,
    max_sitemaps: int,
) -> tuple[list[str], int]:
    visited: set[str] = set()
    page_urls: list[str] = []

    def visit(url: str) -> None:
        parsed = require_http_url(url, "Sitemap URL")
        normalized_visit = urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path or "/",
                parsed.query,
                "",
            )
        )
        if normalized_visit in visited:
            return
        if len(visited) >= max_sitemaps:
            raise RunnerError(
                f"The sitemap traversal exceeded --max-sitemaps ({max_sitemaps})."
            )
        visited.add(normalized_visit)
        print(f"Reading sitemap: {url}")

        result = fetch_bytes(url, timeout, user_agent)
        text = decode_remote_text(result)
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise RunnerError(f"Could not parse sitemap XML at {url}: {exc}") from exc

        root_name = local_name(root.tag)
        if root_name == "sitemapindex":
            children = child_locations(root, "sitemap")
            if not children:
                raise RunnerError(f"Sitemap index contains no child sitemap locations: {url}")
            for child in children:
                visit(child)
            return

        if root_name == "urlset":
            page_urls.extend(child_locations(root, "url"))
            return

        raise RunnerError(
            f"Unsupported sitemap root element {root_name!r} at {url}; "
            "expected 'urlset' or 'sitemapindex'."
        )

    for sitemap_url in sitemap_urls:
        visit(sitemap_url)

    return page_urls, len(visited)


def key_scope_directory(key_location: str) -> str:
    parsed = require_http_url(key_location, "Key location")
    path = parsed.path or "/"
    directory = str(PurePosixPath(path).parent)
    if directory in {"", "."}:
        directory = "/"
    if not directory.startswith("/"):
        directory = "/" + directory
    if directory != "/" and not directory.endswith("/"):
        directory += "/"
    return directory


def replace_host(parsed: SplitResult, canonical_host: str) -> str:
    port = parsed.port
    netloc = canonical_host
    if port is not None:
        netloc = f"{canonical_host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, ""))


def normalize_page_urls(
    raw_urls: Iterable[str],
    canonical_host: str,
    rewrite_host_from: Optional[str],
    key_directory: str,
) -> tuple[list[str], int, list[str]]:
    normalized: set[str] = set()
    invalid: list[str] = []
    rewritten = 0

    for raw in raw_urls:
        try:
            parsed = require_http_url(raw, "Sitemap page URL")
            if parsed.fragment:
                raise RunnerError("Fragments are not allowed in sitemap URLs.")
            assert parsed.hostname is not None
            page_host = normalize_host(parsed.hostname)

            if page_host == canonical_host:
                value = urlunsplit(
                    (
                        parsed.scheme.lower(),
                        parsed.netloc.lower(),
                        parsed.path or "/",
                        parsed.query,
                        "",
                    )
                )
            elif rewrite_host_from and page_host == rewrite_host_from:
                value = replace_host(parsed, canonical_host)
                rewritten += 1
            else:
                raise RunnerError(
                    f"Host {page_host!r} does not match canonical host {canonical_host!r}."
                )

            canonical = urlsplit(value)
            if key_directory != "/" and not (canonical.path or "/").startswith(key_directory):
                raise RunnerError(
                    f"URL path is outside the key file scope {key_directory!r}."
                )
            normalized.add(value)
        except (RunnerError, ValueError) as exc:
            invalid.append(f"{raw} ({exc})")

    return sorted(normalized), rewritten, invalid


def post_batch(
    endpoint: str,
    payload: dict[str, object],
    timeout: int,
    user_agent: str,
) -> tuple[int, str]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "User-Agent": user_agent,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json,text/plain,*/*",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace").strip()
            return int(response.status), response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace").strip()
        meaning = STATUS_MEANINGS.get(exc.code, "Unexpected HTTP response.")
        detail = f" Response: {response_body[:500]}" if response_body else ""
        raise RunnerError(f"HTTP {exc.code} - {meaning}{detail}") from exc
    except urllib.error.URLError as exc:
        raise RunnerError(f"POST {endpoint} failed: {exc.reason}") from exc


def batched(values: list[str], size: int) -> Iterable[list[str]]:
    for offset in range(0, len(values), size):
        yield values[offset : offset + size]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read XML sitemaps, validate their URLs against a hosted IndexNow "
            "key, and submit them in batches."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--sitemap",
        action="append",
        required=True,
        help="Sitemap or sitemap-index URL. Repeat for multiple root sitemaps.",
    )
    parser.add_argument(
        "--key-location",
        required=True,
        help="Public URL of the hosted IndexNow key file.",
    )
    parser.add_argument(
        "--canonical-host",
        help="Canonical hostname. Defaults to the hostname in --key-location.",
    )
    parser.add_argument(
        "--rewrite-host-from",
        help="Optional exact alternate hostname to rewrite to the canonical host.",
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT, help="IndexNow POST endpoint.")
    parser.add_argument("--batch-size", type=int, default=10_000, help="URLs per POST request.")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between live batches.")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--max-sitemaps", type=int, default=1000, help="Maximum recursively fetched sitemap files."
    )
    parser.add_argument(
        "--user-agent", default=f"IndexNow-Public-Runner/{VERSION}", help="HTTP User-Agent."
    )
    parser.add_argument("--show-urls", action="store_true", help="Print every normalized URL.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without sending a POST.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if not 1 <= args.batch_size <= 10_000:
        raise RunnerError("--batch-size must be between 1 and 10,000.")
    if not 0 <= args.delay <= 300:
        raise RunnerError("--delay must be between 0 and 300 seconds.")
    if not 1 <= args.timeout <= 600:
        raise RunnerError("--timeout must be between 1 and 600 seconds.")
    if not 1 <= args.max_sitemaps <= 10_000:
        raise RunnerError("--max-sitemaps must be between 1 and 10,000.")

    key_parsed = require_http_url(args.key_location, "Key location")
    require_http_url(args.endpoint, "Endpoint")
    for sitemap in args.sitemap:
        require_http_url(sitemap, "Sitemap URL")

    assert key_parsed.hostname is not None
    canonical_host = normalize_host(args.canonical_host or key_parsed.hostname)
    key_host = normalize_host(key_parsed.hostname)
    if key_host != canonical_host:
        raise RunnerError(
            f"Key file host {key_host!r} does not match canonical host {canonical_host!r}."
        )

    rewrite_host = (
        normalize_host(args.rewrite_host_from) if args.rewrite_host_from else None
    )
    if rewrite_host == canonical_host:
        raise RunnerError("--rewrite-host-from must differ from --canonical-host.")

    print()
    print(f"IndexNow Public Runner {VERSION}")
    print("=" * 27)
    print(f"Canonical host: {canonical_host}")
    print(f"Key file:      {args.key_location}")
    print(f"Endpoint:      {args.endpoint}")
    print(f"Sitemaps:      {len(args.sitemap)}")
    print(
        f"Host rewrite:  {rewrite_host} -> {canonical_host}"
        if rewrite_host
        else "Host rewrite:  disabled"
    )
    print(f"Mode:          {'DRY RUN' if args.dry_run else 'LIVE SUBMISSION'}")
    print()

    print(f"Checking hosted IndexNow key: {args.key_location}")
    key_result = fetch_bytes(args.key_location, args.timeout, args.user_agent)
    final_key = require_http_url(key_result.final_url, "Final key location")
    assert final_key.hostname is not None
    final_key_host = normalize_host(final_key.hostname)
    if final_key_host != canonical_host:
        raise RunnerError(
            "The key URL redirected to a different host: "
            f"{final_key_host!r}, expected {canonical_host!r}."
        )

    key = decode_remote_text(key_result).strip().lstrip("\ufeff")
    if not KEY_PATTERN.fullmatch(key):
        raise RunnerError("The hosted key must be 8-128 letters, numbers, or hyphens.")

    raw_urls, sitemap_count = collect_sitemap_urls(
        args.sitemap, args.timeout, args.user_agent, args.max_sitemaps
    )
    if not raw_urls:
        raise RunnerError("No page URLs were found in the supplied sitemap files.")

    urls, rewritten, invalid = normalize_page_urls(
        raw_urls,
        canonical_host,
        rewrite_host,
        key_scope_directory(args.key_location),
    )
    if invalid:
        examples = "\n  ".join(invalid[:5])
        raise RunnerError(
            f"Found {len(invalid)} invalid, out-of-scope, or non-canonical URL(s). "
            f"Expected host {canonical_host!r}. Examples:\n  {examples}"
        )
    if not urls:
        raise RunnerError("No valid canonical URLs remain after validation.")

    print(
        f"Read {sitemap_count} sitemap file(s), found {len(raw_urls)} URL(s), "
        f"and prepared {len(urls)} unique canonical URL(s)."
    )
    if rewritten:
        print(
            f"WARNING: Rewrote {rewritten} URL(s) from {rewrite_host!r} "
            f"to {canonical_host!r}. Fix the sitemap when practical.",
            file=sys.stderr,
        )

    print()
    print("Canonical URLs:" if args.show_urls else "First canonical URLs:")
    for value in (urls if args.show_urls else urls[:5]):
        print(f"  {value}")
    print()

    batches = list(batched(urls, args.batch_size))
    results: list[tuple[int, int, int | None, str]] = []

    for number, batch in enumerate(batches, start=1):
        if args.dry_run:
            print(
                f"[Dry run] Batch {number} would submit {len(batch)} URL(s) "
                f"to {args.endpoint}"
            )
            results.append((number, len(batch), None, "Dry run"))
        else:
            payload: dict[str, object] = {
                "host": canonical_host,
                "key": key,
                "keyLocation": args.key_location,
                "urlList": batch,
            }
            status, response_body = post_batch(
                args.endpoint, payload, args.timeout, args.user_agent
            )
            meaning = STATUS_MEANINGS.get(status, "Unexpected HTTP response.")
            detail = f" Response: {response_body[:500]}" if response_body else ""
            print(f"Batch {number}: HTTP {status} - {meaning}{detail}")
            results.append((number, len(batch), status, meaning))
            if number < len(batches) and args.delay:
                time.sleep(args.delay)

    print()
    print(f"Completed {len(batches)} batch(es), covering {len(urls)} unique URL(s).")
    print()
    print(f"{'Batch':>5} {'URLs':>8} {'HTTP':>6}  Status")
    print(f"{'-' * 5} {'-' * 8} {'-' * 6}  {'-' * 30}")
    for number, count, status, meaning in results:
        status_text = "-" if status is None else str(status)
        print(f"{number:>5} {count:>8} {status_text:>6}  {meaning}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        raise SystemExit(130)
