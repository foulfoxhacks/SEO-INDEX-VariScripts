# Repository release guide

Use a feature branch and pull request so the cross-platform CI matrix can validate the release before it reaches `main`.

## 1. Verify locally

```powershell
python -m compileall -q "Py+Linux\Scripts" "Py+Linux\seo_index_toolkit.py"
python -m unittest discover -s Tests -p "test*.py" -v
node --check docs\assets\app.js
python -m json.tool docs\matrix.json | Out-Null
python -m json.tool Config\engine_profiles.json | Out-Null
```

On Linux or macOS, also validate executable scripts:

```bash
bash -n ./seo-index ./install.sh ./Py+Linux/*.sh ./Py+Linux/Scripts/*.sh ./MacOS/*.command
```

## 2. Prepare a release branch

```powershell
git switch -c release/v1.4.0
git add .
git update-index --chmod=+x -- `
  "seo-index" `
  "install.sh" `
  "MacOS/*.command" `
  "Py+Linux/*.sh" `
  "Py+Linux/Scripts/*.sh"
git diff --cached --check
git commit -m "feat: release SEO-INDEX VariScripts v1.4.0"
git push -u origin release/v1.4.0
```

Open a pull request, wait for **Test toolkit** and **Deploy graphical workbench to GitHub Pages** validation where applicable, then merge through the repository's normal review policy.

## 3. GitHub Pages

Repository settings should use **GitHub Actions** as the Pages source. The deployment workflow publishes only `docs/` and runs automatically for relevant changes on `main`.

Configured custom domain:

```text
https://webtools.mellozone.site/
```

Project-site fallback:

```text
https://foulfoxhacks.github.io/SEO-INDEX-VariScripts/
```

## 4. Post-release smoke test

```powershell
irm https://raw.githubusercontent.com/foulfoxhacks/SEO-INDEX-VariScripts/main/install.ps1 | iex
seo-index --version
seo-index --no-splash list-engines
seo-index page --url https://example.com --fail-on never
seo-index web --print-only
```
