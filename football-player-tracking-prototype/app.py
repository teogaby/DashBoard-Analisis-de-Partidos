from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
import cv2
import streamlit as st
from metrics import compute_metrics
from tracker import process_video

BASE_DIR = Path(__file__).resolve().parent
UPLOADS_DIR, OUTPUTS_DIR, CACHE_DIR = BASE_DIR / "uploads", BASE_DIR / "outputs", BASE_DIR / "cache"
for d in [UPLOADS_DIR, OUTPUTS_DIR, CACHE_DIR, BASE_DIR / "sample_data"]: d.mkdir(parents=True, exist_ok=True)

PRESETS = {
    "conservador": BASE_DIR / "bytetrack_conservative.yaml",
    "equilibrado": BASE_DIR / "bytetrack_balanced.yaml",
    "agresivo": BASE_DIR / "bytetrack_aggressive.yaml",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("tracking_app")


def save_uploaded_file_in_chunks(uploaded_file, dst_path: Path, chunk_size: int = 1024 * 1024):
    uploaded_file.seek(0)
    with open(dst_path, "wb") as out:
        while True:
            c = uploaded_file.read(chunk_size)
            if not c: break
            out.write(c)


def remove_files_in_folder(folder: Path):
    for f in folder.glob("**/*"):
        if f.is_file(): f.unlink(missing_ok=True)


def keep_latest_n_videos(folder: Path, n=3):
    vids=[f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in {'.mp4','.mov','.avi','.mkv'}]
    vids.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in vids[n:]: old.unlink(missing_ok=True)


def get_video_duration_minutes(video_path: Path) -> float:
    cap=cv2.VideoCapture(str(video_path)); fps=cap.get(cv2.CAP_PROP_FPS) or 0; frames=cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0; cap.release()
    return (frames/fps/60) if fps>0 else 0.0


def load_yaml_values(path: Path):
    vals={}
    for line in path.read_text().splitlines():
        if ":" in line:
            k,v=line.split(":",1); vals[k.strip()]=v.strip()
    return vals


def write_runtime_tracker_yaml(path: Path, th, tl, nt, buf, mt):
    path.write_text(f"""tracker_type: bytetrack
track_high_thresh: {th}
track_low_thresh: {tl}
new_track_thresh: {nt}
track_buffer: {buf}
match_thresh: {mt}
fuse_score: true
""")


st.set_page_config(page_title="Football Player Tracking Prototype", layout="wide")
st.title("⚽ Football Player Tracking Prototype")

with st.sidebar:
    model_name=st.selectbox("Modelo YOLO", ["yolov8n.pt","yolov8s.pt"], index=0)
    conf=st.slider("Confianza mínima",0.1,0.9,0.35,0.05)
    preset=st.selectbox("Preset ByteTrack", ["conservador","equilibrado","agresivo"], index=1)
    pv=load_yaml_values(PRESETS[preset])
    track_high_thresh=st.slider("track_high_thresh",0.1,0.9,float(pv["track_high_thresh"]),0.05)
    track_low_thresh=st.slider("track_low_thresh",0.01,0.5,float(pv["track_low_thresh"]),0.01)
    new_track_thresh=st.slider("new_track_thresh",0.1,0.95,float(pv["new_track_thresh"]),0.05)
    track_buffer=st.slider("track_buffer",10,200,int(float(pv["track_buffer"])),5)
    match_thresh=st.slider("match_thresh",0.1,0.95,float(pv["match_thresh"]),0.05)

uploaded=st.file_uploader("Sube vídeo", type=["mp4","mov","avi"])
if uploaded:
    remove_files_in_folder(UPLOADS_DIR)
    in_path=UPLOADS_DIR/f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
    save_uploaded_file_in_chunks(uploaded, in_path)
    size_mb=in_path.stat().st_size/(1024*1024)
    dur_min=get_video_duration_minutes(in_path)
    st.write(f"Tamaño: **{size_mb:.2f} MB** | Duración: **{dur_min:.2f} min**")
    st.video(str(in_path))
    proceed=True
    if size_mb>500 or dur_min>10:
        st.warning("Vídeo grande/largo")
        proceed=st.checkbox("Procesar igualmente", value=False)

    if st.button("Procesar vídeo", disabled=not proceed, type="primary"):
        runtime_yaml=OUTPUTS_DIR/"tracker_config_used.yaml"
        write_runtime_tracker_yaml(runtime_yaml, track_high_thresh, track_low_thresh, new_track_thresh, track_buffer, match_thresh)
        logger.info("tracker cargado")
        logger.info("configuración tracker usada: %s", runtime_yaml)
        progress=st.progress(0.0, text="Procesando...")
        out_video=OUTPUTS_DIR/f"tracked_{in_path.stem}.mp4"
        out_csv=OUTPUTS_DIR/f"tracking_{in_path.stem}.csv"
        out_metrics=OUTPUTS_DIR/f"metrics_{in_path.stem}.csv"

        try:
            v,csv=process_video(str(in_path), str(out_video), str(out_csv), model_name=model_name, conf=conf, tracker_cfg=str(runtime_yaml), progress_callback=lambda p: progress.progress(p, text=f"Procesando... {int(p*100)}%"))
            m=compute_metrics(csv); m.to_csv(out_metrics,index=False)
            keep_latest_n_videos(OUTPUTS_DIR,3)
            st.success("Procesado completado")
            st.video(v); st.dataframe(m, use_container_width=True)
        except Exception as exc:
            st.error("Error cargando configuración del tracker" if "tracker" in str(exc).lower() else str(exc))
            logger.error("errores de tracking: %s", exc)
else:
    st.info("Sube un vídeo para comenzar")
