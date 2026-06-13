from ultralytics import YOLO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "datasets/site_safety_v10/data.yaml"

if not DATA.exists():
    raise FileNotFoundError(f"未找到数据集配置文件: {DATA}")

model = YOLO("yolov8n.pt")

model.train(
    data=str(DATA),
    epochs=100,
    imgsz=640,
    batch=8,
    workers=2,
    name="site_safety_v10",
    project=str(ROOT / "runs/detect"),
    pretrained=True,
    patience=25
)

best = ROOT / "runs/detect/site_safety_v10/weights/best.pt"
target = ROOT / "models/site_safety.pt"

if best.exists():
    target.write_bytes(best.read_bytes())
    print("训练完成，已导出新模型：", target)
else:
    print("训练结束，但没有找到 best.pt，请检查 runs/detect/site_safety_v10/weights/")
