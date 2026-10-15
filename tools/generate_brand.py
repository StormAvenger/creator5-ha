"""Render the project's original four-nozzle icon; no vendor artwork is used."""

from pathlib import Path

from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "custom_components/creator5/brand"
root.mkdir(parents=True, exist_ok=True)
for size, filename in ((256, "icon.png"), (512, "icon@2x.png")):
    scale = size / 256
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)

    def box(points, scale=scale):
        return tuple(round(x * scale) for x in points)

    draw.rounded_rectangle(box((8, 8, 248, 248)), radius=round(48 * scale), fill="#126B91")
    for x, y in ((53, 50), (147, 50), (53, 144), (147, 144)):
        draw.rounded_rectangle(box((x, y, x + 56, y + 48)), radius=round(8 * scale), fill="white")
        draw.rectangle(box((x + 8, y + 13, x + 48, y + 20)), fill="#126B91")
        draw.polygon(
            [box((x + 14, y + 48)), box((x + 42, y + 48)), box((x + 28, y + 66))], fill="#8DE1D9"
        )
    image.save(root / filename)
