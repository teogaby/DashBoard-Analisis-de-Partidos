"""Aplicación Streamlit para tracking de jugadores con YOLO + ByteTrack.

Enfoque de esta versión:
- Mejorar estabilidad de disco/memoria para pruebas continuas.
- Mantener tracking/métricas existentes sin cambios funcionales.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st

from metrics import compute_metrics
from tracker import process_video

# -----------------------------
# Configuración de rutas
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
CACHE_DIR = BASE_DIR / "cache"
SAMPLE_DIR = BASE_DIR / "sample_data"

for folder in [UPLOADS_DIR, OUTPUTS_DIR, CACHE_DIR, SAMPLE_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Logging básico
# -----------------------------
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
    video_ext = {".mp4", ".mov", ".avi", ".mkv"}
    videos = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in video_ext]
    videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in videos[n:]:
        old.unlink(missing_ok=True)


def system_status() -> dict:
    uploads_files = [f for f in UPLOADS_DIR.iterdir() if f.is_file()]
    outputs_files = [f for f in OUTPUTS_DIR.iterdir() if f.is_file()]
    cache_files = [f for f in CACHE_DIR.iterdir() if f.is_file()]

    uploads_size = folder_size_bytes(UPLOADS_DIR)
    outputs_size = folder_size_bytes(OUTPUTS_DIR)
    cache_size = folder_size_bytes(CACHE_DIR)
    total_size = uploads_size + outputs_size + cache_size

    return {
        "temp_files_count": len(uploads_files) + len(outputs_files) + len(cache_files),
        "uploads_size_mb": uploads_size / (1024 * 1024),
        "outputs_size_mb": outputs_size / (1024 * 1024),
        "cache_size_mb": cache_size / (1024 * 1024),
        "total_used_mb": total_size / (1024 * 1024),
    }


def get_video_duration_seconds(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError("No se pudo abrir el vídeo para calcular duración.")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    cap.release()
    return (frames / fps) if fps > 0 else 0.0


def save_uploaded_file_in_chunks(uploaded_file, dst_path: Path, chunk_size: int = 1024 * 1024) -> None:
    """Guarda subida en bloques binarios para reducir pico de memoria."""
    uploaded_file.seek(0)
    with open(dst_path, "wb") as out:
        while True:
            data = uploaded_file.read(chunk_size)
            if not data:
                break
            out.write(data)


st.set_page_config(page_title="Football Player Tracking Prototype", layout="wide")
st.title("⚽ Football Player Tracking Prototype")
st.caption("YOLO (Ultralytics) + ByteTrack/BotSort + OpenCV + Streamlit")

with st.sidebar:
    st.header("Configuración")
    model_name = st.selectbox("Modelo YOLO", ["yolov8n.pt", "yolov8s.pt"], index=0)
    conf = st.slider("Confianza mínima", min_value=0.1, max_value=0.9, value=0.35, step=0.05)
    tracker_cfg = st.selectbox("Tracker", ["bytetrack.yaml", "botsort.yaml"], index=0)

    if st.button("Limpiar archivos temporales"):
        try:
            remove_files_in_folder(UPLOADS_DIR)
            remove_files_in_folder(OUTPUTS_DIR)
            remove_files_in_folder(CACHE_DIR)
            st.success("Limpieza completada: uploads/, outputs/ y cache/ vaciados.")
            logger.info("limpieza completada")
        except (OSError, FileNotFoundError, MemoryError) as exc:
            st.error(f"Error limpiando archivos temporales: {exc}")

status = system_status()
st.subheader("Estado del sistema")
st.write(f"Espacio estimado usado: **{status['total_used_mb']:.2f} MB**")
st.write(f"Número de vídeos/archivos temporales: **{status['temp_files_count']}**")
st.write(f"Tamaño total de outputs/: **{status['outputs_size_mb']:.2f} MB**")
logger.info("espacio estimado usado %.2f MB", status["total_used_mb"])

uploaded_file = st.file_uploader("Sube un vídeo (MP4, MOV, AVI)", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    try:
        # Limpiar uploads para mantener sólo último vídeo.
        remove_files_in_folder(UPLOADS_DIR)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        input_path = UPLOADS_DIR / f"{timestamp}_{uploaded_file.name}"
        save_uploaded_file_in_chunks(uploaded_file, input_path)
        keep_only_latest_file(UPLOADS_DIR)

        file_size_mb = input_path.stat().st_size / (1024 * 1024)
        duration_sec = get_video_duration_seconds(input_path)
        duration_min = duration_sec / 60

        logger.info("vídeo cargado: %s", uploaded_file.name)
        logger.info("vídeo guardado: %s", input_path)

        st.success(f"Vídeo guardado en: {input_path}")
        st.write(f"Tamaño del vídeo: **{file_size_mb:.2f} MB**")
        st.write(f"Duración aproximada: **{duration_min:.2f} minutos**")
        st.video(str(input_path))

        too_big = file_size_mb > 500
        too_long = duration_min > 10

        if too_big or too_long:
            st.warning(
                "El vídeo supera límites recomendados (500 MB o 10 minutos). "
                "Puedes cancelar para evitar errores de recursos."
            )
            proceed = st.checkbox("Aun así, quiero procesar este vídeo", value=False)
        else:
            proceed = True

        if st.button("Procesar vídeo", type="primary", disabled=not proceed):
            out_video = OUTPUTS_DIR / f"tracked_{input_path.stem}.mp4"
            out_csv = OUTPUTS_DIR / f"tracking_{input_path.stem}.csv"
            out_metrics = OUTPUTS_DIR / f"metrics_{input_path.stem}.csv"

            progress = st.progress(0.0, text="Procesando vídeo...")

            def _update_progress(v: float):
                progress.progress(max(0.0, min(v, 1.0)), text=f"Procesando vídeo... {int(v * 100)}%")

            with st.spinner("Ejecutando detección + tracking..."):
                final_video_path, final_csv_path = process_video(
                    input_video=str(input_path),
                    output_video=str(out_video),
                    output_csv=str(out_csv),
                    model_name=model_name,
                    conf=conf,
                    tracker_cfg=tracker_cfg,
                    progress_callback=_update_progress,
                )

                metrics_df = compute_metrics(final_csv_path)
                metrics_df.to_csv(out_metrics, index=False)

            # Mantener sólo últimos 3 vídeos procesados en outputs.
            keep_latest_n_videos(OUTPUTS_DIR, n=3)

            progress.progress(1.0, text="Procesamiento completado ✅")
            st.success("Procesamiento completado correctamente.")
            logger.info("vídeo procesado: %s", final_video_path)

            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("Vídeo procesado")
                st.video(final_video_path)
            with col2:
                st.subheader("Métricas por track_id")
                st.dataframe(metrics_df, use_container_width=True)

            with open(final_csv_path, "rb") as f:
                st.download_button("Descargar CSV de detecciones", data=f, file_name=Path(final_csv_path).name, mime="text/csv")

            with open(out_metrics, "rb") as f:
                st.download_button("Descargar CSV de métricas", data=f, file_name=out_metrics.name, mime="text/csv")

            with open(final_video_path, "rb") as f:
                st.download_button("Descargar vídeo procesado", data=f, file_name=Path(final_video_path).name, mime="video/mp4")

    except OSError as exc:
        st.error(f"Error de disco/archivo (OSError): {exc}")
    except MemoryError as exc:
        st.error(f"Error de memoria durante la operación: {exc}")
    except FileNotFoundError as exc:
        st.error(f"Archivo no encontrado: {exc}")
    except Exception as exc:
        st.error(f"Error durante el procesamiento: {exc}")
else:
    st.info("Sube un vídeo para comenzar.")
