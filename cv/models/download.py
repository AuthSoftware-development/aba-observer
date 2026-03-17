"""Download required CV model files if not present."""

import hashlib
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).parent

MODELS = {
    "MobileNetSSD_deploy.prototxt": {
        "url": "https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.prototxt",
        "size_mb": 0.03,
        "sha256": None,  # Skip hash check for prototxt
    },
    "MobileNetSSD_deploy.caffemodel": {
        "url": "https://github.com/djmv/MobilNet_SSD_opencv/raw/master/MobileNetSSD_deploy.caffemodel",
        "size_mb": 23.1,
        "sha256": None,  # Skip hash check — multiple valid versions exist
    },
}


def download_models(force: bool = False):
    """Download all required model files."""
    for filename, info in MODELS.items():
        path = MODELS_DIR / filename
        if path.exists() and not force:
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > 0.01:  # Not an empty/corrupt file
                print(f"  [ok] {filename} ({size_mb:.1f} MB)")
                continue

        print(f"  [downloading] {filename} ({info['size_mb']:.1f} MB)...")
        try:
            urllib.request.urlretrieve(info["url"], str(path))
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  [ok] {filename} ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"  [error] {filename}: {e}")
            sys.exit(1)


def check_models() -> bool:
    """Check if all required model files are present and valid."""
    for filename, info in MODELS.items():
        path = MODELS_DIR / filename
        if not path.exists():
            return False
        if path.stat().st_size < 1024:  # Less than 1KB = corrupt/placeholder
            return False
    return True


if __name__ == "__main__":
    print("Checking CV model files...")
    if "--force" in sys.argv:
        download_models(force=True)
    else:
        download_models()
    print("All models ready.")
