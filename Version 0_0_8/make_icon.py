from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).parent / "deployment" / "MT5Agent.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def build_icon() -> None:
    images = []
    for size in SIZES:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        margin = max(1, size // 8)
        draw.rounded_rectangle((margin, margin, size - margin, size - margin), radius=max(2, size // 6), fill=(30, 90, 150, 255))
        draw.line((size // 5, size * 3 // 5, size // 2, size * 4 // 5), fill=(255, 255, 255, 255), width=max(1, size // 12))
        draw.line((size // 2, size * 4 // 5, size * 4 // 5, size // 4), fill=(255, 255, 255, 255), width=max(1, size // 12))
        images.append(image)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES])


if __name__ == "__main__":
    build_icon()
