import base64
import re
import time
from pathlib import Path

DATA_URI_PREFIX = re.compile(r"^data:image/\w+;base64,")


def save_qr_code_as_png(base64_string, transaction_id, directory):
    cleaned = DATA_URI_PREFIX.sub("", base64_string.strip())
    image_bytes = base64.b64decode(cleaned, validate=True)

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / f"qr_{transaction_id}_{int(time.time() * 1000)}.png"
    file_path.write_bytes(image_bytes)
    return str(file_path)
