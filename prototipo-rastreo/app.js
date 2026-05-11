// Prototipo experimental de seguimiento asistido con OpenCV.js.
// Flujo principal:
// 1) Usuario pausa vídeo y dibuja una caja (template inicial del jugador).
// 2) Al iniciar seguimiento, guardamos template + último bounding box.
// 3) En cada frame buscamos el template dentro de una ventana cercana al último punto (matchTemplate).
// 4) Si el score es aceptable, actualizamos caja, dibujamos rastro y guardamos evento.
// 5) Si score bajo, avisamos posible pérdida para intervención manual.

const videoInput = document.getElementById('videoInput');
const video = document.getElementById('video');
const canvas = document.getElementById('overlayCanvas');
const ctx = canvas.getContext('2d');
const playPauseBtn = document.getElementById('playPauseBtn');
const startBtn = document.getElementById('startTrackingBtn');
const stopBtn = document.getElementById('stopTrackingBtn');
const resetBtn = document.getElementById('resetTrackingBtn');
const metricsList = document.getElementById('metricsList');
const eventsBody = document.getElementById('eventsBody');
const statusBadge = document.getElementById('statusBadge');

let cvReady = false;
let selectedBox = null;
let isDrawing = false;
let dragStart = null;
let isTracking = false;
let rafId = null;
let lastSavedTime = -1;
let templateMat = null;
let lastBox = null;
let trackStartTime = null;
const trackingEvents = [];

function setStatus(text, isLow = false) {
  statusBadge.textContent = `Estado: ${text}`;
  statusBadge.classList.toggle('low-score', isLow);
}

function syncCanvasSize() {
  canvas.width = video.videoWidth || video.clientWidth;
  canvas.height = video.videoHeight || video.clientHeight;
  redraw();
}

function getPos(e) {
  const r = canvas.getBoundingClientRect();
  return {
    x: Math.min(Math.max((e.clientX - r.left) * (canvas.width / r.width), 0), canvas.width),
    y: Math.min(Math.max((e.clientY - r.top) * (canvas.height / r.height), 0), canvas.height)
  };
}

function normRect(a, b) {
  const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
  const width = Math.abs(a.x - b.x), height = Math.abs(a.y - b.y);
  return { x, y, width, height, cx: x + width / 2, cy: y + height / 2 };
}

