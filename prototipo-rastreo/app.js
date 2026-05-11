// ============================================================
// RASTREO EXPERIMENTAL POR COLOR DOMINANTE (CAMISETA)
// ============================================================
// Este archivo implementa un prototipo de tracking SIN OpenCV,
// usando únicamente HTML Canvas + JavaScript puro.
//
// Fases:
// 1) Usuario carga vídeo y pausa en el frame deseado.
// 2) Usuario dibuja caja sobre el jugador.
// 3) Se calcula color objetivo (promedio RGB) dentro de la caja.
// 4) Por cada frame: se buscan ventanas candidatas alrededor
//    de la última posición y se elige la más parecida por color.
// 5) La caja se mueve automáticamente y se guarda el rastro.
// ============================================================

const $ = (id) => document.getElementById(id);
const videoInput = $('videoInput');
const video = $('video');
const overlayCanvas = $('overlayCanvas');
const overlayCtx = overlayCanvas.getContext('2d');
const processingCanvas = $('processingCanvas');
const processingCtx = processingCanvas.getContext('2d', { willReadFrequently: true });
const playPauseBtn = $('playPauseBtn');
const startTrackingBtn = $('startTrackingBtn');
const stopTrackingBtn = $('stopTrackingBtn');
const clearTrackingBtn = $('clearTrackingBtn');
const sensitivityInput = $('sensitivityInput');
const searchSizeInput = $('searchSizeInput');
const sensitivityValue = $('sensitivityValue');
const searchSizeValue = $('searchSizeValue');
const statusBadge = $('statusBadge');
const targetColorText = $('targetColorText');
const debugList = $('debugList');
const logPanel = $('logPanel');
const eventsBody = $('eventsBody');

let isDrawing = false;
let isTracking = false;
let dragStart = null;
let selectedBox = null;
let lastBox = null;
let targetColor = null; // {r,g,b}
let currentScore = 0;
let rafId = null;
let lastSavedTime = -1;
const trackingPoints = [];

function log(msg) {
  const item = document.createElement('div');
  item.textContent = `${new Date().toLocaleTimeString()} - ${msg}`;
  logPanel.prepend(item);
}

function setStatus(msg, weak = false) {
  statusBadge.textContent = `Estado: ${msg}`;
  statusBadge.classList.toggle('low-score', weak);
}

function syncCanvasSize() {
  const w = video.videoWidth || video.clientWidth;
  const h = video.videoHeight || video.clientHeight;
  overlayCanvas.width = w; overlayCanvas.height = h;
  processingCanvas.width = w; processingCanvas.height = h;
  drawOverlay();
}

function getScaledMouse(evt) {
  const rect = overlayCanvas.getBoundingClientRect();
  return {
    x: ((evt.clientX - rect.left) * overlayCanvas.width) / rect.width,
    y: ((evt.clientY - rect.top) * overlayCanvas.height) / rect.height
  };
}

function normalizeRect(a, b) {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  const width = Math.abs(a.x - b.x);
  const height = Math.abs(a.y - b.y);
  return { x, y, width, height, cx: x + width / 2, cy: y + height / 2 };
}

function drawBox(box, color = '#31d66f', dashed = false) {
  if (!box) return;
  overlayCtx.save();
  if (dashed) overlayCtx.setLineDash([6, 4]);
  overlayCtx.strokeStyle = color;
  overlayCtx.lineWidth = 2;
  overlayCtx.strokeRect(box.x, box.y, box.width, box.height);
  overlayCtx.beginPath();
  overlayCtx.fillStyle = color;
  overlayCtx.arc(box.cx, box.cy, 4, 0, Math.PI * 2);
  overlayCtx.fill();
  overlayCtx.restore();
}

function drawOverlay() {
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

  if (trackingPoints.length > 1) {
    overlayCtx.beginPath();
    overlayCtx.strokeStyle = '#31d66f';
    overlayCtx.lineWidth = 2;
    trackingPoints.forEach((p, i) => (i === 0 ? overlayCtx.moveTo(p.cx, p.cy) : overlayCtx.lineTo(p.cx, p.cy)));
    overlayCtx.stroke();
  }

  trackingPoints.forEach((p) => drawBox(p, p.score < 0.45 ? '#ff6a6a' : '#31d66f'));
  if (selectedBox && !isTracking) drawBox(selectedBox, '#ffffff', true);
}

