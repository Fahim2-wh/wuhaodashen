from pathlib import Path

p = Path("ai_service/detector.py")
s = p.read_text(encoding="utf-8")

# 1. 确保导入 complex risk detector
import_code = '''
# ===== 云筑天瞳：复杂风险双模型接入 =====
try:
    from ai_service.complex_risk_detector import detect_complex_risk
except Exception:
    try:
        from complex_risk_detector import detect_complex_risk
    except Exception:
        detect_complex_risk = None
# ===== 云筑天瞳：复杂风险双模型接入结束 =====
'''

if "云筑天瞳：复杂风险双模型接入" not in s:
    s = import_code + "\n" + s

# 2. 在 YOLO 绘图前，把 complex_risk.pt 的结果合并进 detections
old = '''    draw_annotated(img, detections, annotated, mode="yolo")
    top = "高" if any(d["level"] == "高" for d in detections) else "中" if any(d["level"] == "中" for d in detections) else "低"
'''
new = '''    # ===== 双模型：复杂风险识别合并 =====
    try:
        if detect_complex_risk is not None:
            complex_result = detect_complex_risk(image_path, model_path="models/complex_risk.pt", conf=0.18)
            for item in complex_result.get("items", []):
                box = item.get("box", [])
                detections.append({
                    "label": item.get("label", item.get("name", "复杂风险")),
                    "class_name": item.get("name", "complex_risk"),
                    "confidence": float(item.get("confidence", 0)),
                    "level": "高" if item.get("level") == "高风险" else "中" if item.get("level") == "中风险" else "低",
                    "bbox": box,
                    "advice": item.get("advice", "建议现场安全员复核。")
                })
    except Exception as e:
        print("复杂风险模型合并失败：", e)
    # ===== 双模型：复杂风险识别合并结束 =====

    draw_annotated(img, detections, annotated, mode="yolo")
    top = "高" if any(d["level"] == "高" for d in detections) else "中" if any(d["level"] == "中" for d in detections) else "低"
'''

if old in s:
    s = s.replace(old, new, 1)
else:
    print("没有找到标准插入点，稍后需要手动检查 detector.py。")
    
p.write_text(s, encoding="utf-8")
print("已尝试接入双模型识别：site_safety.pt + complex_risk.pt")
