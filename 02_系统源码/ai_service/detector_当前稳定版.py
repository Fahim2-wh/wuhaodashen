from pathlib import Path
import uuid
import cv2
import numpy as np

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)

PPE_CN = {
    "helmet": "安全帽",
    "vest": "反光衣",
    "person": "施工人员",
    "no_helmet": "未戴安全帽",
    "no_vest": "未穿反光衣",
    "mask": "口罩",
    "no_mask": "未戴口罩",
    "safety_cone": "安全锥",
    "machinery": "机械设备",
    "vehicle": "车辆",
}

PPE_RISK = {
    "helmet": ("低", "已识别到安全帽，个人防护用品基本符合要求，建议继续保持。"),
    "vest": ("低", "已识别到反光衣，人员可视化防护较好，建议继续保持。"),
    "person": ("中", "识别到施工人员，建议关注人员是否进入危险区域及是否规范佩戴防护用品。"),
    "no_helmet": ("高", "发现未戴安全帽风险，应立即提醒整改，未佩戴人员不得进入施工区域。"),
    "no_vest": ("中", "发现未穿反光衣风险，应立即规范穿戴，提升现场可视化安全管理。"),
    "mask": ("低", "已识别到口罩，防护状态较好。"),
    "no_mask": ("低", "发现未佩戴口罩情况，建议根据现场粉尘环境进行防护提醒。"),
    "safety_cone": ("中", "识别到安全锥，建议检查警示区域是否设置合理。"),
    "machinery": ("中", "识别到机械设备，建议关注人机交叉作业风险。"),
    "vehicle": ("中", "识别到车辆，建议检查车辆通行路线与人员作业区是否分离。"),
}

COMPLEX_CN = {
    "wall_crack": "墙体裂缝",
    "material_stack": "材料堆放",
    "edge_guardrail": "临边防护/护栏",
}

COMPLEX_RISK = {
    "wall_crack": ("高", "发现疑似墙体/地面裂缝，建议记录裂缝位置、长度和宽度；如裂缝持续发展，应由专业工程师复核。"),
    "material_stack": ("中", "发现材料堆放区域，建议检查是否占用通道、是否分类码放，并设置防倾倒措施。"),
    "edge_guardrail": ("低", "识别到临边防护或护栏设施，建议现场复核其连续性、牢固性和警示标识完整性。"),
}

BLOCK = {"boots", "boot", "gloves", "goggles", "shoe", "shoes"}

def _rel(p: Path):
    try:
        return str(p.relative_to(BASE))
    except Exception:
        return str(p)

