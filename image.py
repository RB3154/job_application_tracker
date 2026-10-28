"""Saving and deleting user profile pictures on disk."""

import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


PROFILE_PICS_DIR = Path("media/profile_pics")


def process_profile_image(content: bytes) -> str:
    """Crop the uploaded image to a 300x300 JPEG, save it, and return its new filename.

    Raises PIL.UnidentifiedImageError if the bytes are not an image.
    """

    with Image.open(BytesIO(content)) as original:
        # Phones store rotation in EXIF data; apply it so the picture isn't sideways.
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        # JPEG has no transparency, so convert images that do (e.g. PNG) to plain RGB.
        if img.mode != "RGB":
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.jpg"
        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
        img.save(PROFILE_PICS_DIR / filename, "JPEG", quality=85, optimize=True)

    return filename


def delete_profile_image(filename: str | None) -> None:
    if filename is None:
        return
    (PROFILE_PICS_DIR / filename).unlink(missing_ok=True)
