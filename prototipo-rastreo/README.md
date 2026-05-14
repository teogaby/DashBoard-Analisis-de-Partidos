# Prototipo experimental de rastreo asistido (OpenCV.js)

Aplicación local en HTML/CSS/JavaScript puro para validar seguimiento aproximado de un jugador en vídeo de fútbol.

## Flujo rápido
1. Abre `index.html` en el navegador.
2. Carga un vídeo local.
3. Pausa el vídeo y dibuja una caja sobre el jugador (clic y arrastre).
4. Pulsa **Iniciar seguimiento**.
5. El sistema intentará localizar la plantilla en frames sucesivos y guardará eventos automáticos.
6. Usa **Detener seguimiento** para pausar el tracking y **Reiniciar seguimiento** para limpiar todo.

## Datos por evento
- tiempo del vídeo
- x, y
- ancho, alto
- score de coincidencia

## Métricas
- puntos capturados
- duración seguida
- distancia relativa aproximada
- score medio de seguimiento

## Limitaciones aceptadas
- El seguimiento puede fallar si hay muchos jugadores parecidos.
- Puede fallar si la cámara se mueve rápido.
- Puede fallar si el jugador se tapa o cambia mucho de tamaño.
- Este prototipo es experimental y sirve para validar comportamiento.
