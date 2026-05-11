# Prototipo de rastreo manual de jugador (fútbol)

Aplicación web local (sin frameworks) para etiquetar manualmente eventos de un jugador sobre un vídeo mediante cajas de selección.

## Cómo usar
1. Abre `index.html` en tu navegador.
2. Carga un vídeo local.
3. Define jugador y acción.
4. Haz clic y arrastra sobre el jugador para crear una caja.
5. Cada caja guarda tiempo, posición (x/y), tamaño (ancho/alto), acción y jugador.
6. Haz clic en filas para volver al segundo del vídeo o usa **Borrar** para eliminar eventos individuales.
7. Usa **Limpiar rastreo** para resetear todo.

## Métricas
- Total de puntos/eventos.
- Distancia relativa aproximada del recorrido (centro de cada caja).
- Conteo por tipo de acción.
