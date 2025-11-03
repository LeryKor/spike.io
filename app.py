import os, random, time
from math import sqrt, atan2, cos, sin
from flask import Flask, Response, request
from flask_socketio import SocketIO, emit

# ---------- ПАРАМЕТРЫ ----------
WORLD_W, WORLD_H = 20000, 12000
WORLD_RADIUS = min(WORLD_W, WORLD_H) // 2
WORLD_CENTER = (WORLD_W / 2, WORLD_H / 2)
PELLET_COUNT = 1000
PELLET_RADIUS = 6
PLAYER_RADIUS = 22
PLAYER_SPEED = 220
BOOST_MULT = 2.0
ROT_SPEED = 4.0
TICK_RATE = 30
BASE_DAMAGE = 50
MAX_HP = 100
SHARP_LEN = 12
DAMAGE_COOLDOWN = 0.6
PUSH_STRENGTH = 10.0

# ---------- СЕРВЕР ----------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

players = {}
pellets = []
last_hits = {}

# ---------- УТИЛИТЫ ----------
def rand_color_type():
    color = random.choice(["#ff4b4b", "#3adb40", "#3da9ff"])  # приятные голубые оттенки
    return "score", color

def respawn_pellet():
    """Создаёт пеллет внутри круга арены"""
    t, c = rand_color_type()
    while True:
        x = random.uniform(PELLET_RADIUS, WORLD_W - PELLET_RADIUS)
        y = random.uniform(PELLET_RADIUS, WORLD_H - PELLET_RADIUS)
        cx, cy = WORLD_CENTER
        if sqrt((x - cx) ** 2 + (y - cy) ** 2) <= WORLD_RADIUS - PELLET_RADIUS:
            return {"x": x, "y": y, "type": t, "color": c}

def ensure_pellets():
    while len(pellets) < PELLET_COUNT:
        pellets.append(respawn_pellet())

def distance(ax, ay, bx, by):
    return sqrt((ax-bx)**2 + (ay-by)**2)

# ---------- HTML ----------
@app.route("/")
def index():
    html = f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Spike.io</title>
<style>
html,body{{margin:0;padding:0;height:100%;overflow:hidden;background:#0f1220;color:#fff;font-family:'Inter',system-ui;}}
canvas{{width:100vw;height:100vh;display:block;cursor:crosshair;}}
#hud{{position:fixed;top:10px;left:10px;background:rgba(0,0,0,.3);padding:12px 16px;border-radius:12px;backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,0.15);box-shadow:0 0 10px rgba(255,255,255,0.1);}}
#minimap {{
  position: fixed;
  right: 20px;
  bottom: 20px;
  width: 220px;
  height: 220px;
  aspect-ratio: 1 / 1;
  object-fit: contain;
  background: rgba(15, 18, 32, 0.6);
  border: 2px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  box-shadow: 0 0 20px rgba(64, 201, 255, 0.15);
  backdrop-filter: blur(6px);
  z-index: 50;
  display: none;
}}

#leaderboard {{
  position: fixed;
  right: 20px;
  top: 20px;
  width: 220px;
  background: rgba(15, 18, 32, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  padding: 10px 14px;
  font-size: 15px;
  color: #fff;
  backdrop-filter: blur(6px);
  box-shadow: 0 0 15px rgba(64, 201, 255, 0.1);
  z-index: 50;
  display: none;
}}
#leaderboard h3 {{
  font-size: 16px;
  text-align: center;
  margin: 4px 0 8px;
  color: #40c9ff;
  text-shadow: 0 0 8px rgba(64, 201, 255, 0.6);
}}
#leaderList {{
  margin: 0;
  padding-left: 20px;
  list-style: none;
}}
#leaderList li {{
  margin: 3px 0;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
}}
#leaderList li.me {{
  color: #40c9ff;
  font-weight: bold;
}}

#buffContainer {{
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  display: none;
  gap: 20px;
  z-index: 20;
}}

