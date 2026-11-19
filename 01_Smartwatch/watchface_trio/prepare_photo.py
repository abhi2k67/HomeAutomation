"""Prepare personal photos or generate sleek demo assets for Minimal Trio WFF."""

import math
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent
DRAWABLE_DIR = ROOT / "res" / "drawable"


def center_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop and resize an image to exact target dimensions."""
    return ImageOps.fit(img.convert("RGBA"), (target_w, target_h), method=Image.Resampling.LANCZOS)


def create_radial_vignette(size: int = 450, inner_ratio: float = 0.62) -> Image.Image:
    """Create a pure #000000 radial vignette overlay for infinite-bezel AMOLED melt."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    cx = cy = size / 2.0
    max_r = size / 2.0
    inner_r = max_r * inner_ratio

    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy)
            if dist <= inner_r:
                alpha = 0
            elif dist >= max_r:
                alpha = 255
            else:
                t = (dist - inner_r) / (max_r - inner_r)
                # Smoothstep curve for natural optical falloff
                alpha = int(255 * (t * t * (3 - 2 * t)))
            px[x, y] = (0, 0, 0, alpha)
    return img


def create_leica_reticle(w: int = 340, h: int = 255) -> Image.Image:
    """Create 1px corner crop marks and subtle frame border for Leica Viewfinder."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Subtle outer frame line
    draw.rectangle([0, 0, w - 1, h - 1], outline=(255, 255, 255, 45), width=1)

    # Crisp corner L-brackets
    c = (242, 239, 233, 210)
    arm = 14
    # Top-left
    draw.line([(0, 0), (arm, 0)], fill=c, width=2)
    draw.line([(0, 0), (0, arm)], fill=c, width=2)
    # Top-right
    draw.line([(w - 1 - arm, 0), (w - 1, 0)], fill=c, width=2)
    draw.line([(w - 1, 0), (w - 1, arm)], fill=c, width=2)
    # Bottom-left
    draw.line([(0, h - 1), (arm, h - 1)], fill=c, width=2)
    draw.line([(0, h - 1 - arm), (0, h - 1)], fill=c, width=2)
    # Bottom-right
    draw.line([(w - 1 - arm, h - 1), (w - 1, h - 1)], fill=c, width=2)
    draw.line([(w - 1, h - 1 - arm), (w - 1, h - 1)], fill=c, width=2)

    # Subtle center rangefinder dot
    cx, cy = w // 2, h // 2
    draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(212, 175, 106, 130))
    return img


def generate_demo_scene() -> tuple[Image.Image, Image.Image]:
    """Generate a minimalist twilight mountain silhouette demo (bg + fg cutout)."""
    size = 450
    bg = Image.new("RGBA", (size, size), (12, 16, 28, 255))
    draw = ImageDraw.Draw(bg)

    # Deep twilight gradient sky
    for y in range(size):
        t = y / size
        r = int(10 + 38 * (1 - t) ** 2)
        g = int(14 + 32 * (1 - t) ** 1.6)
        b = int(26 + 48 * (1 - t))
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Subtle distant ridge
    ridge_far = [(0, 290), (85, 235), (175, 265), (275, 220), (365, 255), (450, 230), (450, 450), (0, 450)]
    draw.polygon(ridge_far, fill=(22, 27, 42, 255))

    # Foreground peak (this layer overlaps the giant editorial clock!)
    fg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg)
    peak = [(0, 340), (95, 275), (185, 315), (245, 162), (320, 290), (400, 260), (450, 305), (450, 450), (0, 450)]
    fg_draw.polygon(peak, fill=(10, 12, 18, 255))
    # Subtle rim highlight along the peak's lit edge
    fg_draw.line([(185, 315), (245, 162), (320, 290)], fill=(212, 175, 106, 150), width=2)

    return bg, fg


def make_chrono_mono(img: Image.Image, vignette: Image.Image) -> Image.Image:
    """Create high-contrast warm monochrome + infinite-bezel vignette."""
    gray = ImageOps.grayscale(img.convert("RGB"))
    gray = ImageEnhance.Contrast(gray).enhance(1.35)
    # Subtle warm silver-gold tint
    warm = ImageOps.colorize(gray, black=(0, 0, 0), white=(238, 232, 220)).convert("RGBA")
    warm.alpha_composite(vignette)
    return warm


def prepare(photo_path: Path | None = None, fg_path: Path | None = None) -> None:
    """Generate all drawable assets required by watchface.xml."""
    DRAWABLE_DIR.mkdir(parents=True, exist_ok=True)
    vignette = create_radial_vignette(450, inner_ratio=0.60)
    vignette.save(DRAWABLE_DIR / "overlay_vignette.png")
    create_leica_reticle(340, 255).save(DRAWABLE_DIR / "overlay_leica_reticle.png")

    if photo_path is None:
        bg, fg = generate_demo_scene()
        full_scene = bg.copy()
        full_scene.alpha_composite(fg)
        bg.save(DRAWABLE_DIR / "photo_depth_bg.png")
        fg.save(DRAWABLE_DIR / "photo_depth_fg.png")
        center_crop_resize(full_scene, 340, 255).save(DRAWABLE_DIR / "photo_leica_frame.png")
        make_chrono_mono(full_scene, vignette).save(DRAWABLE_DIR / "photo_chrono_mono.png")
        preview = full_scene.copy()
        preview.alpha_composite(vignette)
        preview.save(DRAWABLE_DIR / "preview_trio.png")
        print("Generated built-in demo assets in", DRAWABLE_DIR)
        return

    src = Image.open(photo_path)
    bg = center_crop_resize(src, 450, 450)
    bg.save(DRAWABLE_DIR / "photo_depth_bg.png")

    if fg_path is not None and fg_path.exists():
        fg = center_crop_resize(Image.open(fg_path), 450, 450)
    else:
        # Optional: if rembg is installed, auto-extract subject; otherwise empty fg
        try:
            from rembg import remove  # type: ignore

            fg = remove(bg)
        except Exception:
            fg = Image.new("RGBA", (450, 450), (0, 0, 0, 0))
    fg.save(DRAWABLE_DIR / "photo_depth_fg.png")

    leica = center_crop_resize(src, 340, 255)
    leica = ImageEnhance.Contrast(leica).enhance(1.12)
    leica.save(DRAWABLE_DIR / "photo_leica_frame.png")

    make_chrono_mono(bg, vignette).save(DRAWABLE_DIR / "photo_chrono_mono.png")

    preview = bg.copy()
    preview.alpha_composite(vignette)
    preview.save(DRAWABLE_DIR / "preview_trio.png")
    print(f"Prepared all 3 watch face styles from: {photo_path}")


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    fg_p = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    prepare(p, fg_p)