function drawFrameToProcessingCanvas() {
  processingCtx.drawImage(video, 0, 0, processingCanvas.width, processingCanvas.height);
}

function getAverageColorInRect(rect) {
  // Lee todos los píxeles de la ROI y promedia RGB.
  const x = Math.max(0, Math.floor(rect.x));
  const y = Math.max(0, Math.floor(rect.y));
  const w = Math.max(1, Math.floor(rect.width));
  const h = Math.max(1, Math.floor(rect.height));

  const imageData = processingCtx.getImageData(x, y, w, h).data;
  let r = 0, g = 0, b = 0;
  const totalPixels = imageData.length / 4;

  for (let i = 0; i < imageData.length; i += 4) {
    r += imageData[i];
    g += imageData[i + 1];
    b += imageData[i + 2];
  }

  return { r: r / totalPixels, g: g / totalPixels, b: b / totalPixels };
}

function colorDistance(c1, c2) {
  // Distancia euclídea RGB normalizada a [0..1] aprox.
  const dr = c1.r - c2.r;
  const dg = c1.g - c2.g;
  const db = c1.b - c2.b;
  return Math.sqrt(dr * dr + dg * dg + db * db) / 441.6729559;
}

function computeScore(candidateColor) {
  // Score alto = mejor coincidencia.
  const dist = colorDistance(targetColor, candidateColor);
  const sensitivity = Number(sensitivityInput.value); // 20..180
  const tolerance = sensitivity / 255;
  return Math.max(0, 1 - dist / Math.max(0.05, tolerance));
}

function findBestMatchAroundLastBox() {
  // Busca ventanas candidatas en una rejilla alrededor de la última caja.
  const area = Number(searchSizeInput.value);
  const step = Math.max(4, Math.round(Math.min(lastBox.width, lastBox.height) / 4));

  let best = null;
  let bestScore = -1;

  const startX = Math.max(0, Math.floor(lastBox.x - area));
  const endX = Math.min(processingCanvas.width - lastBox.width, Math.ceil(lastBox.x + area));
  const startY = Math.max(0, Math.floor(lastBox.y - area));
  const endY = Math.min(processingCanvas.height - lastBox.height, Math.ceil(lastBox.y + area));

  for (let y = startY; y <= endY; y += step) {
    for (let x = startX; x <= endX; x += step) {
      const candidateRect = { x, y, width: lastBox.width, height: lastBox.height, cx: x + lastBox.width / 2, cy: y + lastBox.height / 2 };
      const candidateColor = getAverageColorInRect(candidateRect);
      const score = computeScore(candidateColor);
      if (score > bestScore) {
        bestScore = score;
        best = candidateRect;
      }
    }
  }

  return { bestRect: best, bestScore };
}

function saveTrackingPoint(box, score) {
  const point = { ...box, time: video.currentTime, score };
  trackingPoints.push(point);
  if (Math.abs(video.currentTime - lastSavedTime) > 0.04) {
    lastSavedTime = video.currentTime;
  }
}