.buffCard {{
  background: rgba(30,34,60,0.9);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 12px;
  padding: 14px 20px;
  font-size: 18px;
  color: white;
  box-shadow: 0 0 20px rgba(64,201,255,0.2);
  backdrop-filter: blur(8px);
  transition: 0.25s;
  min-width: 200px;
  text-align: center;
}}
.buffCard:hover {{
  background: rgba(50,55,90,0.95);
  box-shadow: 0 0 25px rgba(64,201,255,0.4);
  transform: translateY(-4px);
}}
#healthbar{{width:220px;height:18px;background:#222;border-radius:6px;overflow:hidden;margin-bottom:8px;position:relative;box-shadow:inset 0 0 4px #000;}}
#healthfill{{position:absolute;left:0;top:0;height:100%;background:linear-gradient(90deg,#00ff88,#ff4455);transition:width 0.15s;}}
#stats{{font-size:15px;line-height:1.4em;}}
#menu,#death{{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:radial-gradient(circle at center,#141628,#0f1220);gap:20px;font-size:18px;color:white;text-align:center;}}
#menu input,#menu button,#menu select,#death button{{padding:10px 18px;font-size:18px;border:none;border-radius:8px;outline:none;}}
#menu select{{background:#1b1e34;color:white;cursor:pointer;transition:0.25s;border:1px solid rgba(255,255,255,0.2);box-shadow:inset 0 0 8px rgba(255,255,255,0.1);}}
#menu select:hover{{background:#262a45;box-shadow:0 0 10px rgba(64,201,255,0.4);}}
#menu label{{font-size:16px;margin-top:6px;opacity:0.9;}}
#menu button,#death button{{background:#40c9ff;color:white;cursor:pointer;transition:0.25s all;box-shadow:0 0 20px #40c9ff55;}}
#menu button:hover,#death button:hover{{transform:scale(1.05);background:#5ed3ff;box-shadow:0 0 25px #5ed3ffaa;}}
#menu{{animation:fadeIn 0.6s ease-out;}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(20px);}}to{{opacity:1;transform:translateY(0);}}}}
#menu{{animation:fadeIn 0.8s ease-out;}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(20px);}}to{{opacity:1;transform:translateY(0);}}}}
#death {{
  display:none;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  background:rgba(0,0,0,0.85);
  font-size:24px;
  text-align:center;
  color:white;
  text-shadow:0 0 10px #ff3030;
  z-index: 9999;
}}
/* --- карточка персонажа на главном экране --- */
#characterCard{{ 
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  gap:12px;
  padding:20px 28px;
  background:rgba(20,24,40,0.8);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:16px;
  box-shadow:0 0 25px rgba(64,201,255,0.08);
  backdrop-filter:blur(10px);
  margin-top:10px;
}}

#characterCard label{{font-size:16px;opacity:0.85;margin-top:4px;}}
#characterCard select,#characterCard input{{width:200px;text-align:center;}}
#characterCard select{{background:#1b1e34;color:white;border:none;border-radius:8px;padding:8px;cursor:pointer;
box-shadow:inset 0 0 8px rgba(255,255,255,0.1);transition:0.25s;}}
#characterCard select:hover{{background:#262a45;box-shadow:0 0 10px rgba(64,201,255,0.4);}}
#previewContainer{{margin-top:6px;display:flex;flex-direction:column;align-items:center;}}
#menu h1{{margin-bottom:0;}}
.rules{{max-width:460px;line-height:1.6;font-size:16px;opacity:0.9;}}
.rules span{{display:inline-block;margin:4px 0;}}
.color-circle{{display:inline-block;width:14px;height:14px;border-radius:50%;margin-right:6px;vertical-align:middle;box-shadow:0 0 6px currentColor;}}
</style></head>
<body>
<canvas id="game"></canvas>

<div id="hud" style="display:none">
  <div id="healthbar"><div id="healthfill"></div></div>
  <div id="stats">
    ❤️ <span id="hpText">100 / 100</span><br/>
    ⚔️ Damage: <span id="damageText">50</span>
    <br/>⭐ Score: <span id="scoreText">0</span>
  </div>
</div>

<!-- Миникарта -->
<canvas id="minimap"></canvas>

<!-- Таблица лидеров -->
<div id="leaderboard">
  <h3>🏆 Топ игроков</h3>
  <ol id="leaderList"></ol>
</div>

<div id="buffContainer"></div>

