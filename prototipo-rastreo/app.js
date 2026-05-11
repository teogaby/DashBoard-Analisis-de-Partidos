const videoInput = document.getElementById('videoInput');
const video = document.getElementById('video');
const overlayCanvas = document.getElementById('overlayCanvas');
const overlayCtx = overlayCanvas.getContext('2d');
const processingCanvas = document.getElementById('processingCanvas');
const processingCtx = processingCanvas.getContext('2d');
const playPauseBtn = document.getElementById('playPauseBtn');
const startBtn = document.getElementById('startTrackingBtn');
const stopBtn = document.getElementById('stopTrackingBtn');
const resetBtn = document.getElementById('resetTrackingBtn');
const metricsList = document.getElementById('metricsList');
const eventsBody = document.getElementById('eventsBody');
const statusBadge = document.getElementById('statusBadge');
const scoreText = document.getElementById('scoreText');
const logPanel = document.getElementById('logPanel');

let cvReady = false;
let isTracking = false;
let isDrawing = false;
let selectedBox = null;
let dragStart = null;
let templateMat = null;
let lastBox = null;
let rafId = null;
let lastSavedTime = -1;
const trackingEvents = [];

function addLog(message) {
  const line = document.createElement('div');
  line.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
  logPanel.prepend(line);
}

function setStatus(text, low = false) {
  statusBadge.textContent = `Estado: ${text}`;
  statusBadge.classList.toggle('low-score', low);
}

function setScore(score, low = false) {
  scoreText.textContent = `Score actual: ${score}`;
  scoreText.classList.toggle('low-score', low);
}

function syncCanvasSize() {
  const w = video.videoWidth || video.clientWidth;
  const h = video.videoHeight || video.clientHeight;
  overlayCanvas.width = w; overlayCanvas.height = h;
  processingCanvas.width = w; processingCanvas.height = h;
  redrawOverlay();
}

function getScaledPos(e) {
  const r = overlayCanvas.getBoundingClientRect();
  return { x: (e.clientX - r.left) * (overlayCanvas.width / r.width), y: (e.clientY - r.top) * (overlayCanvas.height / r.height) };
}

function normalizeRect(a, b) {
  const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
  const width = Math.abs(a.x - b.x), height = Math.abs(a.y - b.y);
  return { x, y, width, height, cx: x + width / 2, cy: y + height / 2 };
}

function drawBox(box, color = '#31d66f', dashed = false) {
  if (!box) return;
  overlayCtx.save();
  if (dashed) overlayCtx.setLineDash([6, 4]);
  overlayCtx.strokeStyle = color;
  overlayCtx.lineWidth = 2;
  overlayCtx.strokeRect(box.x, box.y, box.width, box.height);
  overlayCtx.beginPath(); overlayCtx.fillStyle = color;
  overlayCtx.arc(box.cx, box.cy, 4, 0, Math.PI * 2); overlayCtx.fill();
  overlayCtx.restore();
}

function redrawOverlay() {
  overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  if (trackingEvents.length > 1) {
    overlayCtx.beginPath(); overlayCtx.strokeStyle = '#31d66f'; overlayCtx.lineWidth = 2;
    trackingEvents.forEach((p, i) => (i === 0 ? overlayCtx.moveTo(p.cx, p.cy) : overlayCtx.lineTo(p.cx, p.cy)));
    overlayCtx.stroke();
  }
  trackingEvents.forEach((p) => drawBox(p, p.score < 0.45 ? '#ff6a6a' : '#31d66f'));
  if (selectedBox && !isTracking) drawBox(selectedBox, '#ffffff', true);
}

function renderMetrics() {
  const points = trackingEvents.length;
  const duration = points ? trackingEvents[points - 1].time - trackingEvents[0].time : 0;
  const avgScore = points ? trackingEvents.reduce((s, e) => s + e.score, 0) / points : 0;
  let dist = 0;
  for (let i = 1; i < points; i += 1) dist += Math.hypot(trackingEvents[i].cx - trackingEvents[i - 1].cx, trackingEvents[i].cy - trackingEvents[i - 1].cy);
  metricsList.innerHTML = `<li>Puntos capturados: <strong>${points}</strong></li><li>Duración seguida: <strong>${duration.toFixed(2)} s</strong></li><li>Distancia relativa aprox.: <strong>${dist.toFixed(2)} px</strong></li><li>Score medio: <strong>${avgScore.toFixed(3)}</strong></li>`;
}

