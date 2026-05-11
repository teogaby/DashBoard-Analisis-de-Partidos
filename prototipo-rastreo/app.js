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

const colorsByAction = {
  posición: '#ffffff',
  presión: '#31d66f',
  recuperación: '#4bc4ff',
  pérdida: '#ff6a6a',
  pase: '#ffd166',
  duelo: '#c77dff',
  desmarque: '#00f5d4'
};

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

function drawPoint(event, index) {
  const radius = 5;
  const color = colorsByAction[event.action] || '#fff';

  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(event.x, event.y, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#ffffff';
  ctx.font = '11px sans-serif';
  ctx.fillText(String(index + 1), event.x + 7, event.y - 7);
}

function redrawTracking() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (trackingEvents.length < 1) return;

  ctx.lineWidth = 2;
  ctx.strokeStyle = '#31d66f';
  ctx.beginPath();

  trackingEvents.forEach((event, index) => {
    if (index === 0) {
      ctx.moveTo(event.x, event.y);
    } else {
      ctx.lineTo(event.x, event.y);
    }
  });

  ctx.stroke();

  trackingEvents.forEach((event, index) => drawPoint(event, index));
}

function calculateDistance(events) {
  let total = 0;
  for (let i = 1; i < events.length; i += 1) {
    const dx = events[i].x - events[i - 1].x;
    const dy = events[i].y - events[i - 1].y;
    total += Math.sqrt(dx * dx + dy * dy);
  }
  return total;
}

function renderMetrics() {
  const byAction = trackingEvents.reduce((acc, ev) => {
    acc[ev.action] = (acc[ev.action] || 0) + 1;
    return acc;
  }, {});

  const totalPoints = trackingEvents.length;
  const totalActions = totalPoints;
  const distance = calculateDistance(trackingEvents);

  const actionItems = Object.entries(byAction)
    .map(([action, count]) => `<li>${action}: <strong>${count}</strong></li>`)
    .join('');

  metricsList.innerHTML = `
    <li>Total de puntos: <strong>${totalPoints}</strong></li>
    <li>Número de acciones: <strong>${totalActions}</strong></li>
    <li>Distancia relativa aprox.: <strong>${distance.toFixed(2)} px</strong></li>
    <li>
      Acciones por tipo:
      <ul>${actionItems || '<li>Sin datos</li>'}</ul>
    </li>
  `;
}

function renderEventsTable() {
  eventsBody.innerHTML = '';

  trackingEvents.forEach((event, index) => {
    const row = document.createElement('tr');
    row.dataset.time = String(event.time);
    row.innerHTML = `
      <td>${index + 1}</td>
      <td>${formatTime(event.time)}</td>
      <td>${event.player}</td>
      <td>${event.action}</td>
      <td>${Math.round(event.x)}</td>
      <td>${Math.round(event.y)}</td>
    `;

    row.addEventListener('click', () => {
      video.currentTime = Number(row.dataset.time);
      if (video.paused) {
        video.play();
      }
    });

    eventsBody.appendChild(row);
  });
}

function addTrackingEvent(x, y) {
  const player = playerInput.value.trim() || 'No especificado';
  const action = actionSelect.value;

  trackingEvents.push({
    time: video.currentTime,
    x,
    y,
    action,
    player
  });

  redrawTracking();
  renderEventsTable();
  renderMetrics();
}

videoInput.addEventListener('change', (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  const url = URL.createObjectURL(file);
  video.src = url;
  playPauseBtn.disabled = false;
  clearBtn.disabled = false;
});

video.addEventListener('loadedmetadata', syncCanvasSize);
window.addEventListener('resize', syncCanvasSize);

playPauseBtn.addEventListener('click', () => {
  if (!video.src) return;
  if (video.paused) {
    video.play();
    playPauseBtn.textContent = '⏸ Pausar';
  } else {
    video.pause();
    playPauseBtn.textContent = '▶ Reproducir';
  }
});

video.addEventListener('pause', () => {
  playPauseBtn.textContent = '▶ Reproducir';
});

video.addEventListener('play', () => {
  playPauseBtn.textContent = '⏸ Pausar';
});

canvas.addEventListener('click', (e) => {
  if (!video.src) return;

  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;

  const x = (e.clientX - rect.left) * scaleX;
  const y = (e.clientY - rect.top) * scaleY;

  addTrackingEvent(x, y);
});

clearBtn.addEventListener('click', () => {
  trackingEvents.length = 0;
  redrawTracking();
  renderEventsTable();
  renderMetrics();
});

renderMetrics();
