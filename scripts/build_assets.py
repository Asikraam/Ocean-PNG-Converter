"""Generate Ocean PNG Converter icon (distinct emerald-teal identity, separate from BJ PDF)."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int):
    for path in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def build_ocean_png_icon(assets_dir: Path) -> None:
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Deep teal squircle (#0f766e) - clearly distinct from BJ PDF blue
    m = 16
    draw.rounded_rectangle([m, m, size - m, size - m], radius=108, fill=(15, 118, 110, 255))

    # Crisp white landscape image frame inside
    left, top, right, bottom = 92, 108, 420, 404
    draw.rounded_rectangle([left, top, right, bottom], radius=28, fill=(255, 255, 255, 255))

    # Minimal geometric wave/peak motif inside image frame (represents ocean/raster output)
    draw.ellipse([134, 144, 186, 196], fill=(15, 118, 110, 255))
    draw.polygon(
        [(118, 296), (206, 206), (274, 272), (324, 224), (394, 296)],
        fill=(13, 148, 136, 255),
    )

    # Clear "PNG" bar at bottom of frame
    draw.rounded_rectangle([126, 314, 386, 378], radius=14, fill=(15, 23, 42, 255))
    draw.text((256, 346), "PNG", font=_load_font(48), fill=(255, 255, 255, 255), anchor="mm")

    assets_dir.mkdir(parents=True, exist_ok=True)
    png_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    png_256.save(assets_dir / "ocean_png.png", "PNG")
    png_256.save(
        assets_dir / "ocean_png.ico",
        format="ICO",
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Generated {assets_dir / 'ocean_png.ico'} and ocean_png.png")


if __name__ == "__main__":
    build_ocean_png_icon(Path(__file__).resolve().parent / "assets")
