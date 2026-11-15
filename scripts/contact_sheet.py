#!/usr/bin/env python3
"""
contact_sheet.py - turn captured frames into something you can actually review.

    python contact_sheet.py FRAMES_DIR sheet.jpg            # grid of evenly spaced frames
    python contact_sheet.py FRAMES_DIR sheet.jpg --n 12 --cols 4 --width 480
    python contact_sheet.py FRAMES_DIR clip.mp4 --fps 30     # encode a video (needs ffmpeg)
    python contact_sheet.py FRAMES_DIR clip.mp4 --fps 30 --resample   # use meta.json game times for even motion
    python contact_sheet.py before.png compare.jpg --after after.png --labels "Before" "After"

Frames are taken in name order (f_0000.jpg, f_0001.jpg, ...). Each grid cell is labelled with its
file name so you can point at the exact frame where something pops or smears.
Requires Pillow (pip install pillow).
"""
import argparse
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

EXTS = (".png", ".jpg", ".jpeg")


def frames(d):
    return [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(EXTS)]


def font(size):
    for p in ("DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(paths, out, n, cols, width):
    if len(paths) > n:
        step = (len(paths) - 1) / (n - 1)
        paths = [paths[round(i * step)] for i in range(n)]
    ims = [Image.open(p).convert("RGB") for p in paths]
    h = round(width * ims[0].height / ims[0].width)
    rows = -(-len(ims) // cols)
    sheet = Image.new("RGB", (cols * width + (cols + 1) * 8, rows * (h + 26) + 8), (245, 245, 242))
    dr, f = ImageDraw.Draw(sheet), font(14)
    for i, (im, p) in enumerate(zip(ims, paths)):
        x, y = 8 + (i % cols) * (width + 8), 8 + (i // cols) * (h + 26)
        sheet.paste(im.resize((width, h)), (x, y))
        dr.text((x, y + h + 4), os.path.basename(p), fill=(60, 60, 60), font=f)
    sheet.save(out, quality=88)
    return {"sheet": out, "frames_used": len(ims), "frames_total": len(frames(os.path.dirname(paths[0])))}


def compare(before, after, out, labels, width):
    a, b = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")
    h = round(width * a.height / a.width)
    sheet = Image.new("RGB", (2 * width + 24, h + 52), (245, 245, 242))
    dr, f = ImageDraw.Draw(sheet), font(22)
    for i, (im, lab) in enumerate(((a, labels[0]), (b, labels[1]))):
        x = 8 + i * (width + 8)
        sheet.paste(im.resize((width, h)), (x, 44))
        dr.text((x, 10), lab, fill=(30, 30, 30), font=f)
    sheet.save(out, quality=90)
    return {"compare": out}


def resampled(d, fps):
    """Pick, for each output frame, the captured frame nearest in GAME time (from meta.json)."""
    import json
    meta = json.load(open(os.path.join(d, "meta.json")))
    fr = sorted(meta["frames"], key=lambda f: f["t"])
    ps = frames(d)
    by_index = {int(os.path.splitext(os.path.basename(p))[0].split("_")[-1]): p for p in ps}
    out, j, n = [], 0, int(fr[-1]["t"] * fps) + 1
    for k in range(n):
        t = k / fps
        while j + 1 < len(fr) and abs(fr[j + 1]["t"] - t) <= abs(fr[j]["t"] - t):
            j += 1
        out.append(by_index[fr[j]["f"]])
    return out


def video(d, out, fps, resample=False):
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found")
    ps = resampled(d, fps) if resample else frames(d)
    ext = os.path.splitext(ps[0])[1]
    lst = os.path.join(d, "_frames.txt")
    with open(lst, "w") as fh:
        for p in ps:
            fh.write(f"file '{os.path.abspath(p)}'\nduration {1 / fps:.6f}\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", out], check=True)
    os.remove(lst)
    return {"video": out, "frames": len(ps), "seconds": round(len(ps) / fps, 2), "ext": ext}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--width", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--resample", action="store_true", help="video only: even out motion using meta.json game times")
    ap.add_argument("--after")
    ap.add_argument("--labels", nargs=2, default=["Before", "After"])
    a = ap.parse_args()
    if a.after:
        print(compare(a.src, a.after, a.out, a.labels, max(a.width, 640)))
    elif a.out.lower().endswith((".mp4", ".mov", ".webm")):
        print(video(a.src, a.out, a.fps, a.resample))
    else:
        print(grid(frames(a.src), a.out, a.n, a.cols, a.width))
