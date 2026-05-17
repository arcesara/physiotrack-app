// ============================================================
// sesion.js — PhysioTrack
// Tiempo real: heatmap, HR, EMG, equilibrio, reps/tiempo
// ============================================================

const socket = io();

const estadoBanner = document.getElementById('estado-banner');
const hrValor      = document.getElementById('hr-valor');
const emgValor     = document.getElementById('emg-valor');
const emgBar       = document.getElementById('emg-bar');
const eqIzqEl      = document.getElementById('eq-izq');
const eqDerEl      = document.getElementById('eq-der');
const eqIzqPct     = document.getElementById('eq-izq-pct');
const eqDerPct     = document.getElementById('eq-der-pct');
const resumenDiv   = document.getElementById('resumen');
const resumenAcc   = document.getElementById('resumen-acciones');

// Elementos modo rehab
const repsValorEl  = document.getElementById('reps-valor');
const repsBarEl    = document.getElementById('reps-bar');
// Elementos modo análisis
const tiempoValorEl = document.getElementById('tiempo-valor');
const tiempoBarEl   = document.getElementById('tiempo-bar');

// ─── HEATMAP ────────────────────────────────────────────────
const SENSOR_POS  = { talon: {x:65,y:210}, adel_izq: {x:38,y:90}, adel_der: {x:92,y:90} };
const RADIO       = 100;
const MAX_FUERZA  = 3;

function fuerzaAColor(ratio) {
  ratio = Math.max(0, Math.min(1, ratio));
  let r, g, b;
  if (ratio < 0.33) {
    const t = ratio / 0.33;
    r=255; g=255; b=Math.round(255*(1-t));
  } else if (ratio < 0.66) {
    const t=(ratio-0.33)/0.33;
    r=255; g=Math.round(255-t*153); b=0;
  } else {
    const t=(ratio-0.66)/0.34;
    r=255; g=Math.round(102*(1-t)); b=0;
  }
  return [r,g,b];
}

function trazarPieIzq(ctx) {
  ctx.beginPath();
  ctx.moveTo(40,242); ctx.quadraticCurveTo(18,228,17,195);
  ctx.quadraticCurveTo(14,158,20,118); ctx.quadraticCurveTo(23,88,28,62);
  ctx.quadraticCurveTo(33,38,44,22); ctx.quadraticCurveTo(55,8,65,8);
  ctx.quadraticCurveTo(76,8,79,20); ctx.quadraticCurveTo(83,33,81,50);
  ctx.quadraticCurveTo(90,46,97,51); ctx.quadraticCurveTo(104,57,101,68);
  ctx.quadraticCurveTo(108,65,111,72); ctx.quadraticCurveTo(114,81,108,90);
  ctx.quadraticCurveTo(112,93,113,100); ctx.quadraticCurveTo(114,110,108,115);
  ctx.quadraticCurveTo(105,135,103,158); ctx.quadraticCurveTo(101,185,95,212);
  ctx.quadraticCurveTo(85,252,65,254); ctx.quadraticCurveTo(50,254,40,242);
  ctx.closePath();
}

function trazarPieDer(ctx) {
  ctx.beginPath();
  ctx.moveTo(90,242); ctx.quadraticCurveTo(112,228,113,195);
  ctx.quadraticCurveTo(116,158,110,118); ctx.quadraticCurveTo(107,88,102,62);
  ctx.quadraticCurveTo(97,38,86,22); ctx.quadraticCurveTo(75,8,65,8);
  ctx.quadraticCurveTo(54,8,51,20); ctx.quadraticCurveTo(47,33,49,50);
  ctx.quadraticCurveTo(40,46,33,51); ctx.quadraticCurveTo(26,57,29,68);
  ctx.quadraticCurveTo(22,65,19,72); ctx.quadraticCurveTo(16,81,22,90);
  ctx.quadraticCurveTo(18,93,17,100); ctx.quadraticCurveTo(16,110,22,115);
  ctx.quadraticCurveTo(25,135,27,158); ctx.quadraticCurveTo(29,185,35,212);
  ctx.quadraticCurveTo(45,252,65,254); ctx.quadraticCurveTo(80,254,90,242);
  ctx.closePath();
}

function renderHeatmap(canvasId, valores, esDerecho) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.save();
  if (esDerecho) trazarPieDer(ctx); else trazarPieIzq(ctx);
  ctx.clip();
  ctx.fillStyle='#fff'; ctx.fillRect(0,0,canvas.width,canvas.height);
  const sensores = [
    {pos:SENSOR_POS.talon,    valor:valores.talon    ||0},
    {pos:SENSOR_POS.adel_izq, valor:valores.adel_izq ||0},
    {pos:SENSOR_POS.adel_der, valor:valores.adel_der ||0},
  ];
  [...sensores].sort((a,b)=>a.valor-b.valor).forEach(s=>{
    const ratio=Math.min(s.valor/MAX_FUERZA,1);
    if(ratio<0.005) return;
    const [r,g,b]=fuerzaAColor(ratio);
    const am=0.2+ratio*0.75;
    const gr=ctx.createRadialGradient(s.pos.x,s.pos.y,0,s.pos.x,s.pos.y,RADIO);
    gr.addColorStop(0,`rgba(${r},${g},${b},${am})`);
    gr.addColorStop(0.35,`rgba(${r},${g},${b},${am*0.65})`);
    gr.addColorStop(0.7,`rgba(${r},${g},${b},${am*0.25})`);
    gr.addColorStop(1,`rgba(${r},${g},${b},0)`);
    ctx.fillStyle=gr; ctx.fillRect(0,0,canvas.width,canvas.height);
  });
  ctx.restore();
  ctx.save(); if(esDerecho) trazarPieDer(ctx); else trazarPieIzq(ctx);
  ctx.strokeStyle='#c0c0c0'; ctx.lineWidth=1.5; ctx.stroke(); ctx.restore();
  sensores.forEach(s=>{
    const ratio=Math.min((s.valor||0)/MAX_FUERZA,1);
    const [r,g,b]=fuerzaAColor(ratio);
    ctx.beginPath(); ctx.arc(s.pos.x,s.pos.y,4,0,Math.PI*2);
    ctx.fillStyle=ratio>0.02?`rgb(${r},${g},${b})`:'#e0e0e0';
    ctx.fill(); ctx.strokeStyle='#999'; ctx.lineWidth=0.8; ctx.stroke();
  });
}

