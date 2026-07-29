# Repository upload guide

The files in this package are arranged to drop directly into the root of:

`foulfoxhacks/SEO-INDEX-VariScripts`

## Upload order

1. Upload `Config`, `Win`, `MacOS`, `Py+Linux`, and `Tests` while preserving paths.
2. Upload the root launchers and installers: `seo-index`, `seo-index.cmd`, `install.ps1`, and `install.sh`.
3. Replace `README.md` and `CHANGELOG.md` with the included versions.
4. Keep the repository's existing `LICENSE` unless you intentionally choose a different license.
5. Commit with a message such as `feat: add interactive SEO index toolkit and engine scores`.

## Verify after upload

```bash
python3 -m py_compile './Py+Linux/Scripts/seo_index_toolkit.py'
python3 ./Tests/test_toolkit.py
./seo-index --no-splash list-engines
```

On Windows:

```powershell
.\Win\Start-SEOIndexToolkit.ps1 --no-splash list-engines
```

The public installation one-liners in the README begin working after `install.ps1` and `install.sh` are present on the `main` branch.
