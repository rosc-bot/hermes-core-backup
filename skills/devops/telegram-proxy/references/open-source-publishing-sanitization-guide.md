# Open-Source Publishing & Privacy Sanitization Protocol

When publishing, packaging, or uploading a local tool, reverse proxy script, or web service to a public GitHub repository (e.g. via `git push` or `curl | bash` installer), strictly follow this sanitization checklist to prevent private endpoint leaks.

---

## 1. Zero-Leak Sanitization Checklist

Before committing or packaging into `.zip` or pushing to public remotes:
1. **Never Hardcode Real Backend URLs**:
   - Replace private Emby server endpoints (e.g. `c.emby.wtf`, `m.wenjian.de`, `myserver.net`) with generic domain placeholders (`https://emby1.example.com`, `https://emby2.example.com`).
2. **Never Hardcode Real VPS Public IPs**:
   - Strip all specific host server IP addresses (e.g. `199.47.241.137`) and use `127.0.0.1` or `YOUR_SERVER_IP`.
3. **Redact Custom Node / Server Names**:
   - Replace user-specific names like \"终点站\", \"稳健\" with standard \"Emby Server 1 (Demo)\", \"Emby Server 2 (Demo)\".
4. **Scrub Default Config Files & Datastores**:
   - Ensure initial `sites.json`, `config.json`, or `.env` files start either empty or containing only mock dummy examples.
5. **Clean Installation Scripts (`install.sh`)**:
   - Do not embed user-specific tokens, personal Telegram IDs, or pre-filled node routing links in quick-install bash wrappers.

---

## 2. Accidental Leak Remediation & Clean Git History Rewrite

If private endpoints or IPs were accidentally committed and pushed:
1. **Do NOT just push a new commit**:
   - Simple subsequent commits still leave the private URLs and credentials visible in git commit history and diffs.
2. **Amend & Force-Overwrite Git Root Commit**:
   ```bash
   # Clean the files
   python3 -c "
   for path in ['panel.py', 'README.md']:
       with open(path) as f:
           content = f.read()
       # Replace private domains with example.com
       ...
       with open(path, 'w') as f:
           f.write(content)
   "
   
   # Overwrite the commit and force push
   git add .
   git commit --amend -m "feat: Initial commit (Clean Template)"
   git push origin main --force
   ```
3. **Verify Remote Raw Content**:
   - Always verify with `curl -s https://raw.githubusercontent.com/<user>/<repo>/main/<file>` to ensure the sanitization completely wiped the target strings from the live CDN cache.
