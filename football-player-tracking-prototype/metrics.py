"""Cálculo de métricas básicas por track_id a partir del CSV de detecciones."""

from __future__ import annotations

import math
import pandas as pd


def compute_metrics(csv_path: str) -> pd.DataFrame:
    """Calcula métricas por track_id desde el CSV frame a frame.

    Métricas:
    - frames_detectados
    - tiempo_visible_segundos
    - distancia_pixeles_aproximada
    - velocidad_media_pixeles_segundo
    - primera_aparicion
    - ultima_aparicion
    """
    df = pd.read_csv(csv_path)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "track_id",
                "frames_detectados",
                "tiempo_visible_segundos",
                "distancia_pixeles_aproximada",
                "velocidad_media_pixeles_segundo",
                "primera_aparicion",
                "ultima_aparicion",
            ]
        )

    summary_rows = []

    for track_id, g in df.groupby("track_id"):
        g = g.sort_values("frame_number").reset_index(drop=True)
        frames_detectados = int(len(g))
        primera = float(g["timestamp_seconds"].iloc[0])
        ultima = float(g["timestamp_seconds"].iloc[-1])
        tiempo_visible = max(0.0, ultima - primera)

        # Distancia aproximada acumulando saltos entre centros consecutivos.
        dist = 0.0
        for i in range(1, len(g)):
            dx = float(g.loc[i, "center_x"] - g.loc[i - 1, "center_x"])
            dy = float(g.loc[i, "center_y"] - g.loc[i - 1, "center_y"])
            dist += math.hypot(dx, dy)

        vel = dist / tiempo_visible if tiempo_visible > 0 else 0.0

        summary_rows.append(
            {
                "track_id": int(track_id),
                "frames_detectados": frames_detectados,
                "tiempo_visible_segundos": round(tiempo_visible, 3),
                "distancia_pixeles_aproximada": round(dist, 3),
                "velocidad_media_pixeles_segundo": round(vel, 3),
                "primera_aparicion": round(primera, 3),
                "ultima_aparicion": round(ultima, 3),
            }
        )

    return pd.DataFrame(summary_rows).sort_values("track_id").reset_index(drop=True)
