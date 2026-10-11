#!/usr/bin/env python3
"""Generate the three project diagrams with PIL."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(OUT, exist_ok=True)

FB = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

BG = (245, 247, 250)
INK = (30, 30, 30)
ACCENT = (0, 119, 181)       # blue
ACCENT2 = (46, 125, 50)      # green
WARN = (198, 40, 40)         # red
BOX = (255, 255, 255)
LINE = (90, 90, 90)


def font(path, size):
    return ImageFont.truetype(path, size)


def box(d, xy, fill=BOX, outline=ACCENT, width=3, radius=14):
    d.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def centered(d, cx, y, text, fnt, fill=INK):
    bb = d.textbbox((0, 0), text, font=fnt)
    d.text((cx - (bb[2] - bb[0]) / 2, y), text, font=fnt, fill=fill)


def arrow(d, x1, y1, x2, y2, color=LINE, width=3):
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    # arrowhead
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    s = 12
    for a in (ang + 2.6, ang - 2.6):
        d.line([(x2, y2), (x2 + s * math.cos(a), y2 + s * math.sin(a))],
               fill=color, width=width)


def title_block(d, W, text):
    f = font(FB, 44)
    centered(d, W // 2, 28, text, f, ACCENT)


# ---------------------------------------------------------------- architecture
def architecture():
    W, H = 1600, 1000
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title_block(d, W, "Architecture — RKB Restaurant Order System")
    fb, fr, fs = font(FB, 30), font(FR, 24), font(FR, 20)

    # client row
    clients = [("Waiter\n(browser / POS)", 200), ("Kitchen\n(display)", 800),
               ("Customer care\n(desk)", 1400)]
    for label, cx in clients:
        box(d, [cx - 190, 130, cx + 190, 260])
        for i, line in enumerate(label.split("\n")):
            centered(d, cx, 155 + i * 44, line, fb if i == 0 else fr)
    centered(d, 800, 290, "HTTP / JSON (REST)", fs, LINE)
    for cx in (200, 800, 1400):
        arrow(d, cx, 262, cx, 330)

    # FastAPI row
    box(d, [300, 340, 1300, 500], outline=ACCENT2)
    centered(d, 800, 360, "FastAPI application", fb)
    apis = ["menu / tables", "orders", "kitchen", "customer-care", "dashboard"]
    for i, a in enumerate(apis):
        x = 390 + i * 185
        box(d, [x, 415, x + 160, 475], outline=LINE, width=2)
        centered(d, x + 80, 432, a, fs)

    arrow(d, 800, 502, 800, 552)
    centered(d, 800, 512, "service calls", fs, LINE)

    # services row
    box(d, [300, 560, 1300, 680], outline=ACCENT)
    centered(d, 800, 578, "Services (business logic)", fb)
    for i, s in enumerate(["order state machine", "delay detector", "polite notifier"]):
        x = 400 + i * 285
        box(d, [x, 622, x + 250, 662], outline=LINE, width=2)
        centered(d, x + 125, 632, s, fs)

    arrow(d, 800, 682, 800, 732)
    centered(d, 800, 692, "explicit SQL strings", fs, LINE)

    # db.py row
    box(d, [450, 740, 1150, 830], fill=(232, 240, 248), outline=ACCENT)
    centered(d, 800, 758, "app/db/db.py — raw SQL layer (no ORM)", fb, ACCENT)
    centered(d, 800, 796, "? placeholders → %s for psycopg2", fs, LINE)

    arrow(d, 620, 832, 620, 880)
    arrow(d, 980, 832, 980, 880)
    box(d, [420, 885, 780, 965], outline=ACCENT2)
    centered(d, 600, 905, "SQLite (dev / tests)", fb)
    box(d, [820, 885, 1180, 965], outline=ACCENT2)
    centered(d, 1000, 905, "PostgreSQL (prod)", fb)

    img.save(os.path.join(OUT, "architecture.png"))


if __name__ == "__main__":
    architecture()
    print("architecture.png ok")