function renderTable() {
  eventsBody.innerHTML = '';
  trackingPoints.forEach((p, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td>${p.time.toFixed(3)}s</td><td>${Math.round(p.x)}</td><td>${Math.round(p.y)}</td><td>${Math.round(p.width)}</td><td>${Math.round(p.height)}</td><td>${p.score.toFixed(3)}</td>`;
    tr.addEventListener('click', () => { video.currentTime = p.time; drawOverlay(); });
    eventsBody.appendChild(tr);
  });
}

function renderDebug() {
  debugList.innerHTML = `
    <li>Tracking: <strong>${isTracking ? 'activo' : 'detenido'}</strong></li>
    <li>Caja actual: <strong>${lastBox ? `x:${Math.round(lastBox.x)}, y:${Math.round(lastBox.y)}` : '-'}</strong></li>
    <li>Puntos capturados: <strong>${trackingPoints.length}</strong></li>
    <li>Score actual: <strong>${currentScore.toFixed(3)}</strong></li>
  `;
}

function trackFrame() {
  if (!isTracking) return;
  if (video.paused || video.ended) {
    rafId = requestAnimationFrame(trackFrame);
    return;
  }

  drawFrameToProcessingCanvas();
  const { bestRect, bestScore } = findBestMatchAroundLastBox();
  currentScore = bestScore;

  if (bestRect) {
    lastBox = bestRect;
    selectedBox = bestRect;
    saveTrackingPoint(bestRect, bestScore);
    log(`Frame procesado | Score actual: ${bestScore.toFixed(3)}`);

    if (bestScore < 0.45) {
      setStatus('Seguimiento débil / jugador posiblemente perdido', true);
      log('Seguimiento débil');
    } else {
      setStatus('Tracking activo');
    }
  } else {
    setStatus('Jugador posiblemente perdido (sin mejor coincidencia)', true);
  }

  targetColorText.classList.toggle('low-score', currentScore < 0.45);
  targetColorText.textContent = `Color objetivo: rgb(${Math.round(targetColor.r)}, ${Math.round(targetColor.g)}, ${Math.round(targetColor.b)}) | Score actual: ${currentScore.toFixed(3)}`;

  renderTable();
  renderDebug();
  drawOverlay();

  rafId = requestAnimationFrame(trackFrame);
}

function startTracking() {
  if (!selectedBox || isTracking) return;

  drawFrameToProcessingCanvas();
  targetColor = getAverageColorInRect(selectedBox);
  lastBox = { ...selectedBox };
  isTracking = true;

  log('Color objetivo detectado');
  log('Tracking iniciado');
  setStatus('Tracking iniciado');

  targetColorText.textContent = `Color objetivo: rgb(${Math.round(targetColor.r)}, ${Math.round(targetColor.g)}, ${Math.round(targetColor.b)})`;
  startTrackingBtn.disabled = true;
  stopTrackingBtn.disabled = false;

  if (video.paused) video.play();
  rafId = requestAnimationFrame(trackFrame);
}

function stopTracking() {
  isTracking = false;
  if (rafId) cancelAnimationFrame(rafId);
  startTrackingBtn.disabled = !selectedBox;
  stopTrackingBtn.disabled = true;
  setStatus('Tracking detenido');
  renderDebug();
}

function clearTracking() {
  stopTracking();
  selectedBox = null;
  lastBox = null;
  targetColor = null;
  currentScore = 0;
  lastSavedTime = -1;
  trackingPoints.length = 0;
  targetColorText.textContent = 'Color objetivo: -';
  drawOverlay();
  renderTable();
  renderDebug();
  log('Tracking limpiado');
}

videoInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  video.src = URL.createObjectURL(file);
  playPauseBtn.disabled = false;
  clearTrackingBtn.disabled = false;
  setStatus('Vídeo cargado');
  log('Vídeo cargado');
});

video.addEventListener('loadedmetadata', syncCanvasSize);
video.addEventListener('play', () => { playPauseBtn.textContent = '⏸ Pausar'; });
video.addEventListener('pause', () => { playPauseBtn.textContent = '▶ Reproducir'; });
playPauseBtn.addEventListener('click', () => (video.paused ? video.play() : video.pause()));

sensitivityInput.addEventListener('input', () => { sensitivityValue.textContent = sensitivityInput.value; });
searchSizeInput.addEventListener('input', () => { searchSizeValue.textContent = `${searchSizeInput.value} px`; });

overlayCanvas.addEventListener('mousedown', (evt) => {
  if (!video.src || isTracking) return;
  isDrawing = true;
  dragStart = getScaledMouse(evt);
});

overlayCanvas.addEventListener('mousemove', (evt) => {
  if (!isDrawing || isTracking) return;
  selectedBox = normalizeRect(dragStart, getScaledMouse(evt));
  drawOverlay();
});

overlayCanvas.addEventListener('mouseup', (evt) => {
  if (!isDrawing || isTracking) return;
  isDrawing = false;
  selectedBox = normalizeRect(dragStart, getScaledMouse(evt));
  if (selectedBox.width < 6 || selectedBox.height < 6) {
    selectedBox = null;
    setStatus('Caja demasiado pequeña', true);
  } else {
    setStatus('Caja seleccionada');
    log('Caja seleccionada');
    startTrackingBtn.disabled = false;
  }
  drawOverlay();
  renderDebug();
});

startTrackingBtn.addEventListener('click', startTracking);
stopTrackingBtn.addEventListener('click', stopTracking);
clearTrackingBtn.addEventListener('click', clearTracking);

renderDebug();