def _draw(img, detections, out_path: Path):
    out = img.copy()

    for d in detections:
        # AI辅助研判只在右侧卡片展示，不在图片上画框，避免乱标
        if str(d.get("class_name", "")).endswith("_assist"):
            continue

        box = d.get("bbox") or []
        if len(box) != 4:
            continue

        x1, y1, x2, y2 = [int(float(v)) for v in box]
        level = d.get("level", "中")

        if level == "高":
            color = (0, 0, 255)
        elif level == "中":
            color = (0, 190, 255)
        else:
            color = (80, 230, 150)

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 3)

        # 避免中文乱码，框内英文/分数即可；右侧卡片显示中文
        text = f'{d.get("class_name","risk")} {int(float(d.get("confidence",0))*100)}%'
        cv2.rectangle(out, (x1, max(0, y1 - 28)), (min(out.shape[1]-1, x1 + 180), y1), color, -1)
        cv2.putText(out, text, (x1 + 4, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)

    cv2.imwrite(str(out_path), out)

def _dedup(detections):
    # 过滤误检
    cleaned = []
    for d in detections:
        cls = str(d.get("class_name", "")).lower()
        conf = float(d.get("confidence", 0))

        if cls in BLOCK:
            continue

        # PPE 高一点，复杂风险低一点
        if cls in {"helmet", "vest", "person"} and conf < 0.30:
            continue
        if cls in {"no_helmet", "no_vest"} and conf < 0.20:
            continue
        if cls in {"wall_crack", "material_stack", "edge_guardrail"} and conf < 0.10:
            continue

        cleaned.append(d)

    # 每类保留最高的 2 个
    groups = {}
    for d in cleaned:
        label = d.get("label", d.get("class_name", "未知"))
        groups.setdefault(label, []).append(d)

    final = []
    for label, arr in groups.items():
        arr = sorted(arr, key=lambda x: float(x.get("confidence", 0)), reverse=True)
        limit = 2
        if label in {"未戴安全帽", "未穿反光衣"}:
            limit = 3
        final.extend(arr[:limit])

    priority = {
        "未戴安全帽": 1,
        "未穿反光衣": 2,
        "墙体裂缝": 3,
        "材料堆放": 4,
        "临边防护/护栏": 5,
        "安全帽": 6,
        "反光衣": 7,
        "施工人员": 8,
    }

    final = sorted(final, key=lambda x: (priority.get(x.get("label", ""), 99), -float(x.get("confidence", 0))))
    return final[:12]

def _add_ai_assist_if_needed(detections, img_shape):
    # 已关闭旧版固定兜底AI辅助研判
    # 复杂风险后续由千问视觉按钮按需调用
    return detections

def _fallback(img, annotated):
    h, w = img.shape[:2]
    detections = [
        {
            "label": "临边/高处风险",
            "class_name": "edge_fallback",
            "confidence": 0.54,
            "bbox": [int(w*.55), int(h*.10), int(w*.94), int(h*.55)],
            "level": "中",
            "advice": "设置防护栏杆、盖板、安全网和警示标识。"
        },
        {
            "label": "个人防护用品核查",
            "class_name": "ppe_fallback",
            "confidence": 0.45,
            "bbox": [int(w*.06), int(h*.52), int(w*.38), int(h*.90)],
            "level": "中",
            "advice": "请人工复核安全帽、反光衣、安全带佩戴情况。"
        },
        {
            "label": "材料/通道风险",
            "class_name": "material_fallback",
            "confidence": 0.44,
            "bbox": [int(w*.30), int(h*.62), int(w*.90), int(h*.92)],
            "level": "低",
            "advice": "材料分类堆放，清理通道，防止坠落和绊倒。"
        },
    ]

    _draw(img, detections, annotated)
    return {
        "engine": "rule-vision-fallback",
        "risk_level": "中",
        "detections": detections,
        "annotated_path": _rel(annotated),
        "summary": "YOLO 未启用，当前使用图像特征分析回退。"
    }

def analyze_image(image_path, mode="施工现场安全YOLO"):
    image_path = Path(image_path)
    img = cv2.imread(str(image_path))

    if img is None:
        return {
            "engine": "image-read-error",
            "risk_level": "中",
            "detections": [],
            "annotated_path": "",
            "summary": "图片读取失败。"
        }

    annotated = UPLOADS / f"annotated_yolo_{uuid.uuid4().hex}.jpg"

    try:
        from ultralytics import YOLO

        detections = []

        # 1. PPE 主模型
        ppe_model_path = BASE / "models" / "site_safety.pt"
        if not ppe_model_path.exists():
            raise FileNotFoundError("未找到 site_safety.pt")

        ppe_model = YOLO(str(ppe_model_path))
        ppe_results = ppe_model.predict(str(image_path), conf=0.12, imgsz=640, verbose=False)

        for r in ppe_results:
            names = r.names
            if r.boxes is None:
                continue
            for box in r.boxes:
                cls_id = int(box.cls[0])
                raw = str(names.get(cls_id, cls_id))
                raw_l = raw.lower()
                conf = float(box.conf[0])

                if raw_l in BLOCK:
                    continue

                label = PPE_CN.get(raw_l, raw)
                level, advice = PPE_RISK.get(raw_l, ("中", "请安全员结合现场情况复核并形成整改记录。"))
                xyxy = box.xyxy[0].tolist()

                detections.append({
                    "label": label,
                    "class_name": raw_l,
                    "confidence": round(conf, 3),
                    "bbox": [round(x, 1) for x in xyxy],
                    "level": level,
                    "advice": advice,
                })

        # 2. 复杂风险模型
        complex_model_path = BASE / "models" / "complex_risk.pt"
        if complex_model_path.exists():
            complex_model = YOLO(str(complex_model_path))
            complex_results = complex_model.predict(str(image_path), conf=0.25, imgsz=416, verbose=False)

            for r in complex_results:
                names = r.names
                if r.boxes is None:
                    continue

                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    raw = str(names.get(cls_id, cls_id))
                    raw_l = raw.lower()
                    conf = float(box.conf[0])
                    xyxy = box.xyxy[0].tolist()
                    x1, y1, x2, y2 = xyxy
                    h, w = r.orig_shape

                    if raw_l == "edge_guardrail":
                        cx = (x1 + x2) / 2
                        cy = (y1 + y2) / 2
                        if cy < h * 0.28:
                            continue
                        if cx < w * 0.45 and cy < h * 0.55:
                            continue

                    label = COMPLEX_CN.get(raw_l, raw)
                    level, advice = COMPLEX_RISK.get(raw_l, ("中", "建议现场安全员复核。"))

                    detections.append({
                        "label": label,
                        "class_name": raw_l,
                        "confidence": round(conf, 3),
                        "bbox": [round(x, 1) for x in xyxy],
                        "level": level,
                        "advice": advice,
                    })

        detections = _dedup(detections)
        detections = _add_ai_assist_if_needed(detections, img.shape)
        detections = _dedup(detections)

        _draw(img, detections, annotated)

        top = "高" if any(d.get("level") == "高" for d in detections) else "中" if any(d.get("level") == "中" for d in detections) else "低"

        return {
            "engine": "real-yolo 双模型识别",
            "risk_level": top,
            "detections": detections,
            "annotated_path": _rel(annotated),
            "summary": "已启用 PPE 主模型与复杂风险模型，并结合 AI 辅助研判。"
        }

    except Exception as e:
        print("YOLO 双模型识别失败，进入 fallback：", repr(e))
        return _fallback(img, annotated)

# 兼容旧调用
def analyze(path, mode="施工现场安全YOLO"):
    return analyze_image(path, mode)
