# -*- coding: utf-8 -*-
"""Skapar ikon_start.ico (gron kurva-upp) och ikon_stopp.ico (rod kvadrat).
Kors en gang av skapa_genvagar.bat."""
from PIL import Image, ImageDraw

STL = [(16, 16), (32, 32), (48, 48), (256, 256)]


def bas(farg_bg):
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([8, 8, 248, 248], radius=48, fill=farg_bg)
    return im, d


def start_ikon():
    im, d = bas((15, 20, 32, 255))
    # staplar
    for i, (x, h) in enumerate([(48, 70), (98, 110), (148, 90), (198, 150)]):
        d.rectangle([x, 216 - h, x + 34, 216], fill=(61, 220, 132, 255))
    # pil upp
    d.line([(40, 150), (110, 100), (150, 125), (225, 55)],
           fill=(255, 255, 255, 255), width=14, joint="curve")
    d.polygon([(225, 55), (185, 55), (225, 100)], fill=(255, 255, 255, 255))
    im.save("ikon_start.ico", sizes=STL)


def stopp_ikon():
    im, d = bas((40, 16, 22, 255))
    d.rounded_rectangle([78, 78, 178, 178], radius=14, fill=(255, 90, 90, 255))
    im.save("ikon_stopp.ico", sizes=STL)


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    start_ikon()
    stopp_ikon()
    print("ikoner skapade")
