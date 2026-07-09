from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "questionnaire.db"
PADDLE_OCR_DIR = DATA_DIR / "paddleocr"

DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
PADDLE_OCR_DIR.mkdir(exist_ok=True)
os.environ.setdefault("PADDLE_OCR_BASE_DIR", str(PADDLE_OCR_DIR))
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_use_onednn", "0")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover
    cv2 = None
    np = None

try:
    import easyocr
except Exception:  # pragma: no cover
    easyocr = None

try:
    import paddle
    from paddleocr import PaddleOCR
    try:
        paddle.set_flags({"FLAGS_use_mkldnn": False})
    except Exception:
        pass
    try:
        paddle.set_flags({"FLAGS_use_onednn": False})
    except Exception:
        pass
except Exception:  # pragma: no cover
    paddle = None
    PaddleOCR = None

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    Image = None
    ImageStat = None

try:
    from openpyxl import Workbook
except ImportError:  # pragma: no cover
    Workbook = None


app = FastAPI(title="问卷图像识别与数据导出系统 V1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExportPayload(BaseModel):
    taskId: str
    rows: list[dict[str, Any]]


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                file_count INTEGER NOT NULL,
                status TEXT NOT NULL
            )
            """
        )
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                question_no INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                confidence INTEGER NOT NULL,
                status TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """
        )


@lru_cache(maxsize=1)
def get_easyocr_reader() -> Any:
    if easyocr is None:
        raise RuntimeError("EasyOCR 未安装")
    return easyocr.Reader(["ch_sim", "en"], gpu=False)


