# Football Player Tracking Prototype

Prototipo funcional local para seguimiento de jugadores/personas en vídeo de fútbol usando:

- **Python 3.11+**
- **Streamlit** (interfaz web local)
- **Ultralytics YOLO** (detección + tracking)
- **ByteTrack** (tracking multi-objeto)
- **OpenCV** (lectura/escritura/anotación de vídeo)
- **Pandas** (métricas y exportación)

## Estructura

```text
football-player-tracking-prototype/
├── app.py
├── tracker.py
├── metrics.py
├── requirements.txt
├── README.md
├── outputs/
├── uploads/
└── sample_data/
```

## Instalación

```bash
cd football-player-tracking-prototype
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
```

## Ejecución

```bash
streamlit run app.py
```

## Qué hace el prototipo

1. Permite subir un vídeo (`mp4`, `mov`, `avi`).
2. Guarda el archivo en `uploads/`.
3. Procesa el vídeo con `YOLO.track(..., persist=True)` usando tracker seleccionable:
   - `bytetrack_custom.yaml` (config local estable)
4. Detecta clase **person** (jugadores y otras personas visibles).
5. Dibuja en el vídeo:
   - caja de detección
   - ID de tracking
   - trayectoria corta por ID
6. Genera:
   - vídeo anotado en `outputs/`
   - CSV frame a frame de detecciones
   - CSV de métricas por `track_id`

## Métricas por `track_id`

- `frames_detectados`
- `tiempo_visible_segundos`
- `distancia_pixeles_aproximada`
- `velocidad_media_pixeles_segundo`
- `primera_aparicion`
- `ultima_aparicion`

## Limitaciones

- No reconoce dorsal todavía.
- Puede cambiar ID si hay oclusiones o cruces intensos.
- Detecta personas, no jugadores específicos por nombre.
- Para precisión profesional hace falta entrenar un modelo específico y/o añadir reidentificación robusta.

## Notas

- Si faltan carpetas, la app las crea automáticamente.
- Si falta el modelo YOLO local, Ultralytics puede descargarlo automáticamente en la primera ejecución.

## Estabilidad de track_id en fútbol

Los IDs pueden cambiar cuando hay cruces, oclusiones o salidas de plano. ByteTrack decide asociaciones frame a frame y puede reasignar identidad cuando la evidencia visual es ambigua.

### Presets ByteTrack

El prototipo incluye tres presets para ajustar persistencia de identidad:

- `bytetrack_conservative.yaml`
- `bytetrack_balanced.yaml`
- `bytetrack_aggressive.yaml`

En la interfaz puedes seleccionar preset y luego ajustar manualmente:
- `track_high_thresh`
- `track_low_thresh`
- `new_track_thresh`
- `track_buffer`
- `match_thresh`

Recomendación:
- **Conservador**: más estable en IDs, menos sensible a nuevas detecciones rápidas.
- **Equilibrado**: compromiso general para la mayoría de partidos.
- **Agresivo**: capta más detecciones nuevas, pero aumenta riesgo de switches.

### Limitaciones de ByteTrack en fútbol

- Oclusiones largas pueden romper la continuidad del ID.
- Cruces de jugadores cercanos pueden causar intercambio de identidad.
- Cambios de cámara bruscos y zooms afectan la consistencia del track.
