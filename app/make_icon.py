"""Draws the PolySweeper icon (build machine only; needs Pillow): python app/make_icon.py out.ico"""
import sys
from PIL import Image, ImageDraw

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((8, 8, S - 8, S - 8), radius=52, fill=(14, 19, 24, 255), outline=(40, 51, 66, 255), width=6)
# a rising line of small wins with one check mark: "many small sure wins"
pts = [(44, 186), (84, 160), (118, 168), (152, 128), (184, 120), (214, 74)]
d.line(pts, fill=(63, 185, 80, 255), width=14, joint="curve")
for x, y in pts:
    d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(63, 185, 80, 255))
d.line([(150, 206), (172, 226), (214, 176)], fill=(88, 166, 255, 255), width=16, joint="curve")
img.save(sys.argv[1] if len(sys.argv) > 1 else "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
