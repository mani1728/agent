"""
Generate the MT5 Agent application icon.

Run from Version 0_0_1:
    python make_icon.py

Output:
    agent/deployment/MT5Agent.ico     (multi-resolution Windows icon)

Design:
    Neural brain + orbit rings + candlesticks + status pulse,
    rendered with high-quality supersampling and glow effects.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BG_TOP = (10, 22, 40, 255)
BG_BOTTOM = (24, 12, 48, 255)
GRID_COLOR = (70, 120, 200, 18)
EDGE_COLOR = (100, 190, 255, 210)
NODE_CORE = (255, 255, 255, 255)
NODE_GLOW = (80, 180, 255, 140)
RING_CYAN = (0, 200, 255, 255)
RING_VIOLET = (140, 80, 255, 255)
RING_GLOW_CYAN = (0, 190, 255, 100)
RING_GLOW_VIOLET = (150, 90, 255, 90)
SPHERE_BASE = (30, 30, 45, 255)
SPHERE_MID = (90, 95, 120, 255)
SPHERE_HIGHLIGHT = (245, 248, 255, 255)
SPHERE_EDGE = (180, 185, 210, 255)
UP_GREEN = (0, 230, 140, 255)
UP_GREEN_DARK = (0, 170, 100, 255)
DOWN_RED = (230, 70, 90, 255)
DOWN_RED_DARK = (170, 40, 55, 255)
PULSE_GREEN = (0, 230, 140, 255)
PULSE_CORE = (220, 255, 230, 255)
PULSE_GLOW = (0, 230, 140, 110)

# Windows Explorer and the PE icon resource use 256x256 as the highest
# conventional embedded ICO resolution. Smaller sizes are included for
# crisp rendering at different shell/taskbar scales.
ICON_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(len(a)))


def _vertical_gradient(size, top, bottom):
    grad = Image.new("RGBA", (1, size))
    for y in range(size):
        grad.putpixel((0, y), _lerp(top, bottom, y / max(1, size - 1)))
    return grad.resize((size, size), Image.Resampling.BILINEAR)


def _rounded_mask(size, radius_ratio=0.22):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=int(size * radius_ratio),
        fill=255,
    )
    return mask


def _draw_background(size):
    bg = _vertical_gradient(size, BG_TOP, BG_BOTTOM)
    mask = _rounded_mask(size)
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    image.paste(bg, (0, 0), mask)
    return image


def _draw_grid(draw, size):
    step = max(1, size // 10)
    width = max(1, size // 500)
    for i in range(1, 10):
        x = i * step
        y = i * step
        draw.line([(x, 0), (x, size)], fill=GRID_COLOR, width=width)
        draw.line([(0, y), (size, y)], fill=GRID_COLOR, width=width)


def _brain_points(size):
    cx, cy = size * 0.50, size * 0.42
    rx, ry = size * 0.32, size * 0.28
    raw = [
        (-0.95, -0.15), (-0.92, -0.45), (-0.88, 0.15), (-0.85, -0.70),
        (-0.82, 0.40), (-0.80, -0.25), (-0.78, 0.65),
        (-0.70, -0.85), (-0.68, -0.50), (-0.65, -0.15), (-0.65, 0.20),
        (-0.62, 0.50), (-0.60, 0.80), (-0.55, -0.95), (-0.52, -0.60),
        (-0.50, -0.25), (-0.48, 0.10), (-0.48, 0.40), (-0.45, 0.70),
        (-0.42, 0.95),
        (-0.35, -1.00), (-0.35, -0.70), (-0.32, -0.35), (-0.30, 0.00),
        (-0.28, 0.30), (-0.28, 0.60), (-0.25, 0.85),
        (-0.18, -0.95), (-0.15, -0.55), (-0.12, -0.20), (-0.10, 0.15),
        (-0.10, 0.45), (-0.08, 0.75),
        (0.00, -1.00), (0.00, -0.65), (0.02, -0.30), (0.05, 0.05),
        (0.05, 0.35), (0.08, 0.65), (0.10, 0.90),
        (0.18, -0.95), (0.20, -0.60), (0.22, -0.25), (0.25, 0.10),
        (0.25, 0.40), (0.28, 0.70), (0.30, 0.95),
        (0.38, -0.90), (0.40, -0.55), (0.42, -0.20), (0.45, 0.15),
        (0.45, 0.45), (0.48, 0.75),
        (0.55, -0.80), (0.58, -0.45), (0.60, -0.10), (0.62, 0.25),
        (0.65, 0.55), (0.68, 0.80),
        (0.72, -0.65), (0.75, -0.30), (0.78, 0.05), (0.80, 0.35),
        (0.82, 0.60),
        (0.88, -0.45), (0.90, -0.15), (0.92, 0.15), (0.95, 0.40),
        (0.98, 0.00),
        (-0.15, 1.05), (0.00, 1.10), (0.15, 1.05),
        (-0.05, 1.20), (0.05, 1.18),
    ]
    return [(cx + xn * rx, cy + yn * ry) for xn, yn in raw]


def _draw_brain_edges(draw, pts, size):
    max_dist = size * 0.145
    width = max(1, int(size * 0.0032))
    for i, (x1, y1) in enumerate(pts):
        for x2, y2 in pts[i + 1:]:
            distance = math.hypot(x2 - x1, y2 - y1)
            if distance <= max_dist:
                alpha = int(190 * (1.0 - distance / max_dist))
                draw.line(
                    [(x1, y1), (x2, y2)],
                    fill=(90, 185, 255, max(35, alpha)),
                    width=width,
                )


def _draw_brain_nodes(draw, pts, size):
    radius = size * 0.0095
    glow_radius = size * 0.022
    for x, y in pts:
        draw.ellipse(
            [x - glow_radius, y - glow_radius, x + glow_radius, y + glow_radius],
            fill=NODE_GLOW,
        )
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=NODE_CORE,
        )


def _draw_orbit_rings(draw, size):
    cx, cy = size * 0.50, size * 0.44
    draw.ellipse(
        [cx - size * 0.42, cy - size * 0.155, cx + size * 0.42, cy + size * 0.155],
        outline=RING_VIOLET,
        width=max(2, int(size * 0.013)),
    )
    draw.ellipse(
        [cx - size * 0.355, cy - size * 0.125, cx + size * 0.355, cy + size * 0.125],
        outline=RING_CYAN,
        width=max(2, int(size * 0.011)),
    )


def _draw_sphere(draw, size):
    cx, cy = size * 0.82, size * 0.48
    radius = size * 0.048
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=SPHERE_BASE)
    mid_radius = radius * 0.78
    draw.ellipse(
        [cx - mid_radius, cy - mid_radius, cx + mid_radius, cy + mid_radius],
        fill=SPHERE_MID,
    )
    highlight_radius = radius * 0.42
    highlight_cx = cx - radius * 0.28
    highlight_cy = cy - radius * 0.32
    draw.ellipse(
        [
            highlight_cx - highlight_radius,
            highlight_cy - highlight_radius,
            highlight_cx + highlight_radius,
            highlight_cy + highlight_radius,
        ],
        fill=SPHERE_HIGHLIGHT,
    )
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=SPHERE_EDGE,
        width=max(1, int(size * 0.0035)),
    )


def _draw_candles(draw, size):
    body_width = size * 0.052
    wick_width = max(1, int(size * 0.009))
    gap = size * 0.105
    start_x = size * 0.30
    candles = [
        (0.78, 0.88, UP_GREEN, UP_GREEN_DARK),
        (0.74, 0.88, UP_GREEN, UP_GREEN_DARK),
        (0.68, 0.88, UP_GREEN, UP_GREEN_DARK),
        (0.76, 0.88, DOWN_RED, DOWN_RED_DARK),
    ]
    for idx, (top_ratio, bottom_ratio, color, dark) in enumerate(candles):
        x = start_x + idx * gap
        top_y = top_ratio * size
        bottom_y = bottom_ratio * size
        draw.line(
            [(x, top_y - size * 0.045), (x, bottom_y + size * 0.035)],
            fill=color,
            width=wick_width,
        )
        draw.rounded_rectangle(
            [x - body_width / 2, top_y, x + body_width / 2, bottom_y],
            radius=max(1, int(body_width * 0.12)),
            fill=color,
        )
        split = top_y + (bottom_y - top_y) * 0.55
        draw.rounded_rectangle(
            [x - body_width / 2, split, x + body_width / 2, bottom_y],
            radius=max(1, int(body_width * 0.12)),
            fill=dark,
        )


def _draw_status_pulse(draw, size):
    cx, cy = size * 0.84, size * 0.16
    core_radius = size * 0.032
    halo_radius = size * 0.068
    draw.ellipse(
        [cx - halo_radius, cy - halo_radius, cx + halo_radius, cy + halo_radius],
        fill=PULSE_GLOW,
    )
    ring_radius = size * 0.048
    draw.ellipse(
        [cx - ring_radius, cy - ring_radius, cx + ring_radius, cy + ring_radius],
        outline=PULSE_GREEN,
        width=max(1, int(size * 0.007)),
    )
    draw.ellipse(
        [cx - core_radius, cy - core_radius, cx + core_radius, cy + core_radius],
        fill=PULSE_CORE,
    )
    draw.ellipse(
        [
            cx - core_radius * 0.70,
            cy - core_radius * 0.70,
            cx + core_radius * 0.70,
            cy + core_radius * 0.70,
        ],
        fill=PULSE_GREEN,
    )


def draw_icon(size, supersample=None):
    """Render the icon at a requested size with high-quality supersampling."""
    if supersample is None:
        if size <= 48:
            supersample = 10
        elif size <= 128:
            supersample = 5
        else:
            supersample = 3

    canvas_size = size * supersample
    base = _draw_background(canvas_size)
    draw = ImageDraw.Draw(base, "RGBA")
    _draw_grid(draw, canvas_size)

    glow_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer, "RGBA")
    cx, cy = canvas_size * 0.50, canvas_size * 0.44
    glow_draw.ellipse(
        [cx - canvas_size * 0.42, cy - canvas_size * 0.155,
         cx + canvas_size * 0.42, cy + canvas_size * 0.155],
        outline=RING_GLOW_VIOLET,
        width=max(2, int(canvas_size * 0.028)),
    )
    glow_draw.ellipse(
        [cx - canvas_size * 0.355, cy - canvas_size * 0.125,
         cx + canvas_size * 0.355, cy + canvas_size * 0.125],
        outline=RING_GLOW_CYAN,
        width=max(2, int(canvas_size * 0.024)),
    )

    brain_pts = _brain_points(canvas_size)
    for x, y in brain_pts:
        radius = canvas_size * 0.018
        glow_draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(60, 160, 255, 80),
        )

    pulse_x, pulse_y = canvas_size * 0.84, canvas_size * 0.16
    pulse_radius = canvas_size * 0.065
    glow_draw.ellipse(
        [pulse_x - pulse_radius, pulse_y - pulse_radius,
         pulse_x + pulse_radius, pulse_y + pulse_radius],
        fill=PULSE_GLOW,
    )
    base = Image.alpha_composite(
        base,
        glow_layer.filter(ImageFilter.GaussianBlur(canvas_size * 0.011)),
    )

    main = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    main_draw = ImageDraw.Draw(main, "RGBA")
    _draw_orbit_rings(main_draw, canvas_size)
    _draw_brain_edges(main_draw, brain_pts, canvas_size)
    _draw_brain_nodes(main_draw, brain_pts, canvas_size)
    _draw_sphere(main_draw, canvas_size)
    _draw_candles(main_draw, canvas_size)
    _draw_status_pulse(main_draw, canvas_size)
    result = Image.alpha_composite(base, main)

    if supersample > 1:
        result = result.resize((size, size), Image.Resampling.LANCZOS)

    final_mask = _rounded_mask(size)
    alpha = Image.composite(result.getchannel("A"), Image.new("L", (size, size), 0), final_mask)
    result.putalpha(alpha)
    return result


def main() -> None:
    """Generate a high-quality multi-resolution Windows ICO file."""
    output_dir = Path("agent/deployment")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "MT5Agent.ico"

    # Render a 1024px master and let Pillow's ICO writer derive every
    # embedded Windows resolution from that high-quality source.
    master = draw_icon(1024, supersample=2)
    master.save(
        output_path,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
    )
    print(f"[OK] Icon written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
