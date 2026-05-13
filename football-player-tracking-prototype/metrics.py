"""Cálculo de métricas básicas y estabilidad por track_id."""
from __future__ import annotations
import math
import pandas as pd


def compute_metrics(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    cols = ["track_id","frames_detectados","tiempo_visible_segundos","distancia_pixeles_aproximada","velocidad_media_pixeles_segundo","primera_aparicion","ultima_aparicion","cambios_bruscos_posicion","gaps_deteccion","numero_reapariciones","score_estabilidad_track_id"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    out = []
    for track_id, g in df.groupby("track_id"):
        g = g.sort_values("frame_number").reset_index(drop=True)
        frames = len(g)
        primera, ultima = float(g["timestamp_seconds"].iloc[0]), float(g["timestamp_seconds"].iloc[-1])
        tiempo = max(0.0, ultima - primera)

        dist, jumps = 0.0, 0
        frame_gaps = g["frame_number"].diff().fillna(1)
        gaps_deteccion = int((frame_gaps > 1).sum())
        numero_reapariciones = gaps_deteccion

        step_dists = []
        for i in range(1, len(g)):
            dx = float(g.loc[i, "center_x"] - g.loc[i - 1, "center_x"])
            dy = float(g.loc[i, "center_y"] - g.loc[i - 1, "center_y"])
            d = math.hypot(dx, dy)
            step_dists.append(d)
            dist += d

        avg_step = sum(step_dists) / max(1, len(step_dists))
        threshold = max(40.0, avg_step * 2.7)
        jumps = sum(1 for d in step_dists if d > threshold)

        vel = dist / tiempo if tiempo > 0 else 0.0
        stability = max(0.0, 1.0 - ((jumps * 2 + gaps_deteccion * 3) / max(1.0, frames)))

        out.append({
            "track_id": int(track_id),
            "frames_detectados": int(frames),
            "tiempo_visible_segundos": round(tiempo, 3),
            "distancia_pixeles_aproximada": round(dist, 3),
            "velocidad_media_pixeles_segundo": round(vel, 3),
            "primera_aparicion": round(primera, 3),
            "ultima_aparicion": round(ultima, 3),
            "cambios_bruscos_posicion": int(jumps),
            "gaps_deteccion": int(gaps_deteccion),
            "numero_reapariciones": int(numero_reapariciones),
            "score_estabilidad_track_id": round(stability, 3),
        })

    return pd.DataFrame(out).sort_values("track_id").reset_index(drop=True)
