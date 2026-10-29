"""Builds the blurred background image for the "Nature" theme.

Drop your own photo(s) into a folder called "backgrounds" next to gui.py
(.jpg, .jpeg, .png or .webp). The first one (alphabetically) is used. If
the folder is empty or missing, a soft leafy pattern is drawn instead so
the theme still works.

The photo is blurred, then lightened toward pale green by exactly as much
as it takes to keep dark text readable (4.5:1 contrast, the WCAG AA level)
on every part of it. A dark photo gets lightened more than a bright one.

Needs the Pillow library (pip install pillow). It only runs once, when
the Nature theme is first selected, so it won't slow anything down.
"""
import base64
import importlib.util
import io
import random
from pathlib import Path

BACKGROUND_DIR = Path(__file__).with_name("backgrounds")
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}

BLUR_RADIUS = 5                  # how soft the photo is
WASH_COLOR = (238, 247, 238)     # pale green the photo is lightened toward
MIN_WASH, MAX_WASH = 0.25, 0.92  # least / most lightening allowed
CONTRAST = 4.5                   # WCAG AA for normal text
SAFETY = 0.01                    # small extra margin on the luminance


def _linear(channel):
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


_LINEAR = [_linear(c) for c in range(256)]


def luminance(rgb):
    """WCAG relative luminance of an (r, g, b) color, 0 (black) to 1 (white)."""
    r, g, b = rgb
    return 0.2126 * _LINEAR[r] + 0.7152 * _LINEAR[g] + 0.0722 * _LINEAR[b]


def hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def required_luminance(text_colors, contrast=CONTRAST):
    """How light the background must be for ALL these text colors to reach
    the contrast ratio on it. The LIGHTEST of the text colors is the hardest
    to read, so it decides."""
    lightest_text = max(luminance(hex_to_rgb(c)) for c in text_colors)
    return contrast * (lightest_text + 0.05) - 0.05 + SAFETY


def _washed(rgb, amount):
    return tuple(round(c * (1 - amount) + w * amount)
                 for c, w in zip(rgb, WASH_COLOR))


def wash_amount(image, required):
    """Smallest lightening that makes even the darkest part of the image
    at least `required` luminance (searched on a small copy of the image)."""
    from PIL import Image

    pixels = set(image.resize((160, 96), Image.NEAREST).getdata())

    def good_enough(amount):
        return min(luminance(_washed(p, amount)) for p in pixels) >= required

    if good_enough(MIN_WASH):
        return MIN_WASH
    low, high = MIN_WASH, MAX_WASH
    for _ in range(14):
        middle = (low + high) / 2
        if good_enough(middle):
            high = middle
        else:
            low = middle
    return high


def pillow_available():
    return importlib.util.find_spec("PIL") is not None


def list_photos(folder=BACKGROUND_DIR):
    """Photos in the backgrounds folder, alphabetical (empty if none)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)


def _placeholder(width, height):
    """A soft pile of green leaves, used when there is no photo yet."""
    from PIL import Image, ImageDraw

    rng = random.Random(7)  # same picture every time
    image = Image.new("RGB", (width, height), (28, 70, 45))
    greens = [(46, 125, 79), (63, 148, 92), (34, 97, 62),
              (88, 170, 110), (120, 190, 130), (24, 80, 52)]
    for _ in range(170):
        leaf_w = rng.randint(70, 170)
        leaf_h = int(leaf_w * rng.uniform(0.35, 0.5))
        leaf = Image.new("RGBA", (leaf_w, leaf_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(leaf)
        draw.ellipse((0, 0, leaf_w - 1, leaf_h - 1),
                     fill=rng.choice(greens) + (255,))
        draw.line((4, leaf_h // 2, leaf_w - 5, leaf_h // 2),
                  fill=(255, 255, 255, 70), width=2)
        leaf = leaf.rotate(rng.uniform(0, 360), expand=True,
                           resample=Image.BICUBIC)
        image.paste(leaf, (rng.randint(-60, width - 40),
                           rng.randint(-60, height - 40)), leaf)
    return image


def _cover(image, width, height):
    """Resize to fill width x height, cropping the overflow from the middle."""
    from PIL import Image

    scale = max(width / image.width, height / image.height)
    image = image.resize(
        (max(width, round(image.width * scale)),
         max(height, round(image.height * scale))),
        Image.LANCZOS,
    )
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def build_background(width, height, photo=None, text_colors=("#1E3A2B",)):
    """Return the finished background as a base64 PNG string for Tk.

    photo: path to an image; if None, the first photo in the backgrounds
    folder is used, or the leafy placeholder if there isn't one.
    text_colors: the (hex) colors of text that will sit on the photo; the
    photo is lightened until all of them are readable on every part of it.
    """
    from PIL import Image, ImageFilter

    if photo is None:
        photos = list_photos()
        photo = photos[0] if photos else None

    if photo is None:
        image = _placeholder(width, height)
    else:
        image = _cover(Image.open(photo).convert("RGB"), width, height)

    image = image.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    amount = wash_amount(image, required_luminance(text_colors))
    image = Image.blend(image, Image.new("RGB", image.size, WASH_COLOR), amount)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue())


if __name__ == "__main__":
    # Quick test: python3 background.py  (writes background_preview.png)
    data = build_background(800, 480)
    Path("background_preview.png").write_bytes(base64.b64decode(data))
    print("Photos found:", [p.name for p in list_photos()] or "none (using placeholder)")
    print("Wrote background_preview.png")
