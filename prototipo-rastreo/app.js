const videoInput = document.getElementById('videoInput');
const video = document.getElementById('video');
const canvas = document.getElementById('overlayCanvas');
const ctx = canvas.getContext('2d');
const playPauseBtn = document.getElementById('playPauseBtn');
const clearBtn = document.getElementById('clearBtn');
const playerInput = document.getElementById('playerInput');
const actionSelect = document.getElementById('actionSelect');
const eventsBody = document.getElementById('eventsBody');
const metricsList = document.getElementById('metricsList');

const trackingEvents = [];
let isDrawing = false;
let dragStart = null;
let previewRect = null;

const colorsByAction = { posición: '#ffffff', presión: '#31d66f', recuperación: '#4bc4ff', pérdida: '#ff6a6a', pase: '#ffd166', duelo: '#c77dff', desmarque: '#00f5d4' };

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

function formatTime(seconds) {
  const min = Math.floor(seconds / 60);
  const sec = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 1000);
  return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
}

function syncCanvasSize() {
  canvas.width = video.videoWidth || video.clientWidth;
  canvas.height = video.videoHeight || video.clientHeight;
  redrawTracking();
}

function getCanvasPosition(e) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  return {
    x: clamp((e.clientX - rect.left) * scaleX, 0, canvas.width),
    y: clamp((e.clientY - rect.top) * scaleY, 0, canvas.height)
  };
}

function normalizeRect(start, end) {
  const x = Math.min(start.x, end.x);
  const y = Math.min(start.y, end.y);
  const width = Math.abs(end.x - start.x);
  const height = Math.abs(end.y - start.y);
  return { x, y, width, height, cx: x + width / 2, cy: y + height / 2 };
}

function drawBox(event, index) {
  const color = colorsByAction[event.action] || '#fff';
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.strokeRect(event.x, event.y, event.width, event.height);

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(event.cx, event.cy, 5, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#ffffff';
  ctx.font = '11px sans-serif';
  ctx.fillText(String(index + 1), event.cx + 7, event.cy - 7);
}

function drawPreviewRect() {
  if (!previewRect) return;
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = '#ffffffcc';
  ctx.lineWidth = 1.5;
  ctx.strokeRect(previewRect.x, previewRect.y, previewRect.width, previewRect.height);
  ctx.setLineDash([]);
}

function redrawTracking() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!trackingEvents.length) {
    drawPreviewRect();
    return;
  }

  ctx.lineWidth = 2;
  ctx.strokeStyle = '#31d66f';
  ctx.beginPath();
  trackingEvents.forEach((event, i) => {
    if (i === 0) ctx.moveTo(event.cx, event.cy);
    else ctx.lineTo(event.cx, event.cy);
  });
  ctx.stroke();

  trackingEvents.forEach((event, index) => drawBox(event, index));
  drawPreviewRect();
}

function calculateDistance(events) {
  let total = 0;
  for (let i = 1; i < events.length; i += 1) {
    const dx = events[i].cx - events[i - 1].cx;
    const dy = events[i].cy - events[i - 1].cy;
    total += Math.sqrt(dx * dx + dy * dy);
  }
  return total;
}

function renderMetrics() {
  const byAction = trackingEvents.reduce((acc, ev) => ((acc[ev.action] = (acc[ev.action] || 0) + 1), acc), {});
  const actionItems = Object.entries(byAction).map(([a, c]) => `<li>${a}: <strong>${c}</strong></li>`).join('');
  metricsList.innerHTML = `<li>Total de puntos: <strong>${trackingEvents.length}</strong></li>
  <li>Número de acciones: <strong>${trackingEvents.length}</strong></li>
  <li>Distancia relativa aprox.: <strong>${calculateDistance(trackingEvents).toFixed(2)} px</strong></li>
  <li>Acciones por tipo:<ul>${actionItems || '<li>Sin datos</li>'}</ul></li>`;
}

function removeEvent(index) {
  trackingEvents.splice(index, 1);
  redrawTracking();
  renderEventsTable();
  renderMetrics();
}

function renderEventsTable() {
  eventsBody.innerHTML = '';
  trackingEvents.forEach((event, index) => {
    const row = document.createElement('tr');
    row.dataset.time = String(event.time);
    row.innerHTML = `<td>${index + 1}</td><td>${formatTime(event.time)}</td><td>${event.player}</td><td>${event.action}</td><td>${Math.round(event.x)}</td><td>${Math.round(event.y)}</td><td>${Math.round(event.width)}</td><td>${Math.round(event.height)}</td><td><button class="delete-btn" data-index="${index}">Borrar</button></td>`;
    row.addEventListener('click', () => {
      video.currentTime = Number(row.dataset.time);
      if (video.paused) video.play();
    });
    row.querySelector('.delete-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      removeEvent(index);
    });
    eventsBody.appendChild(row);
  });
}

function addTrackingEvent(box) {
  trackingEvents.push({
    time: video.currentTime,
    x: box.x,
    y: box.y,
    width: box.width,
    height: box.height,
    cx: box.cx,
    cy: box.cy,
    action: actionSelect.value,
    player: playerInput.value.trim() || 'No especificado'
  });
  redrawTracking();
  renderEventsTable();
  renderMetrics();
}

videoInput.addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  video.src = URL.createObjectURL(file);
  playPauseBtn.disabled = false;
  clearBtn.disabled = false;
});
video.addEventListener('loadedmetadata', syncCanvasSize);
window.addEventListener('resize', syncCanvasSize);

playPauseBtn.addEventListener('click', () => {
  if (!video.src) return;
  if (video.paused) video.play(); else video.pause();
});
video.addEventListener('pause', () => (playPauseBtn.textContent = '▶ Reproducir'));
video.addEventListener('play', () => (playPauseBtn.textContent = '⏸ Pausar'));

canvas.addEventListener('mousedown', (e) => {
  if (!video.src) return;
  isDrawing = true;
  dragStart = getCanvasPosition(e);
  previewRect = { x: dragStart.x, y: dragStart.y, width: 0, height: 0 };
  redrawTracking();
});

canvas.addEventListener('mousemove', (e) => {
  if (!isDrawing || !dragStart) return;
  previewRect = normalizeRect(dragStart, getCanvasPosition(e));
  redrawTracking();
});

canvas.addEventListener('mouseup', (e) => {
  if (!isDrawing || !dragStart) return;
  const box = normalizeRect(dragStart, getCanvasPosition(e));
  isDrawing = false;
  dragStart = null;
  previewRect = null;
  if (box.width < 3 || box.height < 3) {
    redrawTracking();
    return;
  }
  addTrackingEvent(box);
});

canvas.addEventListener('mouseleave', () => {
  if (!isDrawing) return;
  isDrawing = false;
  dragStart = null;
  previewRect = null;
  redrawTracking();
});

clearBtn.addEventListener('click', () => {
  trackingEvents.length = 0;
  previewRect = null;
  redrawTracking();
  renderEventsTable();
  renderMetrics();
});

renderMetrics();
