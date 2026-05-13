"""Tracking YOLO + ByteTrack con configuración YAML local estable."""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import pandas as pd
from ultralytics import YOLO

logger = logging.getLogger("tracker")


def _color_for_id(track_id: int) -> Tuple[int, int, int]:
    return ((37 * track_id) % 255, (17 * track_id + 99) % 255, (29 * track_id + 171) % 255)


def process_video(input_video: str, output_video: str, output_csv: str, model_name: str = "yolov8n.pt", conf: float = 0.35, tracker_cfg: str = "bytetrack_custom.yaml", progress_callback=None) -> Tuple[str, str]:
    input_path = Path(input_video)
    output_video_path = Path(output_video)
    output_csv_path = Path(output_csv)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    if not Path(tracker_cfg).exists():
        raise FileNotFoundError("Error cargando configuración del tracker")

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir el vídeo de entrada.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(output_video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    model = YOLO(model_name)

    rows: List[dict] = []
    frame_idx = 0
    history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=30))

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        try:
            result_list = model.track(source=frame, conf=conf, classes=[0], tracker=tracker_cfg, persist=True, verbose=False)
        except Exception as exc:
            logger.error("errores de tracking: %s", exc)
            raise RuntimeError("Error cargando configuración del tracker") from exc

        annotated = frame.copy()
        active_tracks = 0
        if result_list:
            result = result_list[0]
            boxes = result.boxes
            if boxes is not None and boxes.xyxy is not None and len(boxes) > 0:
                xyxy = boxes.xyxy.cpu().numpy()
                confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
                clss = boxes.cls.cpu().numpy() if boxes.cls is not None else []
                ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [-1] * len(xyxy)
                active_tracks = len(xyxy)

                for i, box in enumerate(xyxy):
                    x1, y1, x2, y2 = map(float, box)
                    track_id = int(ids[i]) if i < len(ids) else -1
                    conf_val = float(confs[i]) if i < len(confs) else 0.0
                    cls_idx = int(clss[i]) if i < len(clss) else 0
                    class_name = result.names.get(cls_idx, "person")
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    rows.append({"frame_number": frame_idx, "timestamp_seconds": frame_idx / fps, "track_id": track_id, "class_name": class_name, "confidence": conf_val, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "center_x": cx, "center_y": cy})

                    color = _color_for_id(max(track_id, 0))
                    cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
                    cv2.putText(annotated, f"ID {track_id} {conf_val:.2f}", (int(x1), max(18, int(y1) - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
                    history[track_id].append((int(cx), int(cy)))
                    for j in range(1, len(history[track_id])):
                        cv2.line(annotated, history[track_id][j - 1], history[track_id][j], color, 2)

        logger.info("número de tracks activos: %s", active_tracks)
        writer.write(annotated)
        frame_idx += 1
        if progress_callback and total_frames > 0:
            progress_callback(min(frame_idx / total_frames, 1.0))

    cap.release()
    writer.release()
    pd.DataFrame(rows).to_csv(output_csv_path, index=False)
    return str(output_video_path), str(output_csv_path)
