from __future__ import annotations
import math
import pandas as pd


def compute_metrics(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    cols=["track_id","frames_detectados","tiempo_visible_segundos","distancia_pixeles_aproximada","velocidad_media_pixeles_segundo","primera_aparicion","ultima_aparicion","total_gaps","max_gap","sudden_jumps","stability_score","cambios_bruscos_posicion","gaps_deteccion","numero_reapariciones","score_estabilidad_track_id"]
    if df.empty: return pd.DataFrame(columns=cols)

    out=[]
    for tid,g in df.groupby("track_id"):
        g=g.sort_values("frame_number").reset_index(drop=True)
        frames=len(g); primera=float(g.timestamp_seconds.iloc[0]); ultima=float(g.timestamp_seconds.iloc[-1]); tiempo=max(0.0,ultima-primera)
        dist=0.0
        for i in range(1,len(g)):
            dist+=math.hypot(float(g.loc[i,"center_x"]-g.loc[i-1,"center_x"]), float(g.loc[i,"center_y"]-g.loc[i-1,"center_y"]))
        vel=dist/tiempo if tiempo>0 else 0.0

        if "frame_gap_from_previous" in g.columns: gaps=g["frame_gap_from_previous"].fillna(0)
        else: gaps=g["frame_number"].diff().fillna(0)
        total_gaps=int((gaps>1).sum()); max_gap=int(gaps.max())

        if "possible_id_switch" in g.columns: sudden_jumps=int(g["possible_id_switch"].sum())
        else:
            d=((g["center_x"].diff().fillna(0)**2 + g["center_y"].diff().fillna(0)**2)**0.5)
            sudden_jumps=int((d>max(80,d.mean()*2.8)).sum())

        stability=max(0.0,1.0-((sudden_jumps*2+total_gaps*3)/max(1,frames)))

        out.append({"track_id":int(tid),"frames_detectados":frames,"tiempo_visible_segundos":round(tiempo,3),"distancia_pixeles_aproximada":round(dist,3),"velocidad_media_pixeles_segundo":round(vel,3),"primera_aparicion":round(primera,3),"ultima_aparicion":round(ultima,3),"total_gaps":total_gaps,"max_gap":max_gap,"sudden_jumps":sudden_jumps,"stability_score":round(stability,3),"cambios_bruscos_posicion":sudden_jumps,"gaps_deteccion":total_gaps,"numero_reapariciones":total_gaps,"score_estabilidad_track_id":round(stability,3)})

    return pd.DataFrame(out).sort_values("track_id").reset_index(drop=True)
