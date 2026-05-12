"""Módulo de tracking con Ultralytics YOLO + ByteTrack/BotSort.

Este módulo se encarga de:
1) Cargar un modelo YOLO.
2) Recorrer un vídeo frame a frame usando model.track(persist=True).
3) Anotar cajas, IDs y trayectoria corta por track_id.
4) Guardar vídeo anotado + CSV de detecciones por frame.
"""

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import pandas as pd
from ultralytics import YOLO


def _color_for_id(track_id: int) -> Tuple[int, int, int]:
    """Genera un color BGR estable por track_id para visualizar IDs."""
    return (
        (37 * track_id) % 255,
        (17 * track_id + 99) % 255,
        (29 * track_id + 171) % 255,
    )


def process_video(
    input_video: str,
    output_video: str,
    output_csv: str,
    model_name: str = "yolov8n.pt",
    conf: float = 0.35,
    tracker_cfg: str = "bytetrack.yaml",
    progress_callback=None,
) -> Tuple[str, str]:
    """Procesa un vídeo con YOLO tracking y guarda vídeo anotado + CSV.

    Args:
        input_video: Ruta del vídeo original.
        output_video: Ruta del vídeo anotado.
        output_csv: Ruta del CSV con detecciones.
        model_name: Modelo YOLO a cargar.
        conf: Umbral de confianza.
        tracker_cfg: Config del tracker (bytetrack.yaml o botsort.yaml).
        progress_callback: Función opcional para actualizar barra de progreso.

    Returns:
        (ruta_video_anotado, ruta_csv_detecciones)
    """
    input_path = Path(input_video)
    output_video_path = Path(output_video)
    output_csv_path = Path(output_csv)

    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir el vídeo de entrada.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("No se pudo crear el vídeo de salida.")

    model = YOLO(model_name)

    track_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
    rows: List[dict] = []
    frame_idx = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # Tracking por frame con persist=True para mantener identidad de IDs.
            result_list = model.track(
                source=frame,
                conf=conf,
                classes=[0],  # clase 0 en COCO = person
                tracker=tracker_cfg,
                persist=True,
                verbose=False,
            )

            annotated = frame.copy()
            if result_list:
                result = result_list[0]
                boxes = result.boxes

                if boxes is not None and boxes.xyxy is not None and len(boxes) > 0:
                    xyxy = boxes.xyxy.cpu().numpy()
                    confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
                    clss = boxes.cls.cpu().numpy() if boxes.cls is not None else []
                    ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else [-1] * len(xyxy)

                    for i, box in enumerate(xyxy):
                        x1, y1, x2, y2 = map(float, box)
                        track_id = int(ids[i]) if i < len(ids) else -1
                        conf_val = float(confs[i]) if i < len(confs) else 0.0
                        cls_idx = int(clss[i]) if i < len(clss) else 0
                        class_name = result.names.get(cls_idx, "person")

                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        timestamp = frame_idx / fps

                        rows.append(
                            {
                                "frame_number": frame_idx,
                                "timestamp_seconds": timestamp,
                                "track_id": track_id,
                                "class_name": class_name,
                                "confidence": conf_val,
                                "x1": x1,
                                "y1": y1,
                                "x2": x2,
                                "y2": y2,
                                "center_x": center_x,
                                "center_y": center_y,
                            }
                        )

                        color = _color_for_id(max(track_id, 0))
                        pt1, pt2 = (int(x1), int(y1)), (int(x2), int(y2))
                        cv2.rectangle(annotated, pt1, pt2, color, 2)
                        cv2.putText(
                            annotated,
                            f"ID {track_id} {conf_val:.2f}",
                            (int(x1), max(18, int(y1) - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.55,
                            color,
                            2,
                            cv2.LINE_AA,
                        )

                        # Trayectoria corta por track_id.
                        history = track_history[track_id]
                        history.append((int(center_x), int(center_y)))
                        for j in range(1, len(history)):
                            cv2.line(annotated, history[j - 1], history[j], color, 2)

            writer.write(annotated)
            frame_idx += 1

            if progress_callback and total_frames > 0:
                progress_callback(min(frame_idx / total_frames, 1.0))

    finally:
        cap.release()
        writer.release()

    df = pd.DataFrame(rows)
    df.to_csv(output_csv_path, index=False)

    return str(output_video_path), str(output_csv_path)
