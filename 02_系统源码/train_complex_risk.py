import shutil
import zipfile
import random
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
DOWNLOADS = Path.home() / "Downloads"

ZIP_FILES = {
    "crack": DOWNLOADS / "wall crack.zip",
    "stack": DOWNLOADS / "stack.zip",
    "guardrail": DOWNLOADS / "guardrail.zip",
}

OUT = ROOT / "datasets/complex_risk"
TMP = ROOT / "datasets/_tmp_complex_risk"

NAMES = [
    "wall_crack",
    "material_stack",
    "edge_guardrail",
]

CLASS_MAP = {
    "crack": 0,
    "stack": 1,
    "guardrail": 2,
}

# 为了 Mac 稳定，不跑全量，先抽样训练
MAX_IMAGES = {
    "crack": {"train": 1200, "valid": 200, "test": 120},
    "stack": {"train": 1000, "valid": 150, "test": 80},
    "guardrail": {"train": 1000, "valid": 150, "test": 80},
}

def reset_dirs():
    if OUT.exists():
        shutil.rmtree(OUT)
    if TMP.exists():
        shutil.rmtree(TMP)

    for split in ["train", "valid", "test"]:
        (OUT / split / "images").mkdir(parents=True, exist_ok=True)
        (OUT / split / "labels").mkdir(parents=True, exist_ok=True)

    TMP.mkdir(parents=True, exist_ok=True)

def unzip_files():
    for key, zpath in ZIP_FILES.items():
        if not zpath.exists():
            raise FileNotFoundError(f"找不到文件：{zpath}")
        target = TMP / key
        target.mkdir(parents=True, exist_ok=True)
        print(f"正在解压：{zpath.name}")
        with zipfile.ZipFile(zpath, "r") as z:
            z.extractall(target)

def find_dataset_dir(base: Path):
    candidates = []
    for p in base.rglob("data.yaml"):
        if "__MACOSX" not in str(p):
            candidates.append(p.parent)

    if not candidates:
        for p in base.rglob("train"):
            if (p / "images").exists() and (p / "labels").exists():
                candidates.append(p.parent)

    if not candidates:
        raise RuntimeError(f"没有找到 YOLO 数据集目录：{base}")

    candidates = sorted(
        candidates,
        key=lambda x: (
            (x / "train/images").exists(),
            (x / "valid/images").exists() or (x / "val/images").exists(),
            (x / "test/images").exists(),
        ),
        reverse=True,
    )
    return candidates[0]

def convert_label(src_label: Path, dst_label: Path, new_cls: int):
    if not src_label.exists():
        dst_label.write_text("", encoding="utf-8")
        return

    lines = []
    for line in src_label.read_text(errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue

        # 单类别数据集：不管原来类别叫什么，都统一映射
        parts[0] = str(new_cls)
        lines.append(" ".join(parts))

    dst_label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

def copy_dataset(key: str):
    ds = find_dataset_dir(TMP / key)
    print(f"{key} 数据集目录：{ds}")

    for split in ["train", "valid", "test"]:
        img_dir = ds / split / "images"
        lab_dir = ds / split / "labels"

        if split == "valid" and not img_dir.exists():
            img_dir = ds / "val/images"
            lab_dir = ds / "val/labels"

        if not img_dir.exists():
            print(f"跳过 {key}/{split}：没有 images")
            continue

        imgs = [
            img for img in img_dir.iterdir()
            if not img.name.startswith("._")
            and img.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
        ]

        random.shuffle(imgs)
        limit = MAX_IMAGES.get(key, {}).get(split, len(imgs))
        imgs = imgs[:limit]

        count = 0
        for img in imgs:
            new_name = f"{key}_{split}_{img.name}"
            dst_img = OUT / split / "images" / new_name
            shutil.copy2(img, dst_img)

            src_label = lab_dir / f"{img.stem}.txt"
            dst_label = OUT / split / "labels" / f"{Path(new_name).stem}.txt"
            convert_label(src_label, dst_label, CLASS_MAP[key])
            count += 1

        print(f"已合并 {key}/{split}：{count} 张")

def write_yaml():
    names_yaml = "\n".join([f"  {i}: {name}" for i, name in enumerate(NAMES)])
    (OUT / "data.yaml").write_text(
        f"""path: {OUT}
train: train/images
val: valid/images
test: test/images

nc: {len(NAMES)}
names:
{names_yaml}
""",
        encoding="utf-8"
    )
    print("data.yaml 已生成：", OUT / "data.yaml")

def stats():
    print("\n===== 复杂风险数据统计 =====")
    for split in ["train", "valid", "test"]:
        imgs = list((OUT / split / "images").glob("*"))
        labs = list((OUT / split / "labels").glob("*.txt"))
        print(f"{split}: images={len(imgs)}, labels={len(labs)}")

def train():
    print("\n===== 开始训练 complex_risk.pt =====")
    print("类别：wall_crack / material_stack / edge_guardrail")

    model = YOLO("yolov8n.pt")

    model.train(
        data=str(OUT / "data.yaml"),
        epochs=15,
        imgsz=416,
        batch=2,
        workers=0,
        project=str(ROOT / "runs/detect"),
        name="complex_risk",
        patience=5,
        pretrained=True,
        device="cpu",
    )

    best = ROOT / "runs/detect/complex_risk/weights/best.pt"
    target = ROOT / "models/complex_risk.pt"
    target.parent.mkdir(exist_ok=True)

    if best.exists():
        shutil.copy2(best, target)
        print("\n======================================")
        print("复杂风险模型训练完成！")
        print("已导出：", target)
        print("======================================")
    else:
        print("训练结束，但没有找到 best.pt。")

if __name__ == "__main__":
    reset_dirs()
    unzip_files()
    copy_dataset("crack")
    copy_dataset("stack")
    copy_dataset("guardrail")
    write_yaml()
    stats()
    train()
