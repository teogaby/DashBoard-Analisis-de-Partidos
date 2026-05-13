"""Dashboard profesional para análisis de tracking YOLO + ByteTrack."""

from __future__ import annotations

import io
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

REQUIRED_TRACK_COLS = {
    "frame_number",
    "timestamp_seconds",
    "track_id",
    "class_name",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
    "center_x",
    "center_y",
}
REQUIRED_METRIC_COLS = {
    "track_id",
    "frames_detectados",
    "tiempo_visible_segundos",
    "distancia_pixeles_aproximada",
    "velocidad_media_pixeles_segundo",
    "primera_aparicion",
    "ultima_aparicion",
}


@st.cache_data(show_spinner=False)
def load_csv(uploaded_file) -> pd.DataFrame:
    return pd.read_csv(uploaded_file)


@st.cache_data(show_spinner=False)
def load_mapping(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=["track_id", "nombre", "dorsal", "equipo", "posicion"])


def validate_tracks(df: pd.DataFrame) -> list[str]:
    issues = []
    missing = REQUIRED_TRACK_COLS - set(df.columns)
    if missing:
        issues.append(f"tracks.csv: faltan columnas {sorted(missing)}")
    if "track_id" in df.columns and (df["track_id"].isna().any() or (df["track_id"] < 0).any()):
        issues.append("tracks.csv: track_id inválidos detectados (NaN o negativos).")
    if df.empty:
        issues.append("tracks.csv está vacío.")
    return issues


def validate_metrics(df: pd.DataFrame) -> list[str]:
    issues = []
    missing = REQUIRED_METRIC_COLS - set(df.columns)
    if missing:
        issues.append(f"metrics.csv: faltan columnas {sorted(missing)}")
    if df.empty:
        issues.append("metrics.csv está vacío.")
    return issues


