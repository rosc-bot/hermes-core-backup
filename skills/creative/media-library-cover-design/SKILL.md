---
name: media-library-cover-design
description: "Use when designing Emby/Jellyfin/Plex media library covers."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Emby, Jellyfin, Plex, Infuse, Cover, Poster, Design, Pillow, Typography]
    related_skills: [claude-design, design-md]
---

# Media Library Cover Design (Emby / Jellyfin / Plex / Infuse)

When designing custom library category covers, banners, or hub posters for home theater media servers (Emby, Jellyfin, Plex, Apple TV Infuse), follow the 16:9 cinema-grade visual specification to ensure high legibility and luxury visual hierarchy across TVs, tablets, and web interfaces.

## 1. Design System & Typography Specifications

| Element | Specification | Recommended Font / Settings |
| :--- | :--- | :--- |
| **Canvas Ratio** | **16:9 Ultra HD** | Master: `3840x2160` (4K UHD); Web: `1920x1080` (1080P) |
| **Color Grading** | **Teal & Orange / Cinematic HDR** | High dynamic range, deep shadows, atmospheric rim lighting |
| **Shadow Gradient** | **Bottom-Left Vignette** | Multi-step radial + linear dark gradient (`rgba(4,8,16,alpha)`) to isolate text |
| **Quality Badge** | **Frosted Pill Badge** | Translucent vibrant ice blue (`rgb(18, 138, 245)` / `alpha: 235`) with rounded corners |
| **Main Title** | **Bold Modern Serif** | `Noto Serif CJK SC Bold` (思源宋体特粗), pure white with soft drop shadow |
| **Subtitle** | **Tracked Sans-Serif** | `Noto Sans CJK SC Bold` / `Liberation Sans Bold`, uppercase, letter tracking +16px |

## 2. Reusable Python Rendering Pipeline

```python
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def render_media_cover(
    bg_path: str,
    output_path: str,
    badge_text: str,
    main_title: str,
    sub_title: str,
    pill_color=(18, 138, 245),
    target_size=(3840, 2160)
):
    """
    Render a 16:9 cinema-grade media server category banner with dynamic contrast gradient.
    """
    target_w, target_h = target_size
    im = Image.open(bg_path).convert('RGBA')
    
    # 1. Aspect ratio crop (16:9)
    src_w, src_h = im.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    im = im.crop((left, top, left + target_w, top + target_h))

    # 2. Cinema Grade Left-Bottom Shadow Gradient Mask
    gradient = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    
    for y in range(int(target_h * 0.42), target_h):
        p_y = (y - int(target_h * 0.42)) / (target_h * 0.58)
        alpha = int(230 * (p_y ** 1.9))
        for x in range(0, int(target_w * 0.65), 10):
            p_x = x / (target_w * 0.65)
            x_factor = max(0.0, 1.0 - (p_x ** 1.3))
            cur_alpha = int(alpha * x_factor)
            if cur_alpha > 0:
                gdraw.rectangle([x, y, x + 10, y + 1], fill=(4, 8, 16, cur_alpha))

    gradient = gradient.filter(ImageFilter.GaussianBlur(radius=35))
    im = Image.alpha_composite(im, gradient)
    draw = ImageDraw.Draw(im)

    # 3. Fonts Setup (Linux / Ubuntu standard paths)
    font_serif_path = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
    font_sans_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
    
    font_badge = ImageFont.truetype(font_sans_path, size=48, index=0)
    font_title = ImageFont.truetype(font_serif_path, size=240, index=0)
    font_sub = ImageFont.truetype(font_sans_path, size=54, index=0)

    MARGIN_LEFT = int(target_w * 0.057) # ~220px on 3840
    BASE_Y = int(target_h * 0.675)     # ~1460px on 2160

    # 4. Pill Badge Rendering
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 44, 18
    pill_w, pill_h = tw + pad_x * 2 + 10, th + pad_y * 2 + 6
    pill_x0, pill_y0 = MARGIN_LEFT, BASE_Y
    pill_x1, pill_y1 = pill_x0 + pill_w, pill_y0 + pill_h
    radius = pill_h // 2

    pill_layer = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill_layer)
    pdraw.rounded_rectangle([pill_x0 - 3, pill_y0 - 3, pill_x1 + 3, pill_y1 + 3], radius=radius + 3, fill=(*pill_color, 80))
    pdraw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=radius, fill=(*pill_color, 235))
    im = Image.alpha_composite(im, pill_layer)
    draw = ImageDraw.Draw(im)

    draw.text((pill_x0 + pad_x + 5, pill_y0 + pad_y - 2), badge_text, fill=(255, 255, 255, 255), font=font_badge)

    # 5. Main Title (Chinese Serif with Multi-Layer Drop Shadow)
    title_y = pill_y1 + 50
    # Optical alignment fix: shift main title slightly left to visually align with the pill's rounded edge
    title_x = MARGIN_LEFT - 8 
    for ox, oy, sa in [(0, 8, 180), (4, 12, 140), (8, 16, 90)]:
        draw.text((title_x + ox, title_y + oy), main_title, fill=(0, 0, 0, sa), font=font_title)
    draw.text((title_x, title_y), main_title, fill=(255, 255, 255, 255), font=font_title)

    # 6. Subtitle (English Tracked)
    t_bbox = draw.textbbox((0, 0), main_title, font=font_title)
    t_h = t_bbox[3] - t_bbox[1]
    sub_y = title_y + t_h + 80

    cur_x = title_x + 6
    letter_spacing = 16
    for char in sub_title:
        draw.text((cur_x + 3, sub_y + 4), char, fill=(0, 0, 0, 180), font=font_sub)
        draw.text((cur_x, sub_y), char, fill=(215, 228, 245, 255), font=font_sub)
        cur_x += draw.textlength(char, font=font_sub) + letter_spacing

    # 7. Export Master & Web 1080P
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final_rgb = im.convert('RGB')
    final_rgb.save(output_path, quality=96)
    
    web_path = output_path.replace('.jpg', '_1080p.jpg')
    final_rgb.resize((1920, 1080), Image.Resampling.LANCZOS).save(web_path, quality=94)
```

