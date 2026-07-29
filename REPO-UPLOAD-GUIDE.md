# Publish v1.2.0 to GitHub

This package is arranged to merge into the root of `foulfoxhacks/SEO-INDEX-VariScripts`.

## Windows PowerShell

```powershell
$Repo = "$HOME\Documents\Projects\SEO-INDEX-VariScripts"
$Package = "$HOME\Documents\Projects\SEO-INDEX-VariScripts-v1.2.0-full.zip"
$Stage = Join-Path $env:TEMP "seo-index-v1.2.0"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -LiteralPath $Package -DestinationPath $Stage -Force
$Source = Join-Path $Stage "SEO-INDEX-VariScripts-v1.2.0"

robocopy $Source $Repo /E /XD .git __pycache__
if ($LASTEXITCODE -ge 8) { throw "Robocopy failed: $LASTEXITCODE" }

python -m py_compile "$Repo\Py+Linux\Scripts\seo_index_toolkit.py" "$Repo\Py+Linux\Scripts\seo_index_extensions.py"
python "$Repo\Tests\test_toolkit.py"

git -C $Repo add .
git -C $Repo update-index --chmod=+x -- `
  "seo-index" `
  "install.sh" `
  "MacOS/seo-index-toolkit.command" `
  "MacOS/submit-indexnow-macos.command" `
  "MacOS/redirect-lab.command" `
  "MacOS/geo-audit.command" `
  "MacOS/aeo-audit.command" `
  "Py+Linux/Scripts/seo-index-toolkit.sh" `
  "Py+Linux/Scripts/submit-indexnow-linux.sh" `
  "Py+Linux/Scripts/redirect-audit.sh" `
  "Py+Linux/Scripts/robots-audit.sh" `
  "Py+Linux/Scripts/hreflang-audit.sh" `
  "Py+Linux/Scripts/schema-audit.sh" `
  "Py+Linux/Scripts/geo-audit.sh" `
  "Py+Linux/Scripts/aeo-audit.sh"

git -C $Repo commit -m "feat: add category scoring, SEO GEO AEO tools, and web workbench"
git -C $Repo push origin main
```

Robocopy exit codes 0 through 7 are successful or informational. Only 8 and above represent failure.

## Enable GitHub Pages

After pushing:

1. Open the repository on GitHub.
2. Select **Settings**.
3. Select **Pages** under Code and automation.
4. Set **Source** to **GitHub Actions**.
5. Open **Actions** and run **Deploy graphical workbench to GitHub Pages**, or push another change under `docs/`.

Expected URL:

```text
https://foulfoxhacks.github.io/SEO-INDEX-VariScripts/
```

## Verify after publishing

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 | iex
seo-index --no-splash list-engines
seo-index web --print-only
seo-index redirect --url https://example.com
```