function actualizarHeatmaps(force_izq, force_der) {
  if (force_izq) {
    renderHeatmap('canvas-izq',{talon:force_izq.talon_izq||0,adel_izq:force_izq.adelante_izq||0,adel_der:force_izq.adelante_centro||0},true);
    const t=(force_izq.talon_izq||0)+(force_izq.adelante_izq||0)+(force_izq.adelante_centro||0);
    document.getElementById('iz-total').textContent=t.toFixed(1);
  }
  if (force_der) {
    renderHeatmap('canvas-der',{talon:force_der.talon_der||0,adel_izq:force_der.adelante_centro||0,adel_der:force_der.adelante_der||0},false);
    const t=(force_der.talon_der||0)+(force_der.adelante_centro||0)+(force_der.adelante_der||0);
    document.getElementById('der-total').textContent=t.toFixed(1);
  }
}

// ─── TIMER (modo análisis) ───────────────────────────────────
let timerInterval = null;
let tiempoRestante = DURACION_S;

function iniciarTimer() {
  if (MODO !== 'analisis' || !tiempoValorEl) return;
  tiempoRestante = DURACION_S;
  timerInterval = setInterval(() => {
    tiempoRestante = Math.max(0, tiempoRestante - 1);
    tiempoValorEl.textContent = tiempoRestante;
    if (tiempoBarEl) tiempoBarEl.style.width = (tiempoRestante / DURACION_S * 100) + '%';
    if (tiempoRestante <= 0) clearInterval(timerInterval);
  }, 1000);
}

// ─── WEBSOCKET ──────────────────────────────────────────────
socket.on('datos_sensores', datos => {
  actualizarHeatmaps(datos.force_izq, datos.force_der);

  if (datos.hr > 0 && hrValor) hrValor.textContent = datos.hr;

  if (emgValor && datos.emg !== undefined) {
    emgValor.textContent = datos.emg.toFixed(3);
    if (emgBar) emgBar.style.width = Math.min(datos.emg / 5 * 100, 100) + '%';
  }

  if (datos.pct_izq !== undefined) {
    eqIzqEl.style.width  = datos.pct_izq + '%';
    eqDerEl.style.width  = datos.pct_der + '%';
    eqIzqPct.textContent = datos.pct_izq + '%';
    eqDerPct.textContent = datos.pct_der + '%';
  }

  if (estadoBanner.className.includes('espera')) {
    estadoBanner.className = 'estado-banner estado-activo';
    estadoBanner.textContent = 'Sesión en curso';
    if (MODO === 'analisis') iniciarTimer();
  }
});

socket.on('rep_completada', datos => {
  if (!repsValorEl) return;
  repsValorEl.textContent = datos.rep;
  if (repsBarEl) repsBarEl.style.width = (datos.rep / REPS_TOTAL * 100) + '%';
  estadoBanner.className = 'estado-banner estado-activo';
  estadoBanner.textContent = `Ejercicio en curso — Rep ${datos.rep} / ${REPS_TOTAL}`;
});

socket.on('sesion_completada', datos => {
  clearInterval(timerInterval);
  estadoBanner.className = 'estado-banner estado-completado';
  estadoBanner.textContent = 'Sesión completada';
  resumenDiv.classList.remove('hidden');

  const resHr  = document.getElementById('res-hr');
  const resEmg = document.getElementById('res-emg');
  const resEq  = document.getElementById('res-eq');
  const resReps = document.getElementById('res-reps');
  const resDur  = document.getElementById('res-dur');

  if (resHr)  resHr.textContent  = datos.hr_medio;
  if (resEmg) resEmg.textContent = datos.emg_medio;
  if (resEq)  resEq.textContent  = datos.equilibrio;
  if (resReps) resReps.textContent = datos.reps;
  if (resDur)  resDur.textContent = Math.round(datos.duracion);

  let html = '';
  if (datos.completada && datos.siguiente_nivel <= 5) {
    html += `<a href="/sesion/${datos.modo}/${datos.ejercicio_id}/${datos.siguiente_nivel}" class="btn-primary">Subir a nivel ${datos.siguiente_nivel}</a>`;
  }
  html += `<a href="/sesion/${datos.modo}/${datos.ejercicio_id}/${datos.nivel}" class="btn-secondary">Repetir nivel ${datos.nivel}</a>`;
  html += `<a href="/modo/${datos.modo}" class="btn-secondary">Ver ejercicios</a>`;
  if (resumenAcc) resumenAcc.innerHTML = html;
});

// ─── INIT ───────────────────────────────────────────────────
renderHeatmap('canvas-izq',{talon:0,adel_izq:0,adel_der:0},true);
renderHeatmap('canvas-der',{talon:0,adel_izq:0,adel_der:0},false);
