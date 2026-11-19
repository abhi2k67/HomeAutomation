"""Generate crisp 466x466 round-dial AMOLED assets for Minimal Trio (No-Photo Edition)."""

import math
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
DRAWABLE_DIR = ROOT / "res" / "drawable"
SIZE = 466
CENTER = SIZE / 2.0


def create_eclipse_ring() -> Image.Image:
    """Style 1: Pure-black dial with subtle circular orbital track & cardinal pips."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer orbital track (radius 214px, safely inside 233px round bezel)
    r = 214
    bbox = [CENTER - r, CENTER - r, CENTER + r, CENTER + r]
    draw.ellipse(bbox, outline=(212, 175, 106, 48), width=2)

    # Subtle 12/3/6/9 cardinal hairline ticks
    for deg in (0, 90, 180, 270):
        rad = math.radians(deg - 90)
        x1 = CENTER + (r - 6) * math.cos(rad)
        y1 = CENTER + (r - 6) * math.sin(rad)
        x2 = CENTER + (r + 4) * math.cos(rad)
        y2 = CENTER + (r + 4) * math.sin(rad)
        color = (212, 175, 106, 170) if deg == 0 else (242, 239, 233, 95)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)

    return img


def create_braun_ticks() -> Image.Image:
    """Style 2: 60 precision radial chronograph ticks around the 466x466 circle."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r_outer = 224
    for i in range(60):
        rad = math.radians(i * 6 - 90)
        is_hour = (i % 5 == 0)
        r_inner = 208 if is_hour else 217
        width = 2 if is_hour else 1

        if i == 0:
            # 12 o'clock warm-amber Braun/Leica accent
            color = (224, 110, 56, 230)
        elif is_hour:
            color = (170, 170, 170, 175)
        else:
            color = (90, 90, 90, 115)

        x1 = CENTER + r_inner * math.cos(rad)
        y1 = CENTER + r_inner * math.sin(rad)
        x2 = CENTER + r_outer * math.cos(rad)
        y2 = CENTER + r_outer * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

    # Subtle inner instrument ring
    r_sub = 196
    draw.ellipse(
        [CENTER - r_sub, CENTER - r_sub, CENTER + r_sub, CENTER + r_sub],
        outline=(255, 255, 255, 22),
        width=1,
    )
    return img


def create_kinetic_glint() -> Image.Image:
    """Style 3: Subtle brushed-titanium diagonal specular sheen for gyro parallax."""
    # Oversized 520x520 so shifting +/-18px never exposes hard edges
    s = 520
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    px = img.load()
    c = s / 2.0

    for y in range(s):
        for x in range(s):
            # Soft diagonal light band + radial falloff
            dx = (x - c) / c
            dy = (y - c) / c
            dist = math.hypot(dx, dy)
            if dist > 0.92:
                continue
            band = math.exp(-((dx * 0.75 + dy * 0.65) ** 2) / 0.14)
            falloff = max(0.0, 1.0 - (dist / 0.92) ** 2)
            alpha = int(42 * band * falloff)
            px[x, y] = (225, 205, 165, alpha)

    return img


def create_preview(eclipse: Image.Image) -> Image.Image:
    """Create a 466x466 round watch face picker preview."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    img.alpha_composite(eclipse)
    draw = ImageDraw.Draw(img)
    # Minimalist preview ring indicator
    r = 214
    draw.arc([CENTER - r, CENTER - r, CENTER + r, CENTER + r], start=-90, end=45, fill=(212, 175, 106, 220), width=3)
    return img


def main() -> None:
    DRAWABLE_DIR.mkdir(parents=True, exist_ok=True)
    eclipse = create_eclipse_ring()
    eclipse.save(DRAWABLE_DIR / "dial_eclipse_ring.png")
    create_braun_ticks().save(DRAWABLE_DIR / "dial_braun_ticks.png")
    create_kinetic_glint().save(DRAWABLE_DIR / "dial_kinetic_glint.png")
    create_preview(eclipse).save(DRAWABLE_DIR / "preview_trio.png")
    print(f"Generated 466x466 round AMOLED assets in {DRAWABLE_DIR}")


if __name__ == "__main__":
    main()