<div id="menu">
  <h1 style="font-size:46px;text-shadow:0 0 22px #40c9ff;">Spike.io</h1>
  <div class="rules">
    <p>Добро пожаловать в <b>Spike.io</b>!</p>
    <p>Правила просты:</p>
    <span><span class="color-circle" style="background:#40c9ff"></span> Собирайте сферы, чтобы повышать <b>счёт</b>!</span><br>Каждые 50 очков вы можете выбрать 1 из 3 улучшений.<br>
    Управляйте мышью. Зажмите ЛКМ, чтобы ускориться — но HP при этом убывает!<br>
    Атакуйте врагов вашим шипом ⚔️ и набирайте очки!
  </div>
  <div id="characterCard">
      <input id="nameInput" placeholder="Ваш ник" maxlength="16"/>
    
      <div id="previewContainer">
        <canvas id="previewCanvas" width="160" height="160" 
          style="width:160px;height:160px;border-radius:50%;
                 background:radial-gradient(circle at 50% 50%, #20233a, #0f1220);
                 box-shadow:0 0 15px rgba(255,255,255,0.08);
                 image-rendering:pixelated;"></canvas>
        <div style="font-size:14px;opacity:0.7;margin-top:6px;">Превью персонажа</div>
      </div>
    
      <label>🎨 Цвет персонажа:</label>
      <select id="colorSelect">
        <option value="#ffca3a">Жёлтый</option>
        <option value="#8ac926">Зелёный</option>
        <option value="#1982c4">Синий</option>
        <option value="#6a4c93">Фиолетовый</option>
        <option value="#ff595e">Красный</option>
      </select>
    
      <label>🦄 Тип шипа:</label>
      <select id="spikeSelect">
        <option value="classic">Classic</option>
        <option value="unicorn">Unicorn</option>
        <option value="blade">Blade</option>
        <option value="lazer">Lazer</option>
      </select>
    
      <button id="playBtn" style="margin-top:10px;">Играть</button>
  </div>
</div>

<div id="death">
  <div id="deathText" style="font-size:42px;font-weight:600;text-shadow:0 0 20px #ff4040;">💀 Вы умерли!</div>
  <div id="finalScore" style="margin-top:10px;font-size:24px;opacity:0.9;"></div>
  <button id="restartBtn" style="margin-top:16px;">Играть снова</button>
</div>

<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
const WORLD_W={WORLD_W},WORLD_H={WORLD_H},WORLD_RADIUS={WORLD_RADIUS},
      PLAYER_RADIUS={PLAYER_RADIUS},PELLET_RADIUS={PELLET_RADIUS},
      TICK_RATE={TICK_RATE},SHARP_LEN={SHARP_LEN};
const canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
const hud=document.getElementById('hud'),menu=document.getElementById('menu'),death=document.getElementById('death');
const hpText=document.getElementById('hpText'),damageText=document.getElementById('damageText'),hpFill=document.getElementById('healthfill');
const nameInput=document.getElementById('nameInput'),playBtn=document.getElementById('playBtn'),restartBtn=document.getElementById('restartBtn');
const colorSelect=document.getElementById('colorSelect'),
      spikeSelect=document.getElementById('spikeSelect');
const previewCanvas=document.getElementById('previewCanvas'),
      pctx=previewCanvas.getContext('2d');
let previewColor=colorSelect.value, previewSpike=spikeSelect.value, previewAngle=0;



function resize(){{canvas.width=window.innerWidth;canvas.height=window.innerHeight;}}window.addEventListener('resize',resize);resize();

const socket=io();
let me=null,players={{}},pellets=[],mouse={{x:0,y:0}},boosting=false;
let sparks=[],trail=[];

canvas.addEventListener('mousemove',e=>{{mouse.x=e.clientX;mouse.y=e.clientY;}});
canvas.addEventListener('mousedown',()=>{{boosting=true;socket.emit('boost',{{state:true}});}});
canvas.addEventListener('mouseup',()=>{{boosting=false;socket.emit('boost',{{state:false}});}});

// обновление превью при выборе цвета или шипа
function updatePreview(){{
  previewColor=colorSelect.value;
  previewSpike=spikeSelect.value;
}}
colorSelect.addEventListener('change', updatePreview);
spikeSelect.addEventListener('change', updatePreview);

// цикл отрисовки превью
function drawPreview() {{
  const dpr = window.devicePixelRatio || 1;
  const w = 160, h = 160;
  previewCanvas.width = w * dpr;
  previewCanvas.height = h * dpr;
  previewCanvas.style.width = w + 'px';
  previewCanvas.style.height = h + 'px';
  pctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  const cx = w / 2, cy = h / 2;
  pctx.clearRect(0, 0, w, h);

  // фон
  const g = pctx.createRadialGradient(cx, cy, 20, cx, cy, 80);
  g.addColorStop(0, '#181a2f');
  g.addColorStop(1, '#0f1220');
  pctx.fillStyle = g;
  pctx.fillRect(0, 0, w, h);

  // тело персонажа
  pctx.beginPath();
  pctx.fillStyle = previewColor;
  pctx.shadowBlur = 12;
  pctx.shadowColor = previewColor;
  pctx.arc(cx, cy, PLAYER_RADIUS, 0, Math.PI * 2);
  pctx.fill();
  pctx.shadowBlur = 0;

  // отрисовка шипа
  try {{
    drawSpikeCtx(pctx, {{ spike: previewSpike, angle: previewAngle }}, cx, cy);
  }} catch(e) {{
    console.error("Ошибка в drawSpike preview:", e);
  }}


  previewAngle += 0.02;
  requestAnimationFrame(drawPreview);
}}
drawPreview();



playBtn.onclick=()=>{{
  const n=(nameInput.value||"Player").slice(0,16);
  const color=colorSelect.value;
  const spike=spikeSelect.value;
  socket.emit('spawn',{{name:n,color:color,spike:spike}}); // передаем выбранные параметры
  menu.style.display='none';
  hud.style.display='block';
  minimap.style.display = 'block';
  leaderboard.style.display = 'block';
}};
restartBtn.onclick = () => {{
  death.style.display = 'none';
  menu.style.display = 'flex';
  minimap.style.display = 'none';
  leaderboard.style.display = 'none';
}};

socket.on('welcome',d=>{{me=d.me;players=d.players;pellets=d.pellets;updateStats();}});
socket.on('state',d=>{{players=d.players;pellets=d.pellets;if(players[socket.id]){{me=players[socket.id];updateStats();}}}});
socket.on('dead', data => {{
  const score = data && typeof data.score !== 'undefined' ? data.score : (me ? me.score : 0);
  me = null;
  players = {{}};
  pellets = [];
  hud.style.display = 'none';
  death.style.display = 'flex';
  menu.style.display = 'none';
  minimap.style.display = 'none';
  leaderboard.style.display = 'none';
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const scoreEl = document.getElementById('finalScore');
  if (scoreEl) {{
    scoreEl.textContent = `⭐ Ваш счёт: ${{score}}`;
  }}
}});

socket.on('spark', s => {{
  sparks.push({{x:s.x,y:s.y,life:0.4,particles:Array.from({{length:12}},()=>({{
    vx:(Math.random()-0.5)*320, vy:(Math.random()-0.5)*320, r:Math.random()*2+1
  }}))}});
}});

let floatTexts = [];

socket.on('kill_bonus', data => {{
  floatTexts.push({{
    x: data.x,
    y: data.y,
    value: data.value,
    life: 1.0 // секунда жизни
  }});
}});

function updateStats() {{
  if (!me) return;
  hpText.textContent = Math.round(me.hp) + " / " + Math.round(me.max_hp);
  damageText.textContent = me.damage;
  const scoreEl = document.getElementById('scoreText');
  if (scoreEl) scoreEl.textContent = me.score || 0;
  hpFill.style.width = (Math.max(0, me.hp / me.max_hp) * 100) + '%';
}}

setInterval(()=>{{if(!me)return;const wx=me.x+(mouse.x-canvas.width/2),wy=me.y+(mouse.y-canvas.height/2);socket.emit('input',{{targetX:wx,targetY:wy}});}},1000/TICK_RATE);

// --- отрисовка шипов в любой контекст ---
function drawSpikeCtx(gctx, pl, sx, sy) {{
  const sizeMul = pl.spike_size || 1.0;
  const lenMul = pl.spike_length || 1.0;
  const spike = pl.spike || "classic";
  const angle = pl.angle;
  gctx.save();

  if (spike === 'classic') {{
      gctx.beginPath();
      const tipX = sx + Math.cos(angle)*(PLAYER_RADIUS*sizeMul + SHARP_LEN*lenMul);
      const tipY = sy + Math.sin(angle)*(PLAYER_RADIUS*sizeMul + SHARP_LEN*lenMul);
      gctx.moveTo(tipX, tipY);
      gctx.lineTo(sx + Math.cos(angle+2.5)*(PLAYER_RADIUS*sizeMul-4), sy + Math.sin(angle+2.5)*(PLAYER_RADIUS*sizeMul-4));
      gctx.lineTo(sx + Math.cos(angle-2.5)*(PLAYER_RADIUS*sizeMul-4), sy + Math.sin(angle-2.5)*(PLAYER_RADIUS*sizeMul-4));
      gctx.closePath();
      gctx.fillStyle = '#fff';
      gctx.fill();
  }} 
  else if (spike === 'unicorn') {{
    const len = SHARP_LEN *lenMul * 2.5;
    const tipX = sx + Math.cos(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const tipY = sy + Math.sin(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const grad = gctx.createLinearGradient(sx, sy, tipX, tipY);
    grad.addColorStop(0, '#ff00ff');
    grad.addColorStop(0.25, '#00ffff');
    grad.addColorStop(0.5, '#00ff88');
    grad.addColorStop(0.75, '#ffff00');
    grad.addColorStop(1, '#ff00ff');
    gctx.beginPath();
    gctx.moveTo(tipX, tipY);
    gctx.lineTo(sx + Math.cos(angle+2.2)*(PLAYER_RADIUS*sizeMul-5), sy + Math.sin(angle+2.2)*(PLAYER_RADIUS*sizeMul-5));
    gctx.lineTo(sx + Math.cos(angle-2.2)*(PLAYER_RADIUS*sizeMul-5), sy + Math.sin(angle-2.2)*(PLAYER_RADIUS*sizeMul-5));
    gctx.closePath();
    gctx.fillStyle = grad;
    gctx.shadowBlur = 25;
    gctx.shadowColor = '#ffffff';
    gctx.fill();
    gctx.beginPath();
    gctx.arc(tipX, tipY, 3, 0, Math.PI*2);
    gctx.fillStyle = 'rgba(255,255,255,0.9)';
    gctx.fill();
  }} 
  else if (spike === 'blade') {{
    const len = SHARP_LEN *lenMul * 1.8;
    const tipX = sx + Math.cos(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const tipY = sy + Math.sin(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const side1X = sx + Math.cos(angle+0.5)*(PLAYER_RADIUS*sizeMul-6);
    const side1Y = sy + Math.sin(angle+0.5)*(PLAYER_RADIUS*sizeMul-6);
    const side2X = sx + Math.cos(angle-0.5)*(PLAYER_RADIUS*sizeMul-6);
    const side2Y = sy + Math.sin(angle-0.5)*(PLAYER_RADIUS*sizeMul-6);
    const grad = gctx.createLinearGradient(sx, sy, tipX, tipY);
    grad.addColorStop(0, '#888');
    grad.addColorStop(0.2, '#cfd8e0');
    grad.addColorStop(0.5, '#ffffff');
    grad.addColorStop(0.8, '#9bb2c3');
    grad.addColorStop(1, '#5a6d7f');
    gctx.beginPath();
    gctx.moveTo(tipX, tipY);
    gctx.lineTo(side1X, side1Y);
    gctx.lineTo(side2X, side2Y);
    gctx.closePath();
    gctx.fillStyle = grad;
    gctx.shadowBlur = 10;
    gctx.shadowColor = '#aee6ff';
    gctx.fill();
    gctx.beginPath();
    const midX = (sx + tipX) / 2;
    const midY = (sy + tipY) / 2;
    gctx.moveTo(midX, midY);
    gctx.lineTo(tipX, tipY);
    gctx.strokeStyle = 'rgba(255,255,255,0.5)';
    gctx.lineWidth = 1.2;
    gctx.stroke();
  }} 
  else if (spike === 'lazer') {{
    const len = SHARP_LEN *lenMul * 2.4;
    const tipX = sx + Math.cos(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const tipY = sy + Math.sin(angle)*(PLAYER_RADIUS*sizeMul + len*lenMul);
    const grad = gctx.createLinearGradient(sx, sy, tipX, tipY);
    grad.addColorStop(0, 'rgba(255,50,50,0.1)');
    grad.addColorStop(0.5, 'rgba(255,80,80,0.8)');
    grad.addColorStop(1, 'rgba(255,200,200,1)');
    gctx.beginPath();
    gctx.moveTo(sx, sy);
    gctx.lineTo(tipX, tipY);
    gctx.strokeStyle = grad;
    gctx.lineWidth = 3;
    gctx.shadowBlur = 15;
    gctx.shadowColor = '#ff3030';
    gctx.stroke();
    gctx.beginPath();
    gctx.arc(tipX, tipY, 3, 0, Math.PI*2);
    gctx.fillStyle = 'rgba(255,255,255,0.9)';
    gctx.shadowBlur = 20;
    gctx.shadowColor = '#ff4040';
    gctx.fill();
  }}

  gctx.restore();
}}


// --- отрисовка шипов (blade = металл, lazer = лазер) ---
function drawSpike(pl, sx, sy) {{
  // рисуем тем же кодом, но в контекст игрового canvas
  drawSpikeCtx(ctx, pl, sx, sy);
}}


// --- баффы ---
const buffContainer = document.getElementById('buffContainer');
let activeBuffs = [];

socket.on('buff_choices', buffs => {{
  buffContainer.innerHTML = '';
  buffs.forEach((b, i) => {{
    const div = document.createElement('div');
    div.className = 'buffCard';
    div.textContent = `${{i+1}}️⃣ ${{b.name}}`;
    buffContainer.appendChild(div);
  }});
  buffContainer.style.display = 'flex';
  activeBuffs = buffs;
}});

window.addEventListener('keydown', e => {{
  if (!activeBuffs.length) return;
  const n = parseInt(e.key);
  if (n >= 1 && n <= 3) {{
    socket.emit('choose_buff', {{ index: n - 1 }});
    buffContainer.style.display = 'none';
    activeBuffs = [];
  }}
}});

function drawBackground(time) {{
  const gradient = ctx.createRadialGradient(canvas.width/2, canvas.height/2, 200, canvas.width/2, canvas.height/2, canvas.width * 1.2);
  gradient.addColorStop(0, '#15182c');
  gradient.addColorStop(1, '#0c0f1d');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (!me) return;

  // --- рисуем красную границу карты ---
  const camX = me.x - canvas.width/2;
  const camY = me.y - canvas.height/2;
  const worldCenterX = WORLD_W / 2 - camX;
  const worldCenterY = WORLD_H / 2 - camY;

  ctx.beginPath();
  ctx.arc(worldCenterX, worldCenterY, WORLD_RADIUS, 0, Math.PI * 2);
  ctx.strokeStyle = 'rgba(255,60,60,0.6)';
  ctx.lineWidth = 6;
  ctx.shadowBlur = 15;
  ctx.shadowColor = '#ff3030';
  ctx.stroke();
  ctx.shadowBlur = 0;
}}

function drawSparks(dt, camX, camY){{ 
  for(const s of sparks) {{
    s.life-=dt;
    const t=0.4-s.life;
    for(const p of s.particles) {{
      const sx=s.x-camX+p.vx*t,sy=s.y-camY+p.vy*t;
      ctx.beginPath();
      ctx.fillStyle='rgba(255,220,100,'+Math.max(0,s.life*2).toFixed(3)+')';
      ctx.shadowBlur=12;ctx.shadowColor='#ffb400';
      ctx.arc(sx,sy,p.r,0,Math.PI*2);
      ctx.fill();
    }}
  }}
  ctx.shadowBlur=0;
  sparks=sparks.filter(s=>s.life>0);
}}

let lastTS=performance.now();
function draw(){{ 
  const nowTS=performance.now();
  const dt=Math.min(0.05,(nowTS-lastTS)/1000.0);
  lastTS=nowTS;

  if(!me){{requestAnimationFrame(draw);return;}}
  const camX=me.x-canvas.width/2,camY=me.y-canvas.height/2;

  drawBackground(nowTS*0.0002);

  for(const p of pellets){{const sx=p.x-camX,sy=p.y-camY;
    ctx.beginPath();ctx.fillStyle=p.color;ctx.shadowBlur=12;ctx.shadowColor=p.color;
    ctx.arc(sx,sy,PELLET_RADIUS,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}}

  const myTrail={{x:me.x,y:me.y,time:nowTS}};
  trail.push(myTrail);
  trail=trail.filter(t=>nowTS-t.time<400);
  for(const t of trail) {{
    const age=(nowTS-t.time)/400;
    ctx.beginPath();
    ctx.fillStyle='rgba(255,255,255,'+(1-age)*0.2+')';
    ctx.arc(t.x-camX,t.y-camY,PLAYER_RADIUS*(1-age*0.7),0,Math.PI*2);
    ctx.fill();
  }}

  for(const sid in players){{ 
      const pl=players[sid]; 
      const sx=pl.x-camX, sy=pl.y-camY;
      ctx.beginPath();
      ctx.fillStyle=pl.color;
      ctx.shadowBlur=20;
      ctx.shadowColor=pl.color;
      ctx.arc(sx,sy,PLAYER_RADIUS,0,Math.PI*2);
      ctx.fill();
      ctx.shadowBlur=0;
    
      drawSpike(pl, sx, sy);
    
      ctx.fillStyle='rgba(255,255,255,0.9)';
      ctx.font='15px Inter';
      ctx.textAlign='center';
      ctx.fillText(pl.name,sx,sy-PLAYER_RADIUS-12);
    }}

  // --- отрисовка границы карты ---
  const worldCenterX = WORLD_W/2 - camX;
  const worldCenterY = WORLD_H/2 - camY;
  const pulse = Math.sin(performance.now() * 0.003) * 0.15 + 0.85;

  ctx.beginPath();
  ctx.arc(worldCenterX, worldCenterY, WORLD_RADIUS, 0, Math.PI * 2);
  ctx.strokeStyle = `rgba(255,80,80,${{pulse}})`;
  ctx.lineWidth = 20;
  ctx.shadowBlur = 40;
  ctx.shadowColor = '#ff4040';
  ctx.stroke();
  ctx.shadowBlur = 0;
  drawSparks(dt,camX,camY);
  for (const t of floatTexts) {{
  t.life -= dt;
  const camX = me.x - canvas.width/2;
  const camY = me.y - canvas.height/2;
  const alpha = Math.max(0, t.life);
  const sy = t.y - camY - (1.0 - t.life) * 40; // всплывает вверх
  const sx = t.x - camX;
  ctx.save();
  ctx.font = 'bold 26px Inter';
  ctx.fillStyle = `rgba(255,200,80,${{alpha}})`;
  ctx.shadowBlur = 20;
  ctx.shadowColor = '#ffcc66';
  ctx.textAlign = 'center';
  ctx.fillText('+' + t.value, sx, sy);
  ctx.restore();
  }}
  floatTexts = floatTexts.filter(t => t.life > 0);
  if(boosting){{ctx.beginPath();ctx.arc(canvas.width/2,canvas.height/2,PLAYER_RADIUS+14,0,Math.PI*2);ctx.strokeStyle='rgba(255,255,255,0.3)';ctx.lineWidth=2;ctx.stroke();}}
  
  // --- Миникарта и лидерборд ---
 const minimap = document.getElementById('minimap');
 const mctx = minimap.getContext('2d');
 const leaderList = document.getElementById('leaderList');

 function drawMinimap() {{
   minimap.width = minimap.clientWidth;
   minimap.height = minimap.clientHeight;
   const w = minimap.width, h = minimap.height;
   mctx.clearRect(0, 0, w, h);  

   const scale = (w / 2) / WORLD_RADIUS;
   const cx = w / 2, cy = h / 2;

   // фон карты
   mctx.beginPath();
   mctx.arc(cx, cy, WORLD_RADIUS * scale, 0, Math.PI * 2);
   mctx.fillStyle = 'rgba(30, 34, 60, 0.8)';
   mctx.fill();
   mctx.strokeStyle = 'rgba(255, 60, 60, 0.4)';
   mctx.lineWidth = 2;
   mctx.stroke();

   // точки игроков
   for (const sid in players) {{
     const p = players[sid];
     const px = cx + (p.x - WORLD_W / 2) * scale;
     const py = cy + (p.y - WORLD_H / 2) * scale;
     mctx.beginPath();
     mctx.arc(px, py, 3, 0, Math.PI * 2);
     if (sid === socket.id) {{
       mctx.fillStyle = '#40c9ff';
       mctx.shadowBlur = 6;
       mctx.shadowColor = '#40c9ff';
     }} else {{
       mctx.fillStyle = 'rgba(255,255,255,0.7)';
       mctx.shadowBlur = 0;
     }}
     mctx.fill();
   }}
 }}

 function updateLeaderboard() {{
   const sorted = Object.values(players)
     .sort((a, b) => b.score - a.score)
     .slice(0, 10);

   leaderList.innerHTML = '';
   sorted.forEach((p, i) => {{
     const li = document.createElement('li');
     li.textContent = `${{i + 1}}. ${{p.name}} — ${{p.score}}`;
     if (p.sid === socket.id) li.classList.add('me');
     leaderList.appendChild(li);
   }});
 }}
  drawMinimap();
  updateLeaderboard();
  requestAnimationFrame(draw);
  
}}draw();
</script></body></html>"""
    return Response(html, mimetype="text/html")


# ---------- СЕРВЕРНЫЕ СОБЫТИЯ (без изменений логики) ----------
@socketio.on("spawn")
def spawn(data):
    sid=request.sid
    name=str(data.get("name","Player"))[:16]
    color = data.get("color", random.choice(["#ffca3a", "#8ac926", "#1982c4", "#6a4c93", "#ff9f1c"]))
    spike = data.get("spike", "classic")
    x=random.randint(PLAYER_RADIUS,WORLD_W-PLAYER_RADIUS)
    y=random.randint(PLAYER_RADIUS,WORLD_H-PLAYER_RADIUS)
    players[sid] = {
        "x": x,
        "y": y,
        "tx": x,
        "ty": y,
        "angle": 0.0,
        "hp": MAX_HP,
        "max_hp": MAX_HP,
        "damage": BASE_DAMAGE,
        "regen": 5.0,
        "speed_mult": 1.0,
        "boost_mult": 1.0,
        "spike_size": 1.0,
        "spike_length": 1.0,
        "score": 0,
        "boost": False,
        "name": name,
        "color": color,
        "spike": spike

    }

    ensure_pellets()
    emit("welcome", {"me": {**players[sid], "sid": sid}, "players": players, "pellets": pellets})

@socketio.on("disconnect")
def disconnect(): players.pop(request.sid,None)

@socketio.on("input")
def on_input(data):
    sid=request.sid
    if sid not in players:return
    players[sid]["tx"]=float(data.get("targetX",players[sid]["x"]))
    players[sid]["ty"]=float(data.get("targetY",players[sid]["y"]))

@socketio.on("boost")
def on_boost(data):
    sid=request.sid
    if sid in players: players[sid]["boost"]=bool(data.get("state",False))

# ---------- ЛОГИКА ----------
def handle_pvp():
    now=time.time()
    sids=list(players.keys())
    for i in range(len(sids)):
        for j in range(i+1,len(sids)):
            sid_a,sid_b=sids[i],sids[j]
            a,b=players[sid_a],players[sid_b]
            key = frozenset({sid_a, sid_b})


            dx=b["x"]-a["x"]; dy=b["y"]-a["y"]; dist=sqrt(dx*dx+dy*dy)
            if dist==0: continue

            overlap=PLAYER_RADIUS*2-dist
            if overlap>0:
                nx,ny=dx/dist,dy/dist
                impulse=overlap*5.0
                a["vx"]=a.get("vx",0)-nx*impulse
                a["vy"]=a.get("vy",0)-ny*impulse
                b["vx"]=b.get("vx",0)+nx*impulse
                b["vy"]=b.get("vy",0)+ny*impulse

            tip_ax = a["x"] + cos(a["angle"]) * (
                        PLAYER_RADIUS * a.get("spike_size", 1.0) + SHARP_LEN * a.get("spike_length", 1.0))
            tip_ay = a["y"] + sin(a["angle"]) * (
                        PLAYER_RADIUS * a.get("spike_size", 1.0) + SHARP_LEN * a.get("spike_length", 1.0))
            tip_bx = b["x"] + cos(b["angle"]) * (
                        PLAYER_RADIUS * b.get("spike_size", 1.0) + SHARP_LEN * b.get("spike_length", 1.0))
            tip_by = b["y"] + sin(b["angle"]) * (
                        PLAYER_RADIUS * b.get("spike_size", 1.0) + SHARP_LEN * b.get("spike_length", 1.0))

            if distance(tip_ax,tip_ay,b["x"],b["y"])<PLAYER_RADIUS and distance(tip_bx,tip_by,a["x"],a["y"])>PLAYER_RADIUS:
                if now-last_hits.get(key,0)>DAMAGE_COOLDOWN:
                    b["hp"]=max(0,b["hp"]-a["damage"]); last_hits[key]=now
                    socketio.emit("spark", {"x": b["x"], "y": b["y"]})
                    b["last_hit_time"] = now
                    # если игрок B умер — начисляем убийце +30 очков
                    if b["hp"] <= 0:
                        old_score = a["score"]
                        a["score"] += 30
                        # Проверяем, пересёк ли игрок ближайший порог 50
                        if (old_score // 50) < (a["score"] // 50):
                            give_buff_options(sid_a)
                        socketio.emit("kill_bonus", {"x": a["x"], "y": a["y"], "value": 30})
            elif distance(tip_bx,tip_by,a["x"],a["y"])<PLAYER_RADIUS and distance(tip_ax,tip_ay,b["x"],b["y"])>PLAYER_RADIUS:
                if now-last_hits.get(key,0)>DAMAGE_COOLDOWN:
                    a["hp"]=max(0,a["hp"]-b["damage"]); last_hits[key]=now
                    socketio.emit("spark", {"x": a["x"], "y": a["y"]})
                    a["last_hit_time"] = now
                    # если игрок A умер — начисляем убийце +30 очков
                    if a["hp"] <= 0:
                        old_score = b["score"]
                        b["score"] += 30
                        if (old_score // 50) < (b["score"] // 50):
                            give_buff_options(sid_b)
                        socketio.emit("kill_bonus", {"x": b["x"], "y": b["y"], "value": 30})


def apply_pellet_effect(p, pel):
    p["score"] += 1
    # каждые 50 очков открываем выбор баффа
    if p["score"] % 50 == 0:
        for sid, pl in players.items():
            if pl is p:
                give_buff_options(sid)
                break

def give_buff_options(sid):
    """Отправляет игроку 3 случайных баффа для выбора"""
    import random
    buffs = random.sample(BUFF_POOL, 3)
    players[sid]["buff_choices"] = buffs
    socketio.emit("buff_choices", buffs, room=sid)

@socketio.on("choose_buff")
def choose_buff(data):
    sid = request.sid
    if sid not in players:
        return
    idx = int(data.get("index", -1))
    buffs = players[sid].get("buff_choices")
    if not buffs or not (0 <= idx < len(buffs)):
        return
    buff = buffs[idx]
    p = players[sid]
    k, v, t = buff["key"], buff["value"], buff["type"]
    # применяем бафф
    if t == "add":
        p[k] = p.get(k, 0) + v
    elif t == "mult":
        # для полей с множителями (speed_mult, boost_mult, spike_size, spike_length)
        p[k] = p.get(k, 1.0) * v
    p.pop("buff_choices", None)

BUFF_POOL = [
    {"name": "+10 max HP", "key": "max_hp", "type": "add", "value": 10},
    {"name": "+2 HP regen/sec", "key": "regen", "type": "add", "value": 2},
    {"name": "+10 damage", "key": "damage", "type": "add", "value": 10},
    {"name": "+15% spike size", "key": "spike_size", "type": "mult", "value": 1.15},
    {"name": "+25% spike length", "key": "spike_length", "type": "mult", "value": 1.25},
    {"name": "+10% move speed", "key": "speed_mult", "type": "mult", "value": 1.10},
    {"name": "+20% boost speed", "key": "boost_mult", "type": "add", "value": 0.20},
]

def game_loop():
    last=time.time()
    while True:
        now=time.time(); dt=now-last; last=now
        dead=[]
        for sid,p in list(players.items()):
            dx,dy=p["tx"]-p["x"],p["ty"]-p["y"]
            target_angle=atan2(dy,dx)
            diff=(target_angle-p["angle"]+3.14159)%(2*3.14159)-3.14159
            p["angle"]+=max(-ROT_SPEED*dt,min(ROT_SPEED*dt,diff))
            dist=sqrt(dx*dx+dy*dy)
            base_speed = PLAYER_SPEED * p.get("speed_mult", 1.0)
            if p["boost"]:
                base_speed = max(PLAYER_SPEED * p.get("speed_mult", 1.0),
                                 220 * BOOST_MULT * p.get("boost_mult", 1.0))

            if dist>1:
                p["x"]+=cos(p["angle"])*base_speed*dt
                p["y"]+=sin(p["angle"])*base_speed*dt
            p["x"]+=p.get("vx",0)*dt; p["y"]+=p.get("vy",0)*dt
            p["vx"]=p.get("vx",0)*0.88; p["vy"]=p.get("vy",0)*0.88
            # --- урон от ускорения ---
            if p["boost"]:
                p["hp"] = max(0, p["hp"] - p["max_hp"] * 0.15 * dt)
                p["last_hit_time"] = now  # останавливаем реген пока бустит

            # --- реген ---
            if p["hp"] > 0 and p["hp"] < p["max_hp"]:
                last_hit = p.get("last_hit_time", 0)
                if now - last_hit > 5.0 and not p["boost"]:
                    p["hp"] = min(p["max_hp"], p["hp"] + p.get("regen", 0) * dt)

            cx, cy = WORLD_CENTER
            dx, dy = p["x"] - cx, p["y"] - cy
            dist = sqrt(dx * dx + dy * dy)
            if dist > WORLD_RADIUS - PLAYER_RADIUS:
                nx, ny = dx / dist, dy / dist
                p["x"] = cx + nx * (WORLD_RADIUS - PLAYER_RADIUS)
                p["y"] = cy + ny * (WORLD_RADIUS - PLAYER_RADIUS)
            if p["hp"]<=0: dead.append(sid)
        handle_pvp()

        eaten=set()
        for sid,p in players.items():
            for i,pel in enumerate(pellets):
                if i in eaten: continue
                if distance(p["x"],p["y"],pel["x"],pel["y"])<=PLAYER_RADIUS+PELLET_RADIUS:
                    apply_pellet_effect(p,pel); eaten.add(i)
        if eaten:
            for idx in sorted(eaten,reverse=True):
                pellets[idx]=respawn_pellet()

        for sid in dead:
            p = players.get(sid)
            if not p:
                continue
            try:
                socketio.emit("dead", {"score": int(p.get("score", 0))}, to=sid)
                time.sleep(0.1)
            except Exception as e:
                print("Ошибка отправки dead:", e)
            finally:
                players.pop(sid, None)

        socketio.emit("state", {"players": players, "pellets": pellets})

        for sid, p in list(players.items()):
            if p["hp"] <= 0:
                socketio.emit("dead", {"score": int(p.get("score", 0))}, to=sid)
                players.pop(sid, None)

        socketio.sleep(1.0/TICK_RATE)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.start_background_task(game_loop)
    socketio.run(app, host="0.0.0.0", port=port)

