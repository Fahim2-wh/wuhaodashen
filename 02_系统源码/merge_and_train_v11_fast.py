import shutil
import zipfile
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent
DOWNLOADS = Path.home() / "Downloads"

ZIP_FILES = {
    "ppe": DOWNLOADS / "construction-site-safety 2.zip",
    "crack": DOWNLOADS / "wall crack.zip",
    "stack": DOWNLOADS / "stack.zip",
    "guardrail": DOWNLOADS / "guardrail.zip",
}

OUT = ROOT / "datasets/site_safety_v11"
TMP = ROOT / "datasets/_tmp_merge_v11"

NAMES = [
    "helmet",
    "mask",
    "no_helmet",
    "no_mask",
    "no_vest",
    "person",
    "safety_cone",
    "vest",
    "machinery",
    "vehicle",
    "wall_crack",
    "material_stack",
    "edge_guardrail",
]

PPE_MAP = {
    0: 0,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 9,
}

SINGLE_MAP = {
    "crack": 10,
    "stack": 11,
    "guardrail": 12,
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


def convert_label(src_label: Path, dst_label: Path, mapping):
    if not src_label.exists():
        dst_label.write_text("", encoding="utf-8")
        return

    new_lines = []

    for line in src_label.read_text(errors="ignore").splitlines():
        parts = line.strip().split()
        if len(parts) < 5:
            continue

        try:
            old_cls = int(float(parts[0]))
        except Exception:
            continue

        if isinstance(mapping, dict):
            if old_cls not in mapping:
                continue
            new_cls = mapping[old_cls]
        else:
            new_cls = int(mapping)

        parts[0] = str(new_cls)
        new_lines.append(" ".join(parts))

    dst_label.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")


def copy_dataset(key: str, mapping):
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

        count = 0

        for img in img_dir.iterdir():
            if img.name.startswith("._"):
                continue
            if img.suffix.lower() not in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
                continue

            new_name = f"{key}_{split}_{img.name}"
            dst_img = OUT / split / "images" / new_name
            shutil.copy2(img, dst_img)

            src_label = lab_dir / f"{img.stem}.txt"
            dst_label = OUT / split / "labels" / f"{Path(new_name).stem}.txt"
            convert_label(src_label, dst_label, mapping)

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
        encoding="utf-8",
    )

    print("data.yaml 已生成：", OUT / "data.yaml")


def print_stats():
    print("\n===== 合并后数据统计 =====")

    for split in ["train", "valid", "test"]:
        imgs = list((OUT / split / "images").glob("*"))
        labs = list((OUT / split / "labels").glob("*.txt"))
        print(f"{split}: images={len(imgs)}, labels={len(labs)}")

    counts = {i: 0 for i in range(len(NAMES))}

    for lab in OUT.rglob("labels/*.txt"):
        for line in lab.read_text(errors="ignore").splitlines():
            parts = line.strip().split()
            if not parts:
                continue

            try:
                cid = int(float(parts[0]))
                if cid in counts:
                    counts[cid] += 1
            except Exception:
                pass

    print("\n===== 类别标注数量 =====")
    for i, name in enumerate(NAMES):
        print(f"{i:02d} {name:18s}: {counts[i]}")


def train_model():
    print("\n===== 开始训练：云筑天瞳 V11 多风险识别模型 =====")

    model = YOLO("yolov8n.pt")

    kwargs = dict(
        data=str(OUT / "data.yaml"),
        epochs=20,
        imgsz=512,
        batch=4,
        workers=4,
        project=str(ROOT / "runs/detect"),
        name="site_safety_v11_multi_risk",
        patience=6,
        pretrained=True,
    )

    try:
        import torch
        if torch.backends.mps.is_available():
            kwargs["device"] = "mps"
            print("已启用 Mac GPU 加速：device=mps")
        else:
            print("MPS 不可用，使用 CPU 训练")
    except Exception:
        print("无法检测 MPS，使用默认设备训练")

    model.train(**kwargs)

    best = ROOT / "runs/detect/site_safety_v11_multi_risk/weights/best.pt"
    target = ROOT / "models/site_safety.pt"
    target.parent.mkdir(exist_ok=True)

    if best.exists():
        shutil.copy2(best, target)
        print("\n======================================")
        print("训练完成！")
        print("新的 site_safety.pt 已导出：")
        print(target)
        print("======================================")
    else:
        print("训练结束，但没有找到 best.pt，请检查 runs/detect 输出。")


if __name__ == "__main__":
    reset_dirs()
    unzip_files()

    copy_dataset("ppe", PPE_MAP)
    copy_dataset("crack", SINGLE_MAP["crack"])
    copy_dataset("stack", SINGLE_MAP["stack"])
    copy_dataset("guardrail", SINGLE_MAP["guardrail"])

    write_yaml()
    print_stats()
    train_model()
