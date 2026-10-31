"""Copy images from a folder into backgrounds/ (skips ones already there or too small).
Usage: python sync_backgrounds.py "<folder>"   """
import os, sys
from PIL import Image
MIN_W = 600
src = sys.argv[1]; dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backgrounds")
os.makedirs(dst, exist_ok=True)
added, skipped = [], []
for f in sorted(os.listdir(src)):
    if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        continue
    name = os.path.splitext(f)[0] + ".jpg"
    if os.path.exists(os.path.join(dst, name)):
        continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    if im.width < MIN_W:
        skipped.append(f"{f} ({im.width}x{im.height}, too small)"); continue
    if im.height > 2400:
        im = im.resize((round(im.width * 2400 / im.height), 2400), Image.LANCZOS)
    im.save(os.path.join(dst, name), quality=92)
    added.append(name)
print(f"added {len(added)}"); [print("  skipped", s) for s in skipped]
