"""Aplicación Streamlit para tracking de jugadores con YOLO + ByteTrack estable."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st

from metrics import compute_metrics
from tracker import process_video

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = BASE_DIR / "cache"
SAMPLE_DIR = BASE_DIR / "sample_data"
TRACKER_YAML = BASE_DIR / "bytetrack_custom.yaml"

for folder in [UPLOADS_DIR, OUTPUTS_DIR, CACHE_DIR, SAMPLE_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("tracking_app")


def folder_size_bytes(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.glob("**/*") if f.is_file())


def remove_files_in_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for f in folder.glob("**/*"):
        if f.is_file():
            f.unlink(missing_ok=True)


def keep_only_latest_file(folder: Path) -> None:
    files = [f for f in folder.iterdir() if f.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[1:]:
        old.unlink(missing_ok=True)


def keep_latest_n_videos(folder: Path, n: int = 3) -> None:
    videos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}]
    videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in videos[n:]:
        old.unlink(missing_ok=True)


def get_video_duration_seconds(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError("No se pudo abrir el vídeo para calcular duración.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    cap.release()
    return (frames / fps) if fps > 0 else 0.0


def save_uploaded_file_in_chunks(uploaded_file, dst_path: Path, chunk_size: int = 1024 * 1024) -> None:
    uploaded_file.seek(0)
    with open(dst_path, "wb") as out:
        while True:
            data = uploaded_file.read(chunk_size)
            if not data:
                break
            out.write(data)


st.set_page_config(page_title="Football Player Tracking Prototype", layout="wide")
st.title("⚽ Football Player Tracking Prototype")
st.caption("YOLO (Ultralytics) + ByteTrack + OpenCV + Streamlit")

with st.sidebar:
    st.header("Configuración")
    model_name = st.selectbox("Modelo YOLO", ["yolov8n.pt", "yolov8s.pt"], index=0)
    conf = st.slider("Confianza mínima", min_value=0.1, max_value=0.9, value=0.35, step=0.05)
    st.success("Tracker fijo: ByteTrack (bytetrack_custom.yaml)")
    st.caption("No se usa BoT-SORT en esta versión por estabilidad/compatibilidad.")

    if st.button("Limpiar archivos temporales"):
        remove_files_in_folder(UPLOADS_DIR)
        remove_files_in_folder(OUTPUTS_DIR)
        remove_files_in_folder(CACHE_DIR)
        st.success("Limpieza completada.")
        logger.info("limpieza completada")

used_mb = (folder_size_bytes(UPLOADS_DIR) + folder_size_bytes(OUTPUTS_DIR) + folder_size_bytes(CACHE_DIR)) / (1024 * 1024)
st.subheader("Estado del sistema")
st.write(f"Espacio estimado usado: **{used_mb:.2f} MB**")

uploaded_file = st.file_uploader("Sube un vídeo (MP4, MOV, AVI)", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    try:
        remove_files_in_folder(UPLOADS_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_path = UPLOADS_DIR / f"{timestamp}_{uploaded_file.name}"
        save_uploaded_file_in_chunks(uploaded_file, input_path)
        keep_only_latest_file(UPLOADS_DIR)

        size_mb = input_path.stat().st_size / (1024 * 1024)
        duration_min = get_video_duration_seconds(input_path) / 60
        st.write(f"Tamaño: **{size_mb:.2f} MB** | Duración: **{duration_min:.2f} min**")
        st.video(str(input_path))

        proceed = True
        if size_mb > 500 or duration_min > 10:
            st.warning("Vídeo grande/largo. Puedes cancelar procesamiento.")
            proceed = st.checkbox("Confirmo procesar igualmente", value=False)

        if st.button("Procesar vídeo", type="primary", disabled=not proceed):
            if not TRACKER_YAML.exists():
                raise FileNotFoundError("Error cargando configuración del tracker")

            # Se usa YAML local del proyecto para evitar incompatibilidades de versión
            # y NO tocar default.yaml interno de ultralytics/site-packages.
            tracker_cfg_used = OUTPUTS_DIR / "tracker_config_used.yaml"
            tracker_cfg_used.write_text(TRACKER_YAML.read_text())
            logger.info("tracker cargado")
            logger.info("configuración tracker usada: %s", tracker_cfg_used)

            out_video = OUTPUTS_DIR / f"tracked_{input_path.stem}.mp4"
            out_csv = OUTPUTS_DIR / f"tracking_{input_path.stem}.csv"
            out_metrics = OUTPUTS_DIR / f"metrics_{input_path.stem}.csv"

            progress = st.progress(0.0, text="Procesando vídeo...")

            def _update(v: float):
                progress.progress(max(0.0, min(v, 1.0)), text=f"Procesando vídeo... {int(v*100)}%")

            final_video_path, final_csv_path = process_video(
                input_video=str(input_path),
                output_video=str(out_video),
                output_csv=str(out_csv),
                model_name=model_name,
                conf=conf,
                tracker_cfg=str(TRACKER_YAML),
                progress_callback=_update,
            )

            metrics_df = compute_metrics(final_csv_path)
            metrics_df.to_csv(out_metrics, index=False)
            keep_latest_n_videos(OUTPUTS_DIR, 3)

            st.success("Procesamiento completado.")
            st.video(final_video_path)
            st.dataframe(metrics_df, use_container_width=True)

    except (OSError, MemoryError, FileNotFoundError) as exc:
        msg = str(exc)
        if "tracker" in msg.lower() or "yaml" in msg.lower():
            st.error("Error cargando configuración del tracker")
            logger.error("errores de tracking: %s", exc)
        else:
            st.error(f"Error: {exc}")
else:
    st.info("Sube un vídeo para comenzar.")
