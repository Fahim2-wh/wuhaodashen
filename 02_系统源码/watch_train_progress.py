import time
import csv
from pathlib import Path
from datetime import datetime, timedelta

TOTAL_EPOCHS = 20
ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "runs/detect/site_safety_v11_multi_risk/results.csv"
WEIGHTS = ROOT / "runs/detect/site_safety_v11_multi_risk/weights"

def progress_bar(done, total, width=30):
    ratio = min(1, max(0, done / total)) if total else 0
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled), ratio

def read_epochs():
    if not RESULTS.exists():
        return []
    try:
        with RESULTS.open("r", encoding="utf-8", errors="ignore") as f:
            rows = list(csv.DictReader(f))
        return rows
    except Exception:
        return []

start_time = time.time()

while True:
    rows = read_epochs()
    now = datetime.now()

    print("\033c", end="")
    print("========================================")
    print("     云筑天瞳 V11 训练进度监控")
    print("========================================")
    print("")

    if not rows:
        print("状态：正在准备训练，还没有生成 results.csv")
        print("提示：如果刚开始训练，等 1～3 分钟再看。")
    else:
        current_epoch = len(rows)
        bar, ratio = progress_bar(current_epoch, TOTAL_EPOCHS)
        percent = ratio * 100

        elapsed = time.time() - start_time
        avg_per_epoch = elapsed / current_epoch if current_epoch else 0
        remain_epochs = max(0, TOTAL_EPOCHS - current_epoch)
        remain_seconds = avg_per_epoch * remain_epochs
        finish_time = now + timedelta(seconds=remain_seconds)

        last = rows[-1]

        print(f"当前进度：第 {current_epoch} / {TOTAL_EPOCHS} 轮")
        print(f"[{bar}] {percent:.1f}%")
        print("")
        print(f"已用时间：{timedelta(seconds=int(elapsed))}")
        print(f"预计剩余：{timedelta(seconds=int(remain_seconds))}")
        print(f"预计完成：{finish_time.strftime('%H:%M:%S')}")
        print("")

        map50 = last.get("metrics/mAP50(B)", "") or last.get("metrics/mAP50", "")
        box_loss = last.get("train/box_loss", "")
        cls_loss = last.get("train/cls_loss", "")

        print("最近一轮指标：")
        print(f"box_loss：{box_loss}")
        print(f"cls_loss：{cls_loss}")
        print(f"mAP50：{map50}")

    print("")
    best = WEIGHTS / "best.pt"
    lastpt = WEIGHTS / "last.pt"

    print("模型文件：")
    print("best.pt：", "已生成" if best.exists() else "未生成")
    print("last.pt：", "已生成" if lastpt.exists() else "未生成")

    print("")
    print("每 30 秒自动刷新，按 Control + C 退出监控。")
    time.sleep(30)
