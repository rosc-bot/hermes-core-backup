# Mihomo/Clash Common Syntax Pitfalls & Anchor Errors

## 1. `yaml: unknown anchor 'XXX' referenced`
This is a fatal parse error that will cause the Mihomo/Clash core to crash entirely on startup.
It occurs when a YAML anchor alias (e.g., `<<: *proxy_fp` or `<<: *TG_Use`) is referenced later in the document, but the original anchor definition has been removed or was stripped by a tool.

### Prevention & Fix
If you delete an anchor definition, you **MUST** also search the rest of the configuration file and remove every `<<: *anchor_name` line that references it. A partial deletion breaks the YAML structure.

---

## 2. SurfingTile Automatic Override & Custom Anchor Stripping Pitfalls

In Android root environments using **SurfingTile** (e.g. Magisk / KernelSU Box for Magisk / Box-bll):

### A. Missing `proxy_fp` Anchor Injection Trap
- **Mechanism**: When TLS fingerprint / client fingerprint is enabled in the SurfingTile Android app preferences (`ClashConfigPrefs.xml`), SurfingTile automatically injects `<<: *proxy_fp` under `override:` for every subscription in `proxy-providers` when generating/saving configs.
- **Symptom**: If the user's `config.yaml` does not pre-define `proxy_fp: &proxy_fp`, saving the configuration in the module will immediately fail pre-validation:
  ```text
  level=error msg="yaml: unknown anchor 'proxy_fp' referenced"
  configuration file /data/adb/box_bll/clash/config.yaml test failed
  [Error]: 配置预校验失败，请检查 /data/adb/box_bll/run/check.log 中的语法错误.
  ```
- **Diagnostics Paths**:
  - Pre-validation error log: `/data/adb/box_bll/run/check.log`
  - Module startup log: `/data/adb/box_bll/run/run.log`
- **Fix**:
  1. Add the anchor definition explicitly near the top of `config.yaml`:
     ```yaml
     proxy_fp: &proxy_fp
       client-fingerprint: chrome
     ```
  2. Or disable client fingerprint in SurfingTile app settings and clean up `proxy_fp` in `/data/user/0/com.surfing.tile/shared_prefs/ClashConfigPrefs.xml`.

### B. Custom Anchor Stripping When Adding Subscriptions in UI (`Unknown anchor 'XXX' referenced`)
- **Mechanism**: When a user adds/edits subscriptions through the **SurfingTile App UI**, the app's config generator reconstructs the top of the file, recognizing ONLY standard module anchors (`&p`, `&proxy_fp`, `&A`, `&All`). It **silently wipes out any custom user-defined anchors** (e.g., `TG_Use: &TG_Use`). However, the references (`<<: *TG_Use`) remain in `proxy-groups`, crashing Mihomo with `Unknown anchor 'TG_Use' referenced`.
- **Golden Rule**: **NEVER define custom anchors for SurfingTile configs.**
  Instead, use **INLINE properties** directly inside specific proxy groups:
  ```yaml
  - name: Telegram
    type: select
    proxies:
      - TG·延迟最低
      - ALL·香港地区
      - ALL·狮城地区
      - 🌐 本机·本地直连
    use:
      - "星河"
      - "聚合"
      - "顺畅"
    filter: "^(?!.*(CF|cf|Cloudflare|cloudflare|套餐|重置|剩余|到期|订阅|群|账户|流量|有效期|时间|官网|失联|余额)).*$"
  ```

---

## 3. Provider Inclusion Gotcha: Why Newly Added Subscriptions Don't Show in Proxy Groups
Adding a subscription to `proxy-providers:` only downloads it into the local provider cache.
For nodes from a new subscription (e.g., `"大机场"`) to actually appear inside policy groups (`总模式`, `ALL·延迟最低`, `ALL·香港地区`, `Telegram`):
The subscription's key name **MUST be explicitly added to the `use:` list** of the groups (or anchors `A: &A` and `All: &All`):
```yaml
A: &A
  use:
    - "CF"
    - "星河"
    - "聚合"
    - "顺畅"
    - "大机场"   # 👈 MUST explicitly add here!
```

---

## 4. Invalid Parameters in `health-check` vs `url-test`
Mihomo handles automatic node selection and health-checking in two separate blocks. Mixing up their parameters is a common mistake that clutters logs or breaks logic.

**WRONG**: Placing switching logic in health-check
```yaml
health-check:
  enable: true
  url: https://www.gstatic.com/generate_204
  interval: 300
  lazy: true          # ILLEGAL HERE
  tolerance: 200      # ILLEGAL HERE
  max-failed-times: 3 # ILLEGAL HERE
```

**CORRECT**: `lazy`, `tolerance`, and `max-failed-times` belong directly under the strategy group definition (`type: url-test`, `type: fallback`, or `type: load-balance`).
```yaml
- name: ALL·延迟最低
  type: url-test
  tolerance: 200
  lazy: true
  interval: 1800
  timeout: 3000
  max-failed-times: 3
  url: 'https://www.gstatic.com/generate_204'
  proxies:
    - NodeA
    - NodeB
```

---

## 5. Go `http.Header` Schema Gotcha: `'header[XXX]' is not a slice`
In Mihomo (Go), `proxy-provider`'s `header` field maps directly to Go's `http.Header` structure, defined as `map[string][]string`.
Every header key's value **MUST** be a list/slice of strings (`[]string`), never a scalar string.

### Error Symptom:
```text
parse proxy provider CF error: 'header[User-Agent]' is not a slice
configuration file /data/adb/box_bll/clash/config.yaml test failed
```

### WRONG (Scalar string):
```yaml
header:
  User-Agent: "Mihomo"
```

### CORRECT (YAML list/slice format):
```yaml
header:
  User-Agent:
    - "Mihomo"
    - "clash-verge/v2.2.3"
```
or inline list:
```yaml
header:
  User-Agent: ["Mihomo"]
```
