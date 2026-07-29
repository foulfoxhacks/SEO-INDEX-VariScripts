# IndexNow Public Runner

A small, dependency-light toolkit that reads XML sitemaps and submits their URLs to the global IndexNow endpoint.

## Included runners

- `Submit-IndexNow.ps1`: Windows PowerShell 5.1 and PowerShell 7+
- `indexnow_runner.py`: cross-platform Python 3 runner
- `submit-indexnow-macos.command`: macOS launcher
- `submit-indexnow-linux.sh`: Linux launcher

## Features

- Reads standard sitemap files and sitemap indexes recursively
- Supports GZip-compressed sitemap files
- Reads and validates the publicly hosted IndexNow key
- Enforces one exact canonical hostname
- Optionally rewrites one exact alternate hostname, such as `www.example.com` to `example.com`
- Rejects fragments, unsupported schemes, out-of-scope key paths, and foreign hosts
- Removes duplicate URLs
- Splits submissions into batches of at most 10,000 URLs
- Includes a dry-run mode before any POST request is sent
- Uses only built-in PowerShell/.NET features or the Python standard library

## Before running

1. Generate an IndexNow key containing 8 to 128 letters, numbers, or hyphens.
2. Host a plain-text file containing only that key.
3. Make sure the key file, sitemap URLs, canonical tags, and submitted page URLs use the same hostname.
4. Test with dry-run mode first.

The hosted key is intentionally public. It proves control of the site; it is not a password for a private account.

## Windows PowerShell

Dry run:

```powershell
.\Submit-IndexNow.ps1 `
  -SitemapUrl 'https://www.example.com/sitemap.xml' `
  -KeyLocation 'https://www.example.com/YOUR_KEY.txt' `
  -DryRun
```

Live submission:

```powershell
.\Submit-IndexNow.ps1 `
  -SitemapUrl 'https://www.example.com/sitemap.xml' `
  -KeyLocation 'https://www.example.com/YOUR_KEY.txt'
```

When Windows marks the downloaded script as internet-originated:

```powershell
Unblock-File -LiteralPath '.\Submit-IndexNow.ps1'
```

A one-process execution-policy override can be used from Command Prompt:

```cmd
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Submit-IndexNow.ps1" -SitemapUrl "https://www.example.com/sitemap.xml" -KeyLocation "https://www.example.com/YOUR_KEY.txt" -DryRun
```

## macOS

Python 3 is required. On a recent macOS installation without Python:

```bash
brew install python
```

Allow the launcher to run:

```bash
chmod +x submit-indexnow-macos.command indexnow_runner.py
```

Dry run:

```bash
./submit-indexnow-macos.command \
  --sitemap 'https://www.example.com/sitemap.xml' \
  --key-location 'https://www.example.com/YOUR_KEY.txt' \
  --dry-run
```

Live submission:

```bash
./submit-indexnow-macos.command \
  --sitemap 'https://www.example.com/sitemap.xml' \
  --key-location 'https://www.example.com/YOUR_KEY.txt'
```

## Linux

Allow the launcher to run:

```bash
chmod +x submit-indexnow-linux.sh indexnow_runner.py
```

Dry run:

```bash
./submit-indexnow-linux.sh \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/YOUR_KEY.txt' \
  --dry-run
```

Live submission:

```bash
./submit-indexnow-linux.sh \
  --sitemap 'https://example.com/sitemap.xml' \
  --key-location 'https://example.com/YOUR_KEY.txt'
```

## Temporary apex/www rewrite

Use this only when the sitemap has one known hostname mismatch. The runner rewrites the exact named host and rejects every other host.

PowerShell:

```powershell
.\Submit-IndexNow.ps1 `
  -SitemapUrl 'https://www.example.com/sitemap.xml' `
  -KeyLocation 'https://example.com/YOUR_KEY.txt' `
  -CanonicalHost 'example.com' `
  -RewriteHostFrom 'www.example.com' `
  -DryRun
```

macOS or Linux:

```bash
./submit-indexnow-linux.sh \
  --sitemap 'https://www.example.com/sitemap.xml' \
  --key-location 'https://example.com/YOUR_KEY.txt' \
  --canonical-host 'example.com' \
  --rewrite-host-from 'www.example.com' \
  --dry-run
```

Fix the sitemap generator afterward so a rewrite is no longer necessary.

## Multiple root sitemaps

PowerShell accepts an array:

```powershell
.\Submit-IndexNow.ps1 `
  -SitemapUrl @(
    'https://example.com/pages-sitemap.xml',
    'https://example.com/posts-sitemap.xml'
  ) `
  -KeyLocation 'https://example.com/YOUR_KEY.txt' `
  -DryRun
```

Python, macOS, and Linux accept repeated flags:

```bash
python3 indexnow_runner.py \
  --sitemap 'https://example.com/pages-sitemap.xml' \
  --sitemap 'https://example.com/posts-sitemap.xml' \
  --key-location 'https://example.com/YOUR_KEY.txt' \
  --dry-run
```

## HTTP results

- `200`: request received successfully
- `202`: request received; first-time key validation may still be pending
- `400`: malformed request
- `403`: key validation failed
- `422`: URL, host, key, or protocol validation failed
- `429`: rate limited

A successful response confirms receipt, not guaranteed indexing. Search engines still decide whether and when to crawl or index each URL.

## Responsible use

IndexNow is intended for URLs that were recently added, updated, deleted, moved, or redirected. Continue publishing a complete XML sitemap for long-term discovery. Avoid repeatedly submitting unchanged URLs.

Official documentation:

- https://www.indexnow.org/documentation
- https://www.indexnow.org/faq

## License

MIT. See `LICENSE`.