function renderTable() {
  eventsBody.innerHTML = '';
  trackingEvents.forEach((e, i) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${i + 1}</td><td>${e.time.toFixed(3)}s</td><td>${Math.round(e.x)}</td><td>${Math.round(e.y)}</td><td>${Math.round(e.width)}</td><td>${Math.round(e.height)}</td><td>${e.score.toFixed(3)}</td>`;
    tr.addEventListener('click', () => { video.currentTime = e.time; redrawOverlay(); });
    eventsBody.appendChild(tr);
  });
}

function captureFrameMat() {
  processingCtx.drawImage(video, 0, 0, processingCanvas.width, processingCanvas.height);
  return cv.imread(processingCanvas);
}

function captureTemplate(box) {
  const frame = captureFrameMat();
  const x = Math.max(0, Math.floor(box.x));
  const y = Math.max(0, Math.floor(box.y));
  const w = Math.max(1, Math.min(frame.cols - x, Math.floor(box.width)));
  const h = Math.max(1, Math.min(frame.rows - y, Math.floor(box.height)));
  const roi = frame.roi(new cv.Rect(x, y, w, h));
  const gray = new cv.Mat();
  cv.cvtColor(roi, gray, cv.COLOR_RGBA2GRAY);
  if (templateMat) templateMat.delete();
  templateMat = gray.clone();
  gray.delete(); roi.delete(); frame.delete();
  addLog('Plantilla capturada');
}

function processTrackingFrame() {
  if (!isTracking) return;
  if (video.paused || video.ended) { rafId = requestAnimationFrame(processTrackingFrame); return; }

  const frame = captureFrameMat();
  const grayFrame = new cv.Mat();
  cv.cvtColor(frame, grayFrame, cv.COLOR_RGBA2GRAY);

  const margin = Math.max(lastBox.width, lastBox.height) * 1.5;
  const sx = Math.max(0, Math.floor(lastBox.x - margin));
  const sy = Math.max(0, Math.floor(lastBox.y - margin));
  const ex = Math.min(grayFrame.cols, Math.ceil(lastBox.x + lastBox.width + margin));
  const ey = Math.min(grayFrame.rows, Math.ceil(lastBox.y + lastBox.height + margin));
  const sw = ex - sx;
  const sh = ey - sy;

  if (sw <= templateMat.cols || sh <= templateMat.rows) {
    setStatus('ventana de búsqueda insuficiente', true);
    grayFrame.delete(); frame.delete();
    rafId = requestAnimationFrame(processTrackingFrame);
    return;
  }

  const search = grayFrame.roi(new cv.Rect(sx, sy, sw, sh));
  const result = new cv.Mat(sh - templateMat.rows + 1, sw - templateMat.cols + 1, cv.CV_32FC1);
  cv.matchTemplate(search, templateMat, result, cv.TM_CCOEFF_NORMED);
  const mm = cv.minMaxLoc(result);

  const score = mm.maxVal;
  setScore(score.toFixed(3), score < 0.45);
  addLog(`Frame procesado | Score actual: ${score.toFixed(3)}`);

  const nx = sx + mm.maxLoc.x;
  const ny = sy + mm.maxLoc.y;
  const box = { x: nx, y: ny, width: templateMat.cols, height: templateMat.rows, cx: nx + templateMat.cols / 2, cy: ny + templateMat.rows / 2, time: video.currentTime, score };

  lastBox = box;
  selectedBox = box;

  if (Math.abs(video.currentTime - lastSavedTime) > 0.04) {
    trackingEvents.push(box);
    lastSavedTime = video.currentTime;
    renderTable(); renderMetrics(); redrawOverlay();
  }

  if (score < 0.45) { setStatus('Jugador posiblemente perdido', true); addLog('Jugador posiblemente perdido'); }
  else setStatus('Tracking activo');

  result.delete(); search.delete(); grayFrame.delete(); frame.delete();
  rafId = requestAnimationFrame(processTrackingFrame);
}

function startTracking() {
  if (!cvReady || !selectedBox || isTracking) return;
  captureTemplate(selectedBox);
  lastBox = { ...selectedBox };
  isTracking = true;
  startBtn.disabled = true;
  stopBtn.disabled = false;
  setStatus('Tracking iniciado');
  addLog('Tracking iniciado');
  if (video.paused) video.play();
  rafId = requestAnimationFrame(processTrackingFrame);
}

function stopTracking() {
  isTracking = false;
  if (rafId) cancelAnimationFrame(rafId);
  startBtn.disabled = !selectedBox || !cvReady;
  stopBtn.disabled = true;
  setStatus('Tracking detenido');
}

function resetTracking() {
  stopTracking();
  trackingEvents.length = 0;
  selectedBox = null;
  lastBox = null;
  lastSavedTime = -1;
  if (templateMat) { templateMat.delete(); templateMat = null; }
  setScore('-');
  renderTable(); renderMetrics(); redrawOverlay();
  addLog('Reinicio completo');
}

videoInput.addEventListener('change', (e) => {
  const file = e.target.files?.[0]; if (!file) return;
  video.src = URL.createObjectURL(file);
  playPauseBtn.disabled = false; resetBtn.disabled = false;
  setStatus('Vídeo cargado, dibuja caja y pulsa iniciar');
});
video.addEventListener('loadedmetadata', syncCanvasSize);
playPauseBtn.addEventListener('click', () => (video.paused ? video.play() : video.pause()));
video.addEventListener('play', () => (playPauseBtn.textContent = '⏸ Pausar'));
video.addEventListener('pause', () => (playPauseBtn.textContent = '▶ Reproducir'));

overlayCanvas.addEventListener('mousedown', (e) => { if (!video.src || isTracking) return; isDrawing = true; dragStart = getScaledPos(e); });
overlayCanvas.addEventListener('mousemove', (e) => { if (!isDrawing || isTracking) return; selectedBox = normalizeRect(dragStart, getScaledPos(e)); redrawOverlay(); });
overlayCanvas.addEventListener('mouseup', (e) => {
  if (!isDrawing || isTracking) return; isDrawing = false;
  selectedBox = normalizeRect(dragStart, getScaledPos(e));
  if (selectedBox.width < 4 || selectedBox.height < 4) { selectedBox = null; setStatus('Caja demasiado pequeña', true); }
  else { setStatus('Caja lista'); startBtn.disabled = !cvReady; }
  redrawOverlay();
});

startBtn.addEventListener('click', startTracking);
stopBtn.addEventListener('click', stopTracking);
resetBtn.addEventListener('click', resetTracking);

window.onOpenCvReady = () => {
  cvReady = true;
  addLog('OpenCV cargado');
  setStatus('OpenCV cargado');
  if (selectedBox) startBtn.disabled = false;
};

renderMetrics();
