from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw

SIZE = 1024
SSAA = 3

NAVY_TOP = (36, 81, 138)
NAVY_BOTTOM = (18, 41, 74)
BLUE = (61, 139, 224)
WHITE = (255, 255, 255)
GREEN = (105, 213, 164)

ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def vertical_gradient(height, top, bottom):
    gradient = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(1, height - 1)
        gradient.putpixel((0, y), tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return gradient.resize((height, height), Image.Resampling.BILINEAR)


def draw_arrowhead(draw, center, radius, angle_deg, tangent_len, width, color):
    angle = math.radians(angle_deg)
    px = center[0] + radius * math.cos(angle)
    py = center[1] + radius * math.sin(angle)
    tangent = (-math.sin(angle), math.cos(angle))
    normal = (math.cos(angle), math.sin(angle))
    tip = (px + tangent[0] * tangent_len, py + tangent[1] * tangent_len)
    base1 = (px - normal[0] * width / 2, py - normal[1] * width / 2)
    base2 = (px + normal[0] * width / 2, py + normal[1] * width / 2)
    draw.polygon([tip, base1, base2], fill=color)


def build_master():
    canvas = SIZE * SSAA
    scale = canvas / 1024.0

    def s(value):
        return value * scale

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    inset = s(30)
    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [inset, inset, canvas - inset - 1, canvas - inset - 1], radius=s(210), fill=255)
    gradient = vertical_gradient(canvas, NAVY_TOP, NAVY_BOTTOM).convert("RGBA")
    image.paste(gradient, (0, 0), mask)

    draw = ImageDraw.Draw(image)
    center = (canvas / 2.0, canvas / 2.0)

    arc_radius = s(332)
    arc_box = [center[0] - arc_radius, center[1] - arc_radius, center[0] + arc_radius, center[1] + arc_radius]
    draw.arc(arc_box, start=158, end=342, fill=BLUE, width=int(s(76)))
    draw_arrowhead(draw, center, arc_radius, 342, tangent_len=s(126), width=s(176), color=BLUE)

    ring_radius = s(238)
    ring_width = int(s(80))
    ring_box = [center[0] - ring_radius, center[1] - ring_radius, center[0] + ring_radius, center[1] + ring_radius]
    draw.ellipse(ring_box, outline=WHITE, width=ring_width)

    hand_width = int(s(66))
    minute_end = (center[0], center[1] - s(152))
    hour_angle = math.radians(210)
    hour_end = (center[0] + s(104) * math.cos(hour_angle), center[1] + s(104) * math.sin(hour_angle))
    for end in (minute_end, hour_end):
        draw.line([center, end], fill=WHITE, width=hand_width)
        radius = hand_width / 2.0
        draw.ellipse([end[0] - radius, end[1] - radius, end[0] + radius, end[1] + radius], fill=WHITE)

    hub = s(42)
    draw.ellipse([center[0] - hub, center[1] - hub, center[0] + hub, center[1] + hub], fill=GREEN)

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    master = build_master()

    master.save(os.path.join(base, "ASCOS-TimeShift.png"), format="PNG")
    master.resize((128, 128), Image.Resampling.LANCZOS).save(
        os.path.join(base, "ASCOS-TimeShift-128.png"), format="PNG")
    master.resize((52, 52), Image.Resampling.LANCZOS).save(
        os.path.join(base, "ASCOS-TimeShift-52.png"), format="PNG")
    master.save(os.path.join(base, "ASCOS-TimeShift.ico"), format="ICO", sizes=[
        (size, size) for size in ICON_SIZES])
    print("Ikonlar olusturuldu:", base)


if __name__ == "__main__":
    main()
