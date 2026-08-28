---
name: short-video-extraction
description: "Extract Douyin/TikTok videos, image notes, and metadata."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Douyin, TikTok, Video, Scraping, Media, WAF, API]
    related_skills: [blocked-page-recovery, youtube-content]
---

# Short Video & Media Extraction

When fetching content from short-video and note platforms (such as Douyin / TikTok), direct HTML scraping (`curl`, `requests`) and standard CLI tools (`yt-dlp`) often fail on image notes or get challenged by JS anti-bot WAF (`window.WAFJS`, empty SSR payloads).

Instead of running heavyweight headless browsers, use the deterministic **API-First Token Pivot**: register a lightweight session token with the platform's union auth service, then query the official mobile/web JSON detail API.

## Douyin (抖音) / TikTok Note & Video Extraction

### Quick Python Workflow

```python
import requests
import json
import re

def extract_douyin_media(url_or_id: str) -> dict:
    """
    Extract Douyin note images, video streams, description, and author.
    Supports /share/note/, /share/video/, /note/, /video/, and raw item IDs.
    """
    match = re.search(r'(\d{15,25})', str(url_or_id))
    if not match:
        raise ValueError(f"No valid item ID found in {url_or_id}")
    item_id = match.group(1)

    session = requests.Session()

    # 1. Obtain valid ByteDance ttwid session cookie
    ttwid_payload = {
        "region": "cn",
        "aid": 1768,
        "needFid": "false",
        "service": "www.ixigua.com",
        "migrate_info": {"ticket": "", "source": "node"},
        "cbUrlProtocol": "https",
        "union": "true"
    }
    session.post("https://ttwid.bytedance.com/ttwid/union/register/", json=ttwid_payload, timeout=10)
    ttwid = session.cookies.get("ttwid")
    if not ttwid:
        raise RuntimeError("Failed to obtain ByteDance ttwid token")

    # 2. Query official web detail endpoint
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
        "Cookie": f"ttwid={ttwid};"
    }
    api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={item_id}&device_platform=webapp&aid=6383"
    resp = session.get(api_url, headers=headers, timeout=10)
    resp.raise_for_status()

    data = resp.json()
    detail = data.get("aweme_detail")
    if not detail:
        raise RuntimeError(f"No aweme_detail returned: {resp.text[:200]}")

    # 3. Parse fields
    desc = detail.get("desc", "")
    author = detail.get("author", {}).get("nickname", "")
    
    # Image notes (图文笔记)
    images = []
    for img in detail.get("images") or []:
        url_list = img.get("url_list") or []
        if url_list:
            images.append(url_list[0])

    # Video stream URLs
    video_urls = detail.get("video", {}).get("play_addr", {}).get("url_list") or []

    return {
        "item_id": item_id,
        "author": author,
        "desc": desc,
        "is_note": len(images) > 0,
        "images": images,
        "video_urls": video_urls,
        "raw": detail
    }
```

## Key Pitfalls & Tips
- **Note vs Video**: Douyin `/share/note/` posts store slides in `aweme_detail.images` instead of `video.play_addr`.
- **WAF Avoidance**: Do not rely on page SSR `window._ROUTER_DATA` or `window._SSR_DATA`, as they are frequently scrubbed or replaced by client-side hydrations.
- **Image Inspection**: Download the highest resolution image directly from CDN and pass to `vision_analyze` for OCR / visual scene understanding.
