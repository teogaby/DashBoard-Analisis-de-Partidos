"""Aplicación Streamlit para tracking de jugadores con YOLO + ByteTrack."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from metrics import compute_metrics
from tracker import process_video

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR = BASE_DIR / "uploads"
OUTPUTS_DIR = BASE_DIR / "outputs"
SAMPLE_DIR = BASE_DIR / "sample_data"

for folder in [UPLOADS_DIR, OUTPUTS_DIR, SAMPLE_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Football Player Tracking Prototype", layout="wide")
st.title("⚽ Football Player Tracking Prototype")
st.caption("YOLO (Ultralytics) + ByteTrack/BotSort + OpenCV + Streamlit")

with st.sidebar:
    st.header("Configuración")
    model_name = st.selectbox("Modelo YOLO", ["yolov8n.pt", "yolov8s.pt"], index=0)
    conf = st.slider("Confianza mínima", min_value=0.1, max_value=0.9, value=0.35, step=0.05)
    tracker_cfg = st.selectbox("Tracker", ["bytetrack.yaml", "botsort.yaml"], index=0)

uploaded_file = st.file_uploader("Sube un vídeo (MP4, MOV, AVI)", type=["mp4", "mov", "avi"])

if uploaded_file is not None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_path = UPLOADS_DIR / f"{timestamp}_{uploaded_file.name}"
    input_path.write_bytes(uploaded_file.read())
    st.success(f"Vídeo guardado en: {input_path}")

    st.video(str(input_path))

    if st.button("Procesar vídeo", type="primary"):
        try:
            out_video = OUTPUTS_DIR / f"tracked_{input_path.stem}.mp4"
            out_csv = OUTPUTS_DIR / f"tracking_{input_path.stem}.csv"
            out_metrics = OUTPUTS_DIR / f"metrics_{input_path.stem}.csv"

            progress = st.progress(0.0, text="Procesando vídeo...")

            def _update_progress(v: float):
                progress.progress(v, text=f"Procesando vídeo... {int(v * 100)}%")

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

            progress.progress(1.0, text="Procesamiento completado ✅")
            st.success("Procesamiento completado correctamente.")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("Vídeo procesado")
                st.video(final_video_path)
            with col2:
                st.subheader("Métricas por track_id")
                st.dataframe(metrics_df, use_container_width=True)

            with open(final_csv_path, "rb") as f:
                st.download_button(
                    "Descargar CSV de detecciones",
                    data=f,
                    file_name=Path(final_csv_path).name,
                    mime="text/csv",
                )

            with open(out_metrics, "rb") as f:
                st.download_button(
                    "Descargar CSV de métricas",
                    data=f,
                    file_name=out_metrics.name,
                    mime="text/csv",
                )

            with open(final_video_path, "rb") as f:
                st.download_button(
                    "Descargar vídeo procesado",
                    data=f,
                    file_name=Path(final_video_path).name,
                    mime="video/mp4",
                )

        except Exception as exc:
            st.error(f"Error durante el procesamiento: {exc}")
            st.info(
                "Verifica que tengas instaladas las dependencias y que el vídeo no esté corrupto. "
                "Si falta el modelo, Ultralytics lo descargará automáticamente."
            )
else:
    st.info("Sube un vídeo para comenzar.")
