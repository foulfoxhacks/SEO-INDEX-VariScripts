# Deploy webtools.mellozone.site with GitHub Pages

## DNS record

In Vercel DNS for `mellozone.site`, remove the current record:

- Type: `CNAME`
- Name: `webtools`
- Value: the existing Vercel-generated target such as `d681...`

Create this replacement:

- Type: `CNAME`
- Name: `webtools`
- Value: `foulfoxhacks.github.io`
- TTL: default / 60 seconds

Do not add an A or AAAA record for `webtools` when using this CNAME.

## GitHub Pages settings

Repository: `foulfoxhacks/SEO-INDEX-VariScripts`

1. Open Settings > Pages.
2. Use GitHub Actions as the source.
3. Set the custom domain to `webtools.mellozone.site`.
4. Wait for DNS validation and certificate issuance.
5. Enable Enforce HTTPS when the checkbox becomes available.

The `docs/CNAME` file contains `webtools.mellozone.site` so branch-based deployments and local repository state preserve the custom-domain declaration. The included GitHub Actions deployment also publishes the `docs` directory.

## Verify from Windows

```powershell
Resolve-DnsName webtools.mellozone.site -Type CNAME
curl.exe -I https://webtools.mellozone.site/
```

Expected DNS target:

```text
foulfoxhacks.github.io
```

The certificate can take time to issue after the DNS record resolves correctly.

## HTTPS notes

The page uses relative local assets and contains no HTTP asset references. A Content Security Policy meta tag upgrades insecure requests and restricts scripts, styles, images, forms, and network connections to the site itself.

GitHub Pages controls TLS and response headers. The repository cannot directly add HSTS or other custom HTTP response headers on GitHub Pages. Enable GitHub's Enforce HTTPS option after certificate issuance.