## 3. Standard Library Categories & Background Sourcing Reference

| Chinese Category | English Subtitle | Quality Badge | Background Concept / Query |
| :--- | :--- | :--- | :--- |
| **追新电视剧** | `NEW TV SERIES & DRAMAS` | `4K ULTRA HD • ON AIR` | 暮色都市天际线、现代建筑霓虹、雨夜倒影 (`cinematic night city skyline neon`) |
| **追新动漫** | `NEW ANIME & ANIMATION` | `4K ULTRA HD • SIMULCAST` | 新海诚风水镜云海、夕阳晚霞、奇幻星空 (`anime scenery clouds sky`, `shinkai makoto`) |
| **追新电影** | `NEW MOVIES & CINEMA` | `4K ULTRA HD • CINEMA` | 深邃星际轨道、太空星云、电影院放映光束 (`cinematic space galaxy earth sci-fi`) |
| **纪录节目** | `DOCUMENTARY & DISCOVERY`| `4K ULTRA HD • CINEMA` | 史诗雪山峰顶刺破大气层、群山湖泊冰川 (`epic snow mountain peak earth horizon`) |
| **4K 臻彩原盘** | `4K REMUX • UHD COLLECTION` | `DOLBY VISION • ATMOS` | 黑金几何晶体、深色金属拉丝光泽 (`dark abstract black gold luxury crystal`) |
| **华语经典** | `CHINESE CLASSICS` | `MASTER RESTORED • 4K` | 复古九十年代胶片色调、经典港风霓虹街景 (`vintage 90s film aesthetic neon street`) |

### High-Res Asset Sourcing Tips
- **Wallhaven API (Curated Anime / 4K Wallpapers)**:
  `requests.get('https://wallhaven.cc/api/v1/search', params={'q': query, 'categories': '010', 'purity': '100', 'ratios': '16x9', 'sorting': 'favorites'})`
  - `categories='010'`: Anime only
  - `categories='100'`: General / Cinematic photography only
  - `categories='111'`: All categories
- **Ensure Anime Aesthetics**: When user asks for anime style, strictly use pure anime illustrated assets (`categories='010'`), featuring vibrant clouds, high contrast sky, or anime heroines/heroes with clean left-bottom dark areas.
