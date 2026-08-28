import os
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def render_cover(bg_path, output_path, badge_text, main_title, sub_title, pill_bg_color=(18, 138, 245)):
    TARGET_W, TARGET_H = 3840, 2160
    im = Image.open(bg_path).convert('RGBA')
    src_w, src_h = im.size
    scale = max(TARGET_W / src_w, TARGET_H / src_h)
    new_w, new_h = int(src_w * scale), int(src_h * scale)
    im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - TARGET_W) // 2
    top = (new_h - TARGET_H) // 2
    im = im.crop((left, top, left + TARGET_W, top + TARGET_H))

    gradient = Image.new('RGBA', (TARGET_W, TARGET_H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(gradient)
    for y in range(int(TARGET_H * 0.42), TARGET_H):
        p_y = (y - int(TARGET_H * 0.42)) / (TARGET_H * 0.58)
        alpha = int(230 * (p_y ** 1.9))
        for x in range(0, int(TARGET_W * 0.65), 10):
            p_x = x / (TARGET_W * 0.65)
            x_factor = max(0.0, 1.0 - (p_x ** 1.3))
            cur_alpha = int(alpha * x_factor)
            if cur_alpha > 0:
                gdraw.rectangle([x, y, x + 10, y + 1], fill=(4, 8, 16, cur_alpha))

    gradient = gradient.filter(ImageFilter.GaussianBlur(radius=35))
    im = Image.alpha_composite(im, gradient)
    draw = ImageDraw.Draw(im)

    font_serif_path = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
    font_sans_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
    
    font_badge = ImageFont.truetype(font_sans_path, size=48, index=0)
    font_title = ImageFont.truetype(font_serif_path, size=240, index=0)
    font_sub = ImageFont.truetype(font_sans_path, size=54, index=0)

    MARGIN_LEFT = 220
    BASE_Y = 1460

    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 44, 18
    pill_w, pill_h = tw + pad_x * 2 + 10, th + pad_y * 2 + 6
    pill_x0, pill_y0 = MARGIN_LEFT, BASE_Y
    pill_x1, pill_y1 = pill_x0 + pill_w, pill_y0 + pill_h
    radius = pill_h // 2

    pill_layer = Image.new('RGBA', (TARGET_W, TARGET_H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill_layer)
    pdraw.rounded_rectangle([pill_x0 - 3, pill_y0 - 3, pill_x1 + 3, pill_y1 + 3], radius=radius + 3, fill=(*pill_bg_color, 80))
    pdraw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y1], radius=radius, fill=(*pill_bg_color, 235))
    im = Image.alpha_composite(im, pill_layer)
    draw = ImageDraw.Draw(im)

    draw.text((pill_x0 + pad_x + 5, pill_y0 + pad_y - 2), badge_text, fill=(255, 255, 255, 255), font=font_badge)

    title_y = pill_y1 + 50
    title_x = MARGIN_LEFT - 8
    for ox, oy, sa in [(0, 8, 180), (4, 12, 140), (8, 16, 90)]:
        draw.text((title_x + ox, title_y + oy), main_title, fill=(0, 0, 0, sa), font=font_title)
    draw.text((title_x, title_y), main_title, fill=(255, 255, 255, 255), font=font_title)

    t_bbox = draw.textbbox((0, 0), main_title, font=font_title)
    t_h = t_bbox[3] - t_bbox[1]
    sub_y = title_y + t_h + 80

    cur_x = title_x + 6
    letter_spacing = 16
    for char in sub_title:
        draw.text((cur_x + 3, sub_y + 4), char, fill=(0, 0, 0, 180), font=font_sub)
        draw.text((cur_x, sub_y), char, fill=(215, 228, 245, 255), font=font_sub)
        cur_x += draw.textlength(char, font=font_sub) + letter_spacing

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final_rgb = im.convert('RGB')
    final_rgb.save(output_path, quality=96)
    web_path = output_path.replace('.jpg', '_1080p.jpg')
    final_rgb.resize((1920, 1080), Image.Resampling.LANCZOS).save(web_path, quality=94)
    print(f"Master saved: {output_path}")
    print(f"Web 1080p saved: {web_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Render 16:9 Media Library Covers")
    parser.add_argument("--bg", required=True, help="Background image path")
    parser.add_argument("--out", required=True, help="Output jpg path")
    parser.add_argument("--badge", required=True, help="Pill badge text")
    parser.add_argument("--title", required=True, help="Main Chinese title")
    parser.add_argument("--sub", required=True, help="English subtitle")
    args = parser.parse_args()
    render_cover(args.bg, args.out, args.badge, args.title, args.sub)
