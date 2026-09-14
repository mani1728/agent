"""
Render high-resolution PNG previews of the MT5Agent icon.

Run from Version 0_0_1:
    python make_icon_preview.py

Output:
    agent/deployment/MT5Agent_preview_1024.png
    agent/deployment/MT5Agent_preview_2048.png
    agent/deployment/MT5Agent_preview_4096.png
    agent/deployment/MT5Agent_sheet.png
    agent/deployment/MT5Agent_sheet_dark.png
    agent/deployment/MT5Agent_sheet_small.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from make_icon import ICON_SIZES, draw_icon


def save_single(size: int, out_dir: Path) -> None:
    supersample = 2 if size <= 2048 else 1
    icon = draw_icon(size, supersample=supersample)
    path = out_dir / f"MT5Agent_preview_{size}.png"
    icon.save(path, format="PNG", optimize=True)
    print(f"[OK] {size}x{size} preview: {path.resolve()}")


def render_contact_sheet(
    icon_sizes: list[int],
    cell: int = 260,
    padding: int = 24,
    cols: int = 5,
    dark_mode: bool = False,
) -> Image.Image:
    rows = (len(icon_sizes) + cols - 1) // cols
    label_h = 40
    width = cols * (cell + padding) + padding
    height = rows * (cell + padding + label_h) + padding
    bg_color = (18, 18, 24, 255) if dark_mode else (245, 245, 250, 255)
    text_color = (230, 230, 240, 255) if dark_mode else (30, 30, 40, 255)

    sheet = Image.new("RGBA", (width, height), bg_color)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except Exception:
        font = ImageFont.load_default()

    for index, size in enumerate(icon_sizes):
        icon = draw_icon(size)
        display = icon.resize((cell, cell), Image.Resampling.NEAREST)
        row = index // cols
        col = index % cols
        x = padding + col * (cell + padding)
        y = padding + row * (cell + padding + label_h)

        if not dark_mode:
            for cy in range(0, cell, 20):
                for cx in range(0, cell, 20):
                    shade = 225 if ((cx // 20) + (cy // 20)) % 2 == 0 else 195
                    draw.rectangle(
                        [x + cx, y + cy, x + cx + 19, y + cy + 19],
                        fill=(shade, shade, shade, 255),
                    )

        sheet.alpha_composite(display, (x, y))
        draw.text(
            (x + 4, y + cell + 8),
            f"{size} x {size}",
            fill=text_color,
            font=font,
        )

    return sheet


def main() -> None:
    out_dir = Path("agent/deployment")
    out_dir.mkdir(parents=True, exist_ok=True)
    save_single(1024, out_dir)
    save_single(2048, out_dir)
    save_single(4096, out_dir)

    sheet = render_contact_sheet(ICON_SIZES, dark_mode=False)
    sheet.save(out_dir / "MT5Agent_sheet.png", format="PNG", optimize=True)
    print("[OK] Contact sheet (light)")

    sheet_dark = render_contact_sheet(ICON_SIZES, dark_mode=True)
    sheet_dark.save(out_dir / "MT5Agent_sheet_dark.png", format="PNG", optimize=True)
    print("[OK] Contact sheet (dark)")

    small_sizes = [16, 20, 24, 32, 48]
    small_sheet = render_contact_sheet(
        small_sizes, cell=180, padding=20, cols=5, dark_mode=True
    )
    small_sheet.save(out_dir / "MT5Agent_sheet_small.png", format="PNG", optimize=True)
    print("[OK] Small sizes sheet")


if __name__ == "__main__":
    main()
