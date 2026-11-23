import os, sys, urllib.request, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_trim as at
from generate import RECITERS
os.makedirs("probe", exist_ok=True)
FILES = ["106001", "106002", "106003", "112001", "112002", "112003", "103001", "103002", "2255", "1001"]
FILES = ["106001", "106002", "106003", "112001", "112002", "112003", "103001", "103002", "094005", "001007", "002285", "093003"]
out = {}
def edge(p):
    x = at._decode(p)
    db = at.frame_features(x)[0]
    level = np.percentile(db, 90)
    tail = db[-3:].mean() - level          # last ~60 ms vs the recitation's loudness
    head = db[:3].mean() - level
    return round(float(tail), 1), round(float(head), 1), round(len(x) / at.SR, 2)
for key, (folder, _) in RECITERS.items():
    row = {}
    for f in FILES:
        p = f"/tmp/{key}_{f}.mp3"
        try:
            urllib.request.urlretrieve(f"https://everyayah.com/data/{folder}/{f}.mp3", p)
            row[f] = edge(p)
        except Exception as e:
            row[f] = str(e)[:30]
    out[key] = row
    print(key, {k: v[0] if isinstance(v, tuple) else v for k, v in row.items()}, flush=True)
json.dump(out, open("probe/edges.json", "w"), indent=0)
