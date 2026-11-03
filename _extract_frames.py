"""One-off tool: slices the downloaded Vampire Survivors GIFs in assets/vs/<raw>/
into numbered transparent PNG frames the game's Animation class can load, plus a
meta.json per animation with each frame's duration (straight from the GIF).
Not imported by the game - just run once (or again if source GIFs change).
"""
import json
import os

from PIL import Image, ImageSequence

VS_DIR = os.path.join("assets", "vs")

# (source gif, output folder, output animation name)
JOBS = [
    ("antonio/walk.gif", "leon", "walk"),
    ("imelda/walk.gif", "elena", "walk"),
    ("skeleton/walk.gif", "skeleton", "walk"),
    ("skeleton/death.gif", "skeleton", "death"),
    ("bat/walk.gif", "harpy", "walk"),
    ("bat/death.gif", "harpy", "death"),
    ("batdragon/walk.gif", "kampe", "walk"),
    ("werewolf/walk.gif", "cerberus", "walk"),
    ("werewolf/death.gif", "cerberus", "death"),
    ("medusa/walk.gif", "hera", "walk"),
    ("reaper/walk.gif", "charon", "walk"),
    ("ghosts/spiritoso.gif", "shadow", "spiritoso"),
    ("ghosts/spiritosa.gif", "shadow", "spiritosa"),
]


def slice_gif(src_path, out_dir, anim_name):
    im = Image.open(src_path)
    os.makedirs(out_dir, exist_ok=True)
    durations = []
    frame_paths = []
    for i, frame in enumerate(ImageSequence.Iterator(im)):
        rgba = frame.convert("RGBA")
        out_path = os.path.join(out_dir, f"{anim_name}_{i}.png")
        rgba.save(out_path)
        frame_paths.append(os.path.basename(out_path))
        durations.append(frame.info.get("duration", 100))
    return frame_paths, durations


def main():
    for rel_src, out_name, anim_name in JOBS:
        src_path = os.path.join(VS_DIR, rel_src)
        out_dir = os.path.join(VS_DIR, out_name)
        frame_paths, durations = slice_gif(src_path, out_dir, anim_name)

        meta_path = os.path.join(out_dir, "meta.json")
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
        meta[anim_name] = {"frames": frame_paths, "durations_ms": durations}
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        print(f"{rel_src} -> {out_dir}/{anim_name}_*.png ({len(frame_paths)} frames)")


if __name__ == "__main__":
    main()
