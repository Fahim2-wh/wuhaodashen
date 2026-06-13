from pathlib import Path

root = Path("datasets/site_safety_v10")
classes = {
    0:"person",
    1:"helmet",
    2:"vest",
    3:"no_helmet",
    4:"no_vest",
    5:"edge_guardrail",
    6:"no_edge_guardrail",
    7:"material_stack",
    8:"messy_material",
    9:"wall_crack",
    10:"ground_crack",
    11:"scaffold",
    12:"warning_sign",
}

for split in ["train", "valid", "test"]:
    img_dir = root / split / "images"
    lab_dir = root / split / "labels"

    imgs = list(img_dir.glob("*.*"))
    labs = list(lab_dir.glob("*.txt"))

    print(f"\n{split}:")
    print("图片数量:", len(imgs))
    print("标签数量:", len(labs))

    count = {i: 0 for i in classes}
    bad = []

    for f in labs:
        for line in f.read_text(errors="ignore").splitlines():
            parts = line.strip().split()
            if not parts:
                continue
            try:
                cid = int(float(parts[0]))
                if cid in count:
                    count[cid] += 1
                else:
                    bad.append((f.name, cid))
            except:
                bad.append((f.name, line))

    for cid, name in classes.items():
        print(f"{cid:02d} {name:18s}: {count[cid]}")

    if bad:
        print("异常标签:", bad[:10])