@lru_cache(maxsize=1)
def get_paddleocr_reader() -> Any:
    if PaddleOCR is None:
        raise RuntimeError("PaddleOCR 未安装")
    try:
        return PaddleOCR(
            lang="ch",
            ocr_version="PP-OCRv3",
            ir_optim=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    except Exception:
        return PaddleOCR(use_angle_cls=True, lang="ch", ocr_version="PP-OCRv3", ir_optim=False, show_log=False)


def bbox_center(box: list[list[float]]) -> tuple[float, float]:
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def bbox_rect(box: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return min(xs), min(ys), max(xs), max(ys)


def run_easyocr(path: Path) -> dict[str, Any]:
    reader = get_easyocr_reader()
    raw_items = reader.readtext(str(path), detail=1, paragraph=False)
    items = []
    for box, text, confidence in raw_items:
        clean_text = re.sub(r"\s+", " ", text).strip()
        if not clean_text:
            continue
        x, y = bbox_center(box)
        x1, y1, x2, y2 = bbox_rect(box)
        items.append(
            {
                "text": clean_text,
                "confidence": round(float(confidence) * 100, 1),
                "box": box,
                "x": x,
                "y": y,
                "rect": [x1, y1, x2, y2],
            }
        )
    items.sort(key=lambda item: (item["y"], item["x"]))
    return {
        "items": items,
        "text": "\n".join(item["text"] for item in items),
        "avg_confidence": round(sum(item["confidence"] for item in items) / max(len(items), 1), 1),
        "engine": "easyocr",
    }


def normalize_paddle_box(poly: Any) -> list[list[float]]:
    points = []
    for point in poly:
        points.append([float(point[0]), float(point[1])])
    return points


def run_paddleocr(path: Path) -> dict[str, Any]:
    reader = get_paddleocr_reader()
    items = []

    if hasattr(reader, "predict"):
        prediction = reader.predict(str(path))
        for page in prediction:
            data = getattr(page, "json", None)
            if callable(data):
                data = data()
            if not isinstance(data, dict):
                data = page if isinstance(page, dict) else {}
            result = data.get("res", data)
            texts = result.get("rec_texts") or result.get("texts") or []
            scores = result.get("rec_scores") or result.get("scores") or []
            polys = result.get("rec_polys") or result.get("dt_polys") or result.get("polys") or []
            for index, text in enumerate(texts):
                clean_text = re.sub(r"\s+", " ", str(text)).strip()
                if not clean_text:
                    continue
                score = float(scores[index]) if index < len(scores) else 0.75
                box = normalize_paddle_box(polys[index]) if index < len(polys) else [[0, float(index * 32)], [1, float(index * 32)], [1, float(index * 32 + 20)], [0, float(index * 32 + 20)]]
                x, y = bbox_center(box)
                x1, y1, x2, y2 = bbox_rect(box)
                items.append({"text": clean_text, "confidence": round(score * 100, 1), "box": box, "x": x, "y": y, "rect": [x1, y1, x2, y2]})
    else:
        raw_pages = reader.ocr(str(path), cls=True)
        for page in raw_pages or []:
            for line in page or []:
                if not line or len(line) < 2:
                    continue
                box = normalize_paddle_box(line[0])
                text_info = line[1]
                text = text_info[0] if len(text_info) > 0 else ""
                score = float(text_info[1]) if len(text_info) > 1 else 0.75
                clean_text = re.sub(r"\s+", " ", str(text)).strip()
                if not clean_text:
                    continue
                x, y = bbox_center(box)
                x1, y1, x2, y2 = bbox_rect(box)
                items.append({"text": clean_text, "confidence": round(score * 100, 1), "box": box, "x": x, "y": y, "rect": [x1, y1, x2, y2]})

    items.sort(key=lambda item: (item["y"], item["x"]))
    return {
        "items": items,
        "text": "\n".join(item["text"] for item in items),
        "avg_confidence": round(sum(item["confidence"] for item in items) / max(len(items), 1), 1),
        "engine": "paddleocr",
    }


def run_best_ocr(path: Path) -> dict[str, Any]:
    errors = []
    if PaddleOCR is not None:
        try:
            return run_paddleocr(path)
        except Exception as exc:  # noqa: BLE001 - OCR model/download/runtime failures should fall through.
            errors.append(f"PaddleOCR失败：{exc}")
    if easyocr is not None:
        try:
            result = run_easyocr(path)
            if errors:
                result["fallbackReason"] = "；".join(errors)
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"EasyOCR失败：{exc}")
    raise RuntimeError("；".join(errors) or "未安装可用OCR引擎")


def detect_checkboxes(path: Path) -> list[dict[str, Any]]:
    if cv2 is None or np is None:
        return []

    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return []

    max_width = 1600
    scale = 1.0
    if image.shape[1] > max_width:
        scale = max_width / image.shape[1]
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    blurred = cv2.GaussianBlur(image, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        8,
    )
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[dict[str, Any]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if area < 180 or area > 3600:
            continue
        aspect = w / max(h, 1)
        if not 0.65 <= aspect <= 1.45:
            continue
        if w < 14 or h < 14 or w > 60 or h > 60:
            continue

        roi = binary[y : y + h, x : x + w]
        fill_ratio = float(cv2.countNonZero(roi)) / max(area, 1)
        if not 0.08 <= fill_ratio <= 0.75:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)
        contour_area = cv2.contourArea(contour)
        extent = contour_area / max(area, 1)
        circularity = 4 * np.pi * contour_area / max(perimeter * perimeter, 1)
        looks_square = 4 <= len(approx) <= 6 and extent >= 0.48
        looks_circle = len(approx) > 6 and 0.45 <= circularity <= 1.25
        if not (looks_square or looks_circle):
            continue
        shape = "圆形" if len(approx) > 6 else "方形"
        checked = fill_ratio > 0.28
        boxes.append(
            {
                "x": round(x / scale),
                "y": round(y / scale),
                "w": round(w / scale),
                "h": round(h / scale),
                "shape": shape,
                "checked": checked,
                "fillRatio": round(fill_ratio, 3),
            }
        )

    boxes.sort(key=lambda item: (item["y"], item["x"]))
    filtered: list[dict[str, Any]] = []
    for box in boxes:
        is_duplicate = any(
            abs(box["x"] - old["x"]) < 8 and abs(box["y"] - old["y"]) < 8 for old in filtered
        )
        if not is_duplicate:
            filtered.append(box)
    return filtered[:80]


def analyze_image(path: Path) -> dict[str, Any]:
    if Image is None or ImageStat is None:
        return {
            "width": 0,
            "height": 0,
            "dark_ratio": 0,
            "checkbox_candidates": 0,
            "note": "未安装 Pillow，无法读取图片。",
        }

    with Image.open(path) as image:
        width, height = image.size
        gray = image.convert("L")
        gray.thumbnail((1200, 1200))
        stat = ImageStat.Stat(gray)
        mean_gray = stat.mean[0]
        total_pixels = max(gray.size[0] * gray.size[1], 1)
        dark_ratio = sum(1 for value in gray.getdata() if value < 120) / total_pixels
        confidence = max(55, min(96, int(100 - abs(mean_gray - 210) / 3)))
        return {
            "width": width,
            "height": height,
            "dark_ratio": round(dark_ratio * 100, 2),
            "confidence": confidence,
        }


def nearest_option_text(box: dict[str, Any], ocr_items: list[dict[str, Any]]) -> str:
    candidates = []
    box_y = box["y"] + box["h"] / 2
    box_x = box["x"] + box["w"]
    for item in ocr_items:
        item_y = item["y"]
        item_x = item["x"]
        if item_x < box_x:
            continue
        y_distance = abs(item_y - box_y)
        if y_distance > max(28, box["h"] * 1.2):
            continue
        candidates.append((y_distance, item_x - box_x, item["text"]))
    if not candidates:
        return "未匹配到选项文字"
    candidates.sort(key=lambda value: (value[0], value[1]))
    return candidates[0][2]


def build_ocr_rows(task_id: str, file_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for file_index, result in enumerate(file_results, start=1):
        ocr = result.get("ocr", {})
        boxes = result.get("checkboxes", [])
        checked_boxes = [box for box in boxes if box.get("checked")]
        ocr_items = ocr.get("items", [])
        text_lines = [item["text"] for item in ocr_items]

        if checked_boxes:
            for box_index, box in enumerate(checked_boxes, start=1):
                option_text = nearest_option_text(box, ocr_items)
                rows.append(
                    {
                        "id": len(rows) + 1,
                        "taskId": task_id,
                        "question": f"图片 {file_index} 勾选项 {box_index}",
                        "answer": option_text,
                        "confidence": min(96, max(60, int(ocr.get("avg_confidence") or 75))),
                        "status": "待确认",
                        "type": box.get("shape", "选项框"),
                        "options": [
                            f"位置：x={box['x']}, y={box['y']}, w={box['w']}, h={box['h']}",
                            f"填充比例：{box['fillRatio']}",
                            f"OCR文字总数：{len(text_lines)}",
                        ],
                    }
                )

        question_candidates = [
            text for text in text_lines if re.search(r"(^\d+[\.\、]|[？?]|姓名|性别|年龄|满意|建议|是否)", text)
        ]
        if not question_candidates and text_lines:
            question_candidates = text_lines[:8]

        for text in question_candidates[:12]:
            rows.append(
                {
                    "id": len(rows) + 1,
                    "taskId": task_id,
                    "question": text,
                    "answer": "请人工确认",
                    "confidence": min(96, max(55, int(ocr.get("avg_confidence") or 70))),
                    "status": "待确认",
                    "type": "OCR文本",
                    "options": text_lines[:10],
                }
            )

        if not rows:
            analysis = result.get("analysis", {})
            rows.append(
                {
                    "id": 1,
                    "taskId": task_id,
                    "question": f"图片 {file_index} 未识别到清晰文字",
                    "answer": "请更换更清晰的扫描件或手动录入",
                    "confidence": int(analysis.get("confidence") or 55),
                    "status": "需复核",
                    "type": "OCR异常",
                    "options": [
                        f"尺寸：{analysis.get('width')} x {analysis.get('height')}",
                        f"深色像素占比：{analysis.get('dark_ratio')}%",
                    ],
                }
            )

    rows.append(
        {
            "id": len(rows) + 1,
            "taskId": task_id,
            "question": "整批问卷识别摘要",
            "answer": f"共识别 {sum(len(item.get('ocr', {}).get('items', [])) for item in file_results)} 段文字，检测 {sum(len(item.get('checkboxes', [])) for item in file_results)} 个候选选项框",
            "confidence": 88,
            "status": "待确认",
            "type": "批量摘要",
            "options": ["请在右侧人工校正题目文本、答案和备注。"],
        }
    )
    return rows


def build_lightweight_rows(task_id: str, file_results: list[dict[str, Any]], error: str = "") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, result in enumerate(file_results, start=1):
        analysis = result.get("analysis", {})
        boxes = result.get("checkboxes", [])
        rows.append(
            {
                "id": len(rows) + 1,
                "taskId": task_id,
                "question": f"图片 {index} 基础识别结果",
                "answer": f"检测到 {len(boxes)} 个候选选项框",
                "confidence": int(analysis.get("confidence") or 70),
                "status": "待确认" if boxes else "需复核",
                "type": "轻量图像分析",
                "options": [
                    f"尺寸：{analysis.get('width')} x {analysis.get('height')}",
                    f"深色像素占比：{analysis.get('dark_ratio')}%",
                    error or "OCR模型未启用，已完成基础图像分析。",
                ],
            }
        )
    return rows


def llm_enabled() -> bool:
    return bool(LLM_API_KEY and LLM_MODEL)


def compact_file_results(file_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact = []
    for index, result in enumerate(file_results, start=1):
        ocr = result.get("ocr", {})
        compact.append(
            {
                "imageIndex": index,
                "analysis": result.get("analysis", {}),
                "ocrEngine": ocr.get("engine", ""),
                "ocrText": ocr.get("text", "")[:6000],
                "ocrItems": [
                    {
                        "text": item.get("text"),
                        "confidence": item.get("confidence"),
                        "rect": item.get("rect"),
                    }
                    for item in ocr.get("items", [])[:120]
                ],
                "checkboxes": result.get("checkboxes", [])[:120],
            }
        )
    return compact


def normalize_llm_rows(task_id: str, data: Any) -> list[dict[str, Any]]:
    rows_source = data.get("rows", data) if isinstance(data, dict) else data
    if not isinstance(rows_source, list):
        raise ValueError("大模型返回内容不是数组")

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(rows_source, start=1):
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or item.get("题目") or "").strip()
        answer = str(item.get("answer") or item.get("答案") or "").strip()
        if not question and not answer:
            continue
        options = item.get("options") or item.get("选项") or []
        if not isinstance(options, list):
            options = [str(options)]
        confidence = item.get("confidence") or item.get("置信度") or 80
        try:
            confidence = int(float(confidence))
        except (TypeError, ValueError):
            confidence = 80
        rows.append(
            {
                "id": index,
                "taskId": task_id,
                "question": question or f"题目 {index}",
                "answer": answer or "请人工确认",
                "confidence": max(1, min(99, confidence)),
                "status": str(item.get("status") or item.get("状态") or "待确认"),
                "type": str(item.get("type") or item.get("题型") or "大模型解析"),
                "options": [str(option) for option in options[:20]],
                "source": "llm",
            }
        )
    if not rows:
        raise ValueError("大模型未返回有效题目")
    return rows


def extract_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def enhance_rows_with_llm(task_id: str, file_results: list[dict[str, Any]], fallback_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    if not llm_enabled():
        return fallback_rows, "大模型未配置"

    payload = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是问卷识别结果结构化解析助手。你只能返回JSON，不要返回Markdown。"
                    "根据OCR文本、文字坐标、候选勾选框和规则解析结果，整理出问卷题目、题型、选项和答案。"
                    "如果无法确定答案，answer写“请人工确认”，status写“待确认”或“需复核”。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "schema": {
                            "rows": [
                                {
                                    "question": "题目内容",
                                    "answer": "识别答案",
                                    "confidence": 1,
                                    "status": "待确认",
                                    "type": "单选题/多选题/填空题/OCR文本",
                                    "options": ["选项A", "选项B"],
                                }
                            ]
                        },
                        "ocrAndCheckboxData": compact_file_results(file_results),
                        "ruleRows": fallback_rows,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        rows = normalize_llm_rows(task_id, extract_json_object(content))
        return rows, "大模型结构化增强完成"
    except (urllib.error.URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
        return fallback_rows, f"大模型增强失败，已保留规则解析结果：{exc}"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "name": "问卷图像识别与数据导出系统 V1.0",
        "paddleocrInstalled": PaddleOCR is not None,
        "paddleInstalled": paddle is not None,
        "easyocrInstalled": easyocr is not None,
        "opencvInstalled": cv2 is not None,
        "llmEnabled": llm_enabled(),
        "llmBaseUrl": LLM_BASE_URL if llm_enabled() else "",
        "llmModel": LLM_MODEL if llm_enabled() else "",
    }


@app.post("/api/tasks")
async def create_task(files: list[UploadFile] = File(...)) -> dict[str, Any]:
    task_id = f"TASK-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    task_name = Path(files[0].filename or "问卷图片").stem
    saved_files = []
    file_results = []
    mode = "ocr"
    mode_error = ""

    for index, upload in enumerate(files):
        suffix = Path(upload.filename or "").suffix.lower() or ".jpg"
        filename = f"{task_id}_{index + 1}{suffix}"
        target = UPLOAD_DIR / filename
        content = await upload.read()
        target.write_bytes(content)

        analysis = analyze_image(target)
        checkboxes = detect_checkboxes(target)
        result: dict[str, Any] = {"analysis": analysis, "checkboxes": checkboxes}
        try:
            result["ocr"] = run_best_ocr(target)
        except Exception as exc:  # noqa: BLE001 - OCR engines fail for environment/model reasons.
            mode = "lightweight"
            mode_error = f"OCR模型暂不可用：{exc}"
            result["ocrError"] = mode_error

        file_results.append(result)
        saved_files.append(
            {
                "id": f"{task_id}-{index + 1}",
                "name": upload.filename,
                "size": f"{len(content) / 1024 / 1024:.2f} MB",
                "status": f"{result.get('ocr', {}).get('engine', 'OCR')}识别完成" if mode == "ocr" else "轻量识别完成",
                "progress": 100,
                "path": str(target),
                "analysis": analysis,
                "checkboxes": checkboxes,
                "ocrText": result.get("ocr", {}).get("text", ""),
                "ocrError": result.get("ocrError", ""),
            }
        )

    rule_results = build_ocr_rows(task_id, file_results) if mode == "ocr" else build_lightweight_rows(task_id, file_results, mode_error)
    results, llm_message = enhance_rows_with_llm(task_id, file_results, rule_results)
    llm_used = any(row.get("source") == "llm" for row in results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "大模型增强完成" if llm_used else ("OCR识别完成" if mode == "ocr" else "轻量识别完成")
    with connect() as db:
        db.execute(
            "INSERT INTO tasks (id, name, created_at, file_count, status) VALUES (?, ?, ?, ?, ?)",
            (task_id, task_name, now, len(saved_files), status),
        )
        db.executemany(
            """
            INSERT INTO results (task_id, question_no, question, answer, confidence, status, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    task_id,
                    row["id"],
                    row["question"],
                    row["answer"],
                    row["confidence"],
                    row["status"],
                    json.dumps(row, ensure_ascii=False),
                )
                for row in results
            ],
        )

    return {
        "task": {
            "id": task_id,
            "name": task_name,
            "createdAt": now,
            "status": status,
            "mode": mode,
            "modeError": mode_error,
            "llmEnabled": llm_enabled(),
            "llmUsed": llm_used,
            "llmMessage": llm_message,
            "files": saved_files,
        },
        "results": results,
    }


@app.get("/api/tasks")
def list_tasks() -> dict[str, Any]:
    init_db()
    with connect() as db:
        rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    return {"tasks": [dict(row) for row in rows]}


@app.post("/api/export")
def export_excel(payload: ExportPayload) -> StreamingResponse:
    if Workbook is None:
        csv = "题号,题目,答案,置信度,状态\n" + "\n".join(
            f'{row.get("id")},"{row.get("question")}","{row.get("answer")}",{row.get("confidence")},{row.get("status")}'
            for row in payload.rows
        )
        return StreamingResponse(
            BytesIO(csv.encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{payload.taskId}.csv"'},
        )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "识别结果"
    sheet.append(["任务ID", "题号", "题目内容", "识别答案", "置信度", "处理状态", "题型"])
    for row in payload.rows:
        sheet.append(
            [
                payload.taskId,
                row.get("id"),
                row.get("question"),
                row.get("answer"),
                row.get("confidence"),
                row.get("status"),
                row.get("type"),
            ]
        )

    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max(max_length + 4, 12), 48)

    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{payload.taskId}.xlsx"'},
    )