function drawBox(box, color = '#31d66f', dashed = false) {
  if (!box) return;
  ctx.save();
  if (dashed) ctx.setLineDash([6, 4]);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(box.x, box.y, box.width, box.height);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(box.cx, box.cy, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function redraw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (trackingEvents.length > 1) {
    ctx.beginPath();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#31d66f';
    trackingEvents.forEach((e, i) => (i ? ctx.lineTo(e.cx, e.cy) : ctx.moveTo(e.cx, e.cy)));
    ctx.stroke();
  }
  trackingEvents.forEach((ev) => drawBox(ev, ev.score < 0.45 ? '#ff6a6a' : '#31d66f'));
  if (selectedBox && !isTracking) drawBox(selectedBox, '#ffffff', true);
}

function renderTable() {
  eventsBody.innerHTML = '';
  trackingEvents.forEach((ev, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td>${ev.time.toFixed(3)}s</td><td>${Math.round(ev.x)}</td><td>${Math.round(ev.y)}</td><td>${Math.round(ev.width)}</td><td>${Math.round(ev.height)}</td><td>${ev.score.toFixed(3)}</td>`;
    tr.addEventListener('click', () => { video.currentTime = ev.time; redraw(); });
    eventsBody.appendChild(tr);
  });
}

function distancePx(events) {
  let d = 0;
  for (let i = 1; i < events.length; i += 1) d += Math.hypot(events[i].cx - events[i - 1].cx, events[i].cy - events[i - 1].cy);
  return d;
}

function renderMetrics() {
  const points = trackingEvents.length;
  const duration = points ? trackingEvents[points - 1].time - trackingEvents[0].time : 0;
  const avgScore = points ? trackingEvents.reduce((s, e) => s + e.score, 0) / points : 0;
  metricsList.innerHTML = `<li>Puntos capturados: <strong>${points}</strong></li>
  <li>Duración seguida: <strong>${duration.toFixed(2)} s</strong></li>
  <li>Distancia relativa aprox.: <strong>${distancePx(trackingEvents).toFixed(2)} px</strong></li>
  <li>Score medio de seguimiento: <strong>${avgScore.toFixed(3)}</strong></li>`;
}

function buildTemplateFromBox(box) {
  const frame = cv.imread(video);
  const x = Math.max(0, Math.floor(box.x));
  const y = Math.max(0, Math.floor(box.y));
  const w = Math.min(frame.cols - x, Math.floor(box.width));
  const h = Math.min(frame.rows - y, Math.floor(box.height));
  const roi = frame.roi(new cv.Rect(x, y, w, h));
  const gray = new cv.Mat();
  cv.cvtColor(roi, gray, cv.COLOR_RGBA2GRAY);
  if (templateMat) templateMat.delete();
  templateMat = gray.clone();
  gray.delete(); roi.delete(); frame.delete();
}

function trackFrame() {
  if (!isTracking || video.paused || video.ended) return;

  const frame = cv.imread(video);
  const grayFrame = new cv.Mat();
  cv.cvtColor(frame, grayFrame, cv.COLOR_RGBA2GRAY);

  const margin = Math.max(lastBox.width, lastBox.height) * 1.4;
  const sx = Math.max(0, Math.floor(lastBox.x - margin));
  const sy = Math.max(0, Math.floor(lastBox.y - margin));
  const ex = Math.min(grayFrame.cols, Math.ceil(lastBox.x + lastBox.width + margin));
  const ey = Math.min(grayFrame.rows, Math.ceil(lastBox.y + lastBox.height + margin));
  const sw = ex - sx;
  const sh = ey - sy;

  if (sw <= templateMat.cols || sh <= templateMat.rows) {
    setStatus('ventana de búsqueda insuficiente', true);
    grayFrame.delete(); frame.delete();
    rafId = requestAnimationFrame(trackFrame);
    return;
  }

  const searchRoi = grayFrame.roi(new cv.Rect(sx, sy, sw, sh));
  const resultCols = sw - templateMat.cols + 1;
  const resultRows = sh - templateMat.rows + 1;
  const result = new cv.Mat(resultRows, resultCols, cv.CV_32FC1);
  cv.matchTemplate(searchRoi, templateMat, result, cv.TM_CCOEFF_NORMED);
  const mm = cv.minMaxLoc(result);
  const score = mm.maxVal;

  const foundX = sx + mm.maxLoc.x;
  const foundY = sy + mm.maxLoc.y;
  const box = {
    x: foundX,
    y: foundY,
    width: templateMat.cols,
    height: templateMat.rows,
    cx: foundX + templateMat.cols / 2,
    cy: foundY + templateMat.rows / 2,
    time: video.currentTime,
    score
  };

  lastBox = box;
  selectedBox = box;

  if (Math.abs(video.currentTime - lastSavedTime) > 0.04) {
    trackingEvents.push(box);
    lastSavedTime = video.currentTime;
    renderTable();
    renderMetrics();
  }

  if (score < 0.45) setStatus(`score bajo (${score.toFixed(3)}): posible pérdida`, true);
  else setStatus(`siguiendo jugador (score ${score.toFixed(3)})`);

  redraw();

  result.delete();
  searchRoi.delete();
  grayFrame.delete();
  frame.delete();

  rafId = requestAnimationFrame(trackFrame);
}

function startTracking() {
  if (!cvReady || !selectedBox) return;
  buildTemplateFromBox(selectedBox);
  lastBox = { ...selectedBox };
  isTracking = true;
  trackStartTime = video.currentTime;
  startBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('seguimiento activo');
  if (video.paused) video.play();
  rafId = requestAnimationFrame(trackFrame);
}

function stopTracking() {
  isTracking = false;
  if (rafId) cancelAnimationFrame(rafId);
  startBtn.disabled = !selectedBox;
  stopBtn.disabled = true;
  const dur = trackStartTime == null ? 0 : Math.max(0, video.currentTime - trackStartTime);
  setStatus(`seguimiento detenido (duración sesión ${dur.toFixed(2)}s)`);
}

function resetTracking() {
  stopTracking();
  trackingEvents.length = 0;
  selectedBox = null;
  lastBox = null;
  lastSavedTime = -1;
  if (templateMat) { templateMat.delete(); templateMat = null; }
  renderTable(); renderMetrics(); redraw();
  setStatus('seguimiento reiniciado; dibuja nueva caja');
}

videoInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  video.src = URL.createObjectURL(file);
  playPauseBtn.disabled = false;
  resetBtn.disabled = false;
  setStatus('vídeo cargado, pausa y dibuja una caja');
});
video.addEventListener('loadedmetadata', syncCanvasSize);
window.addEventListener('resize', syncCanvasSize);
playPauseBtn.addEventListener('click', () => (video.paused ? video.play() : video.pause()));
video.addEventListener('play', () => (playPauseBtn.textContent = '⏸ Pausar'));
video.addEventListener('pause', () => (playPauseBtn.textContent = '▶ Reproducir'));

canvas.addEventListener('mousedown', (e) => {
  if (!video.src || isTracking) return;
  isDrawing = true;
  dragStart = getPos(e);
  selectedBox = { ...dragStart, width: 0, height: 0, cx: dragStart.x, cy: dragStart.y };
});
canvas.addEventListener('mousemove', (e) => {
  if (!isDrawing || isTracking) return;
  selectedBox = normRect(dragStart, getPos(e));
  redraw();
});
canvas.addEventListener('mouseup', (e) => {
  if (!isDrawing || isTracking) return;
  isDrawing = false;
  selectedBox = normRect(dragStart, getPos(e));
  if (selectedBox.width < 4 || selectedBox.height < 4) {
    selectedBox = null;
    setStatus('caja muy pequeña, vuelve a dibujar', true);
  } else {
    setStatus('caja lista, pulsa "Iniciar seguimiento"');
    startBtn.disabled = !cvReady;
  }
  redraw();
});

startBtn.addEventListener('click', startTracking);
stopBtn.addEventListener('click', stopTracking);
resetBtn.addEventListener('click', resetTracking);

// OpenCV.js define este callback cuando termina de cargar WASM.
window.onOpenCvReady = () => {
  cvReady = true;
  setStatus('OpenCV listo. Carga vídeo y dibuja caja.');
  if (selectedBox) startBtn.disabled = false;
};

renderMetrics();
