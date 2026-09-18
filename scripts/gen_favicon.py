#!/usr/bin/env python3
"""
Generate favicons and the Open Graph card from the brand name.

No logo file is required: the favicon is the first letter of SITE_NAME set in
the site's display font on the near-black ground, and the OG card is the full
site name plus tagline. Re-run after changing the brand in .env.

Outputs into app/static/:
    favicon-16.png, favicon-32.png, favicon.ico, apple-touch-icon.png,
    img/og-default.png

Usage:
    pip install Pillow
    python scripts/gen_favicon.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, ROOT)
from app import branding  # noqa: E402

BG = (7, 8, 9)            # --bg-body #070809
FG = (235, 238, 241)      # --text-primary
ACCENT = (41, 171, 226)   # --accent #29ABE2

STATIC = os.path.join(ROOT, 'app', 'static')
FONT = os.path.join(STATIC, 'fonts', 'DejaVuSans-Bold.ttf')


def glyph(size):
    img = Image.new('RGBA', (size, size), BG)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(size * 0.72))
    letter = branding.SITE_NAME.strip()[:1].upper() or 'C'
    box = draw.textbbox((0, 0), letter, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), letter, font=font, fill=ACCENT)
    return img


def og_card():
    img = Image.new('RGB', (1200, 630), BG)
    draw = ImageDraw.Draw(img)
    name_font = ImageFont.truetype(FONT, 96)
    tag_font = ImageFont.truetype(FONT, 30)
    name = branding.SITE_NAME.upper()
    box = draw.textbbox((0, 0), name, font=name_font)
    draw.text(((1200 - (box[2] - box[0])) / 2 - box[0], 230 - box[1]), name, font=name_font, fill=FG)
    tag = branding.SITE_TAGLINE
    box = draw.textbbox((0, 0), tag, font=tag_font)
    draw.text(((1200 - (box[2] - box[0])) / 2 - box[0], 370 - box[1]), tag, font=tag_font, fill=(138, 148, 157))
    draw.rectangle([560, 330, 640, 332], fill=ACCENT)
    return img


def main():
    for size, name in ((16, 'favicon-16.png'), (32, 'favicon-32.png'), (180, 'apple-touch-icon.png')):
        glyph(size).save(os.path.join(STATIC, name))
    glyph(64).save(os.path.join(STATIC, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)])
    og_card().save(os.path.join(STATIC, 'img', 'og-default.png'))
    print('favicons + og-default.png written for', branding.SITE_NAME)


if __name__ == '__main__':
    main()
