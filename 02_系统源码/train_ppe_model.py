from ultralytics import YOLO
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "datasets/construction-site-safety/data.yaml"

print("========================================")
print("云筑天瞳 V10 PPE 安全识别模型训练")
print("========================================")
print("使用数据集：", DATA)

if not DATA.exists():
    raise FileNotFoundError(f"未找到 data.yaml：{DATA}")

model = YOLO("yolov8n.pt")

model.train(
    data=str(DATA),
    epochs=60,
    imgsz=640,
    batch=8,
    workers=2,
    project=str(ROOT / "runs/detect"),
    name="site_safety_ppe_v10",
    patience=15
)

best = ROOT / "runs/detect/site_safety_ppe_v10/weights/best.pt"
target = ROOT / "models/site_safety.pt"

target.parent.mkdir(exist_ok=True)

if best.exists():
    target.write_bytes(best.read_bytes())
    print("========================================")
    print("训练完成！")
    print("新模型已导出到：", target)
    print("========================================")
else:
    print("没有找到 best.pt，请检查训练输出。")
