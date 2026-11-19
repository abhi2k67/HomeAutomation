"""Generate Day (E-Ink Architectural Paper) and Night (Obsidian Terminal) technical wallpapers."""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
DRAWABLE_DIR = ROOT / "res" / "drawable-nodpi"
WALLPAPER_EXPORT_DIR = ROOT / "wallpapers"


def draw_technical_grid_and_astrolabe(
    img: Image.Image,
    grid_color: tuple[int, int, int],
    ring_color: tuple[int, int, int],
    accent_color: tuple[int, int, int],
    is_lockscreen: bool = False,
) -> None:
    """Draw subtle orthographic CAD grid and concentric horological caliper rings (zero stars)."""
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Subtle 60px technical grid
    step = 60
    for x in range(0, w, step):
        draw.line([(x, 0), (x, h)], fill=grid_color, width=1)
    for y in range(0, h, step):
        draw.line([(0, y), (w, y)], fill=grid_color, width=1)

    # Small crosshair markers '+' at major grid intersections
    for x in range(120, w, 240):
        for y in range(180, h, 360):
            draw.line([(x - 5, y), (x + 5, y)], fill=ring_color, width=1)
            draw.line([(x, y - 5), (x, y + 5)], fill=ring_color, width=1)

    if is_lockscreen:
        # Lock Screen: Center Horological Astrolabe (from Video 00:00) + Lower Geodesic Wireframe Sphere
        cx, cy = w // 2, int(h * 0.44)
        for r in (260, 320, 380):
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ring_color, width=2)
        for deg in range(0, 360, 6):
            rad = math.radians(deg)
            r0 = 366 if (deg % 30 == 0) else 373
            r1 = 380
            x0, y0 = cx + int(r0 * math.cos(rad)), cy + int(r0 * math.sin(rad))
            x1, y1 = cx + int(r1 * math.cos(rad)), cy + int(r1 * math.sin(rad))
            draw.line([(x0, y0), (x1, y1)], fill=accent_color if (deg % 30 == 0) else ring_color, width=2 if (deg % 30 == 0) else 1)

        # Lower wireframe geodesic sphere projection
        scx, scy, sr = w // 2, int(h * 0.76), 140
        draw.ellipse((scx - sr, scy - sr, scx + sr, scy + sr), outline=ring_color, width=2)
        for frac in (0.35, 0.68):
            rx = int(sr * frac)
            draw.ellipse((scx - rx, scy - sr, scx + rx, scy + sr), outline=ring_color, width=1)
            ry = int(sr * frac)
            draw.ellipse((scx - sr, scy - ry, scx + sr, scy + ry), outline=ring_color, width=1)


def make_day_eink_wallpaper(width: int = 1080, height: int = 2400, is_lock: bool = False) -> Image.Image:
    """Video 00:02-00:03: Warm E-Ink Architectural Drafting Paper (#E6E5E0)."""
    img = Image.new("RGB", (width, height), (230, 229, 224))
    draw_technical_grid_and_astrolabe(
        img,
        grid_color=(216, 215, 209),
        ring_color=(188, 187, 180),
        accent_color=(120, 120, 115),
        is_lockscreen=is_lock,
    )
    return img


def make_night_obsidian_wallpaper(width: int = 1080, height: int = 2400, is_lock: bool = False) -> Image.Image:
    """Video 00:07-00:09: Pure Obsidian Terminal (#050608) with ultra-subtle CAD hairlines."""
    img = Image.new("RGB", (width, height), (5, 6, 8))
    draw_technical_grid_and_astrolabe(
        img,
        grid_color=(13, 15, 19),
        ring_color=(26, 30, 38),
        accent_color=(58, 64, 78),
        is_lockscreen=is_lock,
    )
    return img


def make_launcher_icon(size: int = 192) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=44, fill=(10, 11, 14, 255), outline=(90, 94, 104, 255), width=3)
    cx = size // 2
    draw.ellipse((cx - 52, cx - 52, cx + 52, cx + 52), outline=(235, 237, 240, 255), width=3)
    draw.ellipse((cx - 34, cx - 34, cx + 34, cx + 34), outline=(160, 165, 175, 255), width=2)
    draw.ellipse((cx - 6, cx - 6, cx + 6, cx + 6), fill=(255, 255, 255, 255))
    return img


def main() -> None:
    DRAWABLE_DIR.mkdir(parents=True, exist_ok=True)
    WALLPAPER_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    assets = {
        "wall_chrono.png": make_night_obsidian_wallpaper(is_lock=False),
        "wall_emerald.png": make_day_eink_wallpaper(is_lock=False),
        "wall_obsidian.png": make_day_eink_wallpaper(is_lock=True),
        "wall_lockscreen.png": make_night_obsidian_wallpaper(is_lock=True),
    }
    for name, im in assets.items():
        im.save(DRAWABLE_DIR / name, "PNG", optimize=True)
        im.save(WALLPAPER_EXPORT_DIR / name, "PNG", optimize=True)
        print(f"Generated {name} ({im.size[0]}x{im.size[1]})")

    icon = make_launcher_icon()
    icon.save(DRAWABLE_DIR / "ic_launcher.png", "PNG", optimize=True)
    print("Generated ic_launcher.png")


if __name__ == "__main__":
    main()
