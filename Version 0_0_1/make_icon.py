"""
Generate the MT5 Agent application icon.

Run from Version 0_0_1:
    python make_icon.py

Output:
    agent/deployment/MT5Agent.ico
"""

from pathlib import Path

from PIL import Image, ImageDraw


BG_DARK = (13, 27, 42, 255)
ACCENT = (0, 200, 120, 255)
UP_COLOR = (0, 220, 130, 255)
DOWN_COLOR = (220, 60, 80, 255)
ICON_SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size: int) -> Image.Image:
    """Draw one icon at the requested size."""
    scale = 4 if size <= 64 else 1
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = int(canvas_size * 0.22)
    draw.rounded_rectangle(
        [0, 0, canvas_size - 1, canvas_size - 1],
        radius=radius,
        fill=BG_DARK,
    )

    grid_color = (255, 255, 255, 25)
    step = canvas_size // 4
    for index in range(1, 4):
        x = index * step
        y = index * step
        draw.line(
            [(x, int(canvas_size * 0.12)), (x, int(canvas_size * 0.88))],
            fill=grid_color,
            width=max(1, scale),
        )
        draw.line(
            [(int(canvas_size * 0.12), y), (int(canvas_size * 0.88), y)],
            fill=grid_color,
            width=max(1, scale),
        )

    candles = [
        (0.22, 0.55, 0.78, 0.48, 0.85, False),
        (0.38, 0.38, 0.62, 0.30, 0.70, True),
        (0.54, 0.30, 0.50, 0.22, 0.58, True),
        (0.70, 0.18, 0.42, 0.12, 0.50, True),
    ]
    body_width = canvas_size * 0.09
    wick_width = max(1, int(canvas_size * 0.02))

    for center_x, body_top, body_bottom, wick_top, wick_bottom, is_up in candles:
        color = UP_COLOR if is_up else DOWN_COLOR
        x = center_x * canvas_size
        draw.line(
            [(x, wick_top * canvas_size), (x, wick_bottom * canvas_size)],
            fill=color,
            width=wick_width,
        )
        draw.rounded_rectangle(
            [
                x - body_width / 2,
                body_top * canvas_size,
                x + body_width / 2,
                body_bottom * canvas_size,
            ],
            radius=int(body_width * 0.15),
            fill=color,
        )

    dot_radius = canvas_size * 0.09
    dot_x = canvas_size * 0.80
    dot_y = canvas_size * 0.20
    draw.ellipse(
        [
            dot_x - dot_radius * 1.6,
            dot_y - dot_radius * 1.6,
            dot_x + dot_radius * 1.6,
            dot_y + dot_radius * 1.6,
        ],
        fill=(0, 200, 120, 60),
    )
    draw.ellipse(
        [
            dot_x - dot_radius,
            dot_y - dot_radius,
            dot_x + dot_radius,
            dot_y + dot_radius,
        ],
        fill=ACCENT,
    )

    if scale > 1:
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    return image


def main() -> None:
    """Generate a multi-resolution Windows ICO file."""
    output_dir = Path("agent/deployment")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "MT5Agent.ico"

    frames = [draw_icon(size) for size in ICON_SIZES]
    frames[0].save(
        output_path,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
        append_images=frames[1:],
    )
    print(f"[OK] Icon written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