def enrich_with_mapping(metrics_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    if mapping_df.empty:
        return metrics_df.copy()
    return metrics_df.merge(mapping_df, on="track_id", how="left")


def reliability_label(row) -> str:
    if row["frames_detectados"] >= 80 and row["tiempo_visible_segundos"] >= 8:
        return "fiable"
    if row["frames_detectados"] >= 20:
        return "dudoso"
    return "perdido"


st.set_page_config(page_title="Tracking Dashboard", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background-color: #0f1419; color: #f2f7f4; }
    .block-container { padding-top: 1rem; }
    h1,h2,h3 { color: #31d66f; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("⚽ Dashboard de análisis YOLO + ByteTrack")

mapping_path = Path(__file__).resolve().parent / "player_mapping.csv"

col_u1, col_u2 = st.columns(2)
with col_u1:
    tracks_file = st.file_uploader("Cargar tracks.csv", type=["csv"])
with col_u2:
    metrics_file = st.file_uploader("Cargar metrics.csv", type=["csv"])

if not tracks_file or not metrics_file:
    st.info("Sube ambos archivos para iniciar el análisis.")
    st.stop()

tracks_df = load_csv(tracks_file)
metrics_df = load_csv(metrics_file)
issues = validate_tracks(tracks_df) + validate_metrics(metrics_df)
if issues:
    for i in issues:
        st.error(i)
    st.stop()

mapping_df = load_mapping(mapping_path)
metrics_enriched = enrich_with_mapping(metrics_df, mapping_df)
metrics_enriched["estado_tracking"] = metrics_enriched.apply(reliability_label, axis=1)

# Filtros globales
min_t, max_t = float(tracks_df["timestamp_seconds"].min()), float(tracks_df["timestamp_seconds"].max())
time_range = st.slider("Filtrar por rango temporal (s)", min_t, max_t, (min_t, max_t), step=0.1)
tracks_view = tracks_df[(tracks_df["timestamp_seconds"] >= time_range[0]) & (tracks_df["timestamp_seconds"] <= time_range[1])].copy()

traj_color = st.color_picker("Color de trayectorias", "#31d66f")
show_points = st.toggle("Mostrar puntos", value=True)

# Tabs
resumen_tab, jugadores_tab, tray_tab, heat_tab, comp_tab, exp_tab = st.tabs([
    "Resumen", "Jugadores", "Trayectorias", "Heatmaps", "Comparativas", "Exportación"
])

with resumen_tab:
    total_tracks = tracks_view["track_id"].nunique()
    duration = tracks_view["timestamp_seconds"].max() - tracks_view["timestamp_seconds"].min()
    frames = tracks_view["frame_number"].nunique()
    mean_players_frame = tracks_view.groupby("frame_number")["track_id"].nunique().mean()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Track IDs totales", int(total_tracks))
    c2.metric("Duración analizada", f"{duration:.2f} s")
    c3.metric("Frames analizados", int(frames))
    c4.metric("Jugadores medios/frame", f"{mean_players_frame:.2f}")

    st.subheader("Ranking por tiempo visible")
    st.dataframe(metrics_enriched.sort_values("tiempo_visible_segundos", ascending=False), use_container_width=True)

with jugadores_tab:
    ranking_option = st.selectbox("Ranking", [
        "tiempo_visible_segundos", "distancia_pixeles_aproximada", "velocidad_media_pixeles_segundo", "frames_detectados"
    ])
    st.dataframe(metrics_enriched.sort_values(ranking_option, ascending=False), use_container_width=True)

    selected_track = st.selectbox("Seleccionar track_id", sorted(tracks_view["track_id"].unique().tolist()))
    player_df = tracks_view[tracks_view["track_id"] == selected_track].sort_values("timestamp_seconds")

    st.write(f"Estado visual: **{metrics_enriched.set_index('track_id').loc[selected_track, 'estado_tracking']}**")

    fig_xy = px.line(player_df, x="timestamp_seconds", y=["center_x", "center_y"], title="Evolución temporal (center_x / center_y)")
    st.plotly_chart(fig_xy, use_container_width=True)

    fig_timeline = px.scatter(player_df, x="timestamp_seconds", y="frame_number", title="Timeline temporal")
    st.plotly_chart(fig_timeline, use_container_width=True)

with tray_tab:
    selected_track = st.selectbox("Track para trayectoria", sorted(tracks_view["track_id"].unique().tolist()), key="tray_track")
    player_df = tracks_view[tracks_view["track_id"] == selected_track].sort_values("timestamp_seconds")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=player_df["center_x"],
        y=player_df["center_y"],
        mode="lines+markers" if show_points else "lines",
        line=dict(color=traj_color, width=3),
        marker=dict(size=5, color=traj_color),
        name=f"track {selected_track}",
    ))
    fig.update_layout(title="Trayectoria completa", xaxis_title="X", yaxis_title="Y", yaxis_autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Mini campo simplificado")
    field = go.Figure()
    field.add_shape(type="rect", x0=0, y0=0, x1=105, y1=68, line=dict(color="white", width=2))
    x_norm = (player_df["center_x"] - player_df["center_x"].min()) / max(1e-9, (player_df["center_x"].max() - player_df["center_x"].min())) * 105
    y_norm = (player_df["center_y"] - player_df["center_y"].min()) / max(1e-9, (player_df["center_y"].max() - player_df["center_y"].min())) * 68
    field.add_trace(go.Scatter(x=x_norm, y=y_norm, mode="lines+markers" if show_points else "lines", line=dict(color=traj_color)))
    field.update_layout(height=420, paper_bgcolor="#0f1419", plot_bgcolor="#145a32", yaxis_autorange="reversed")
    st.plotly_chart(field, use_container_width=True)

with heat_tab:
    selected_track = st.selectbox("Track para heatmap", sorted(tracks_view["track_id"].unique().tolist()), key="heat_track")
    player_df = tracks_view[tracks_view["track_id"] == selected_track]

    fig_heat = px.density_heatmap(player_df, x="center_x", y="center_y", nbinsx=30, nbinsy=30, title="Heatmap aproximado")
    fig_heat.update_yaxes(autorange="reversed")
    st.plotly_chart(fig_heat, use_container_width=True)

with comp_tab:
    selected_tracks = st.multiselect("Comparar track_id", sorted(tracks_view["track_id"].unique().tolist()), default=sorted(tracks_view["track_id"].unique().tolist())[:3])
    cmp_df = metrics_enriched[metrics_enriched["track_id"].isin(selected_tracks)]

    st.plotly_chart(px.bar(cmp_df, x="track_id", y="distancia_pixeles_aproximada", title="Comparativa distancia"), use_container_width=True)
    st.plotly_chart(px.bar(cmp_df, x="track_id", y="tiempo_visible_segundos", title="Comparativa tiempo visible"), use_container_width=True)
    st.plotly_chart(px.bar(cmp_df, x="track_id", y="velocidad_media_pixeles_segundo", title="Comparativa velocidad media"), use_container_width=True)

with exp_tab:
    st.subheader("Sistema manual de mapeo jugador")
    track_for_map = st.selectbox("track_id", sorted(metrics_enriched["track_id"].unique().tolist()), key="map_track")
    c1, c2 = st.columns(2)
    with c1:
        nombre = st.text_input("Nombre jugador")
        dorsal = st.text_input("Dorsal")
    with c2:
        equipo = st.text_input("Equipo")
        posicion = st.text_input("Posición")

    if st.button("Guardar en player_mapping.csv"):
        new_row = pd.DataFrame([{"track_id": track_for_map, "nombre": nombre, "dorsal": dorsal, "equipo": equipo, "posicion": posicion}])
        mapping_df2 = mapping_df[mapping_df["track_id"] != track_for_map]
        mapping_df2 = pd.concat([mapping_df2, new_row], ignore_index=True)
        mapping_df2.to_csv(mapping_path, index=False)
        st.success("Mapping guardado y aplicado.")

    st.subheader("Exportación")
    enriched_tracks = tracks_view.merge(metrics_enriched[["track_id", "estado_tracking"]], on="track_id", how="left")

    csv_bytes = enriched_tracks.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV enriquecido", csv_bytes, file_name="tracks_enriched.csv", mime="text/csv")

    traj_json = (
        tracks_view.groupby("track_id")[["timestamp_seconds", "center_x", "center_y"]]
        .apply(lambda g: g.to_dict(orient="records"))
        .to_dict()
    )
    st.download_button("Descargar JSON trayectorias", data=json.dumps(traj_json, ensure_ascii=False, indent=2), file_name="trajectories.json", mime="application/json")

    # Export PNG simple de trayectoria comparada
    fig_png, ax = plt.subplots(figsize=(8, 5))
    for tid in sorted(tracks_view["track_id"].unique())[:8]:
        d = tracks_view[tracks_view["track_id"] == tid]
        ax.plot(d["center_x"], d["center_y"], label=f"ID {tid}")
    ax.invert_yaxis()
    ax.set_title("Trayectorias (PNG)")
    ax.legend(loc="upper right", fontsize=7)
    buf = io.BytesIO()
    fig_png.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig_png)
    st.download_button("Descargar PNG de gráficos", data=buf.getvalue(), file_name="trayectorias.png", mime="image/png")
