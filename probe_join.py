import os, sys, urllib.request
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio_trim as at
from generate import RECITERS
os.makedirs("probe", exist_ok=True)
folder = RECITERS["maher"][0]
files = ["001001", "106001", "106002", "106003", "106004"]
fig, axes = plt.subplots(len(files), 1, figsize=(22, 4 * len(files)))
lines = []
for ax, f in zip(axes, files):
    p = f"/tmp/{f}.mp3"
    urllib.request.urlretrieve(f"https://everyayah.com/data/{folder}/{f}.mp3", p)
    x = at._decode(p); dur = len(x) / at.SR
    xs = at._decode_stereo(p)
    a, b = at.sound_bounds(xs)
    end = at.speech_end(p)
    ax.specgram(x + 1e-7, NFFT=512, Fs=at.SR, noverlap=448, cmap="magma", vmin=-130)
    ax.set_ylim(0, 6000)
    for v, c in ((a / at.JOIN_SR, "lime"), (b / at.JOIN_SR, "lime"), (end or 0, "cyan")):
        ax.axvline(v, color=c, lw=2)
    ax.set_title(f"{f} dur={dur:.2f} sound_bounds=({a/at.JOIN_SR:.2f},{b/at.JOIN_SR:.2f}) speech_end={end}")
    lines.append(f"{f} dur={dur:.3f} bounds={a/at.JOIN_SR:.3f},{b/at.JOIN_SR:.3f} speech_end={end}")
fig.tight_layout(); fig.savefig("probe/maher_106.png", dpi=50)
open("probe/maher_106.txt", "w").write("\n".join(lines) + "\n")
spans = at.join_verses([f"/tmp/{f}.mp3" for f in files], "/tmp/j.wav")
open("probe/maher_106.txt", "a").write("spans " + " ".join(f"{s:.3f}" for s in spans) + "\n")
