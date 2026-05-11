# Prototipo de rastreo manual de jugador (fútbol)

Aplicación web local (sin frameworks) para etiquetar manualmente eventos de un jugador sobre un vídeo.

## Cómo usar

1. Abre `index.html` directamente en tu navegador.
2. Carga un vídeo local con el selector de archivo.
3. Completa el jugador (nombre o dorsal) y selecciona tipo de acción.
4. Haz clic sobre el vídeo para registrar eventos con tiempo y coordenadas.
5. Revisa la tabla y métricas; haz clic en una fila para saltar a ese instante del vídeo.
6. Usa **Limpiar rastreo** para reiniciar.

## Datos que guarda por evento

- Tiempo exacto del vídeo (segundos con milisegundos).
- Coordenada X.
- Coordenada Y.
- Tipo de acción.
- Jugador seleccionado.

## Notas

- La distancia mostrada es **relativa** (en píxeles sobre el canvas), útil para comparar recorridos dentro del mismo vídeo.
- Todo funciona en local, sin dependencias externas.
