# ============================================================
# PhysioTrack — App web genérico
# Flask + SocketIO + SQLite + PWA
# ============================================================

from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import json, os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'physiotrack-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///physiotrack.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# ─── EJERCICIOS Y NIVELES ───────────────────────────────────

EJERCICIOS_ANALISIS = {
    "estatico":       {"nombre": "Análisis estático",       "descripcion": "De pie, sin movimiento. Evalúa la distribución basal del peso.", "duracion_s": 30},
    "sentadilla":     {"nombre": "Análisis en sentadilla",  "descripcion": "Realiza una sentadilla lenta y mantén la posición.", "duracion_s": 30},
    "monopodal_izq":  {"nombre": "Monopodal izquierdo",     "descripcion": "Apóyate solo en el pie izquierdo.", "duracion_s": 20},
    "monopodal_der":  {"nombre": "Monopodal derecho",       "descripcion": "Apóyate solo en el pie derecho.", "duracion_s": 20},
    "puntillas":      {"nombre": "Análisis en puntillas",   "descripcion": "Eleva los talones y mantén la posición en puntillas.", "duracion_s": 20},
}

EJERCICIOS_REHAB = {
    "sentadillas":        {"nombre": "Sentadillas",          "descripcion": "Flexión de rodillas distribuyendo el peso en ambos pies."},
    "equilibrio_mono":    {"nombre": "Equilibrio monopodal", "descripcion": "Mantén el equilibrio sobre un pie alternando entre ambos."},
    "saltos":             {"nombre": "Saltos en el sitio",   "descripcion": "Saltos suaves aterrizando con ambos pies a la vez."},
    "transferencia_peso": {"nombre": "Transferencia de peso","descripcion": "Desplaza el peso de un pie al otro de forma controlada."},
    "puntillas_rehab":    {"nombre": "Puntillas",            "descripcion": "Elevación de talones apoyándose en la punta de los pies."},
    "marcha_estatica":    {"nombre": "Marcha estática",      "descripcion": "Levanta los pies alternos simulando marcha sin desplazarte."},
}

NIVELES_REHAB = {
    1: {"reps": 5,  "intervalo_ms": 8000},
    2: {"reps": 8,  "intervalo_ms": 7000},
    3: {"reps": 10, "intervalo_ms": 6000},
    4: {"reps": 12, "intervalo_ms": 5000},
    5: {"reps": 15, "intervalo_ms": 4000},
}

NIVELES_ANALISIS = {
    1: {"duracion_s": 15},
    2: {"duracion_s": 20},
    3: {"duracion_s": 25},
    4: {"duracion_s": 30},
    5: {"duracion_s": 40},
}

# ─── MODELOS ────────────────────────────────────────────────

class Usuario(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    nombre        = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    sesiones      = db.relationship('Sesion', backref='usuario', lazy=True)
    progreso      = db.relationship('Progreso', backref='usuario', lazy=True)
    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):  self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

    def get_progreso(self, modo, ejercicio_id):
        p = Progreso.query.filter_by(usuario_id=self.id, modo=modo, ejercicio_id=ejercicio_id).first()
        return p.nivel_actual if p else 1

class Progreso(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    modo         = db.Column(db.String(20), nullable=False)
    ejercicio_id = db.Column(db.String(50), nullable=False)
    nivel_actual = db.Column(db.Integer, default=1)

class Sesion(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    usuario_id    = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    modo          = db.Column(db.String(20), default='analisis')
    ejercicio_id  = db.Column(db.String(50), default='estatico')
    nivel         = db.Column(db.Integer, default=1)
    fecha         = db.Column(db.DateTime, default=datetime.utcnow)
    duracion_s    = db.Column(db.Float, default=0)
    reps_total    = db.Column(db.Integer, default=0)
    hr_medio      = db.Column(db.Float, default=0)
    emg_medio     = db.Column(db.Float, default=0)
    equilibrio_pct = db.Column(db.Float, default=0)
    datos_json    = db.Column(db.Text, default='{}')

    def nombre_ejercicio(self):
        if self.modo == 'analisis':
            return EJERCICIOS_ANALISIS.get(self.ejercicio_id, {}).get('nombre', self.ejercicio_id)
        return EJERCICIOS_REHAB.get(self.ejercicio_id, {}).get('nombre', self.ejercicio_id)

    def fecha_local(self):
        return self.fecha + timedelta(hours=2)

class UsuarioActivo(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class EjercicioActivo(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    usuario_id   = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    modo         = db.Column(db.String(20), default='analisis')
    ejercicio_id = db.Column(db.String(50), default='estatico')
    nivel        = db.Column(db.Integer, default=1)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow)

# ─── AUTH ───────────────────────────────────────────────────

@app.route('/')
def index():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u = Usuario.query.filter_by(email=request.form.get('email')).first()
        if u and u.check_password(request.form.get('password')):
            session['usuario_id'] = u.id
            session['nombre']     = u.nombre
            activo = UsuarioActivo.query.first()
            if not activo:
                activo = UsuarioActivo(usuario_id=u.id)
                db.session.add(activo)
            else:
                activo.usuario_id = u.id
                activo.updated_at = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard'))
        error = 'Email o contraseña incorrectos'
    return render_template('login.html', error=error)

@app.route('/registro', methods=['GET','POST'])
def registro():
    error = None
    if request.method == 'POST':
        if Usuario.query.filter_by(email=request.form.get('email')).first():
            error = 'Ya existe una cuenta con ese email'
        else:
            u = Usuario(nombre=request.form.get('nombre'), email=request.form.get('email'))
            u.set_password(request.form.get('password'))
            db.session.add(u)
            db.session.commit()
            session['usuario_id'] = u.id
            session['nombre']     = u.nombre
            return redirect(url_for('dashboard'))
    return render_template('registro.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ─── PÁGINAS ────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u = Usuario.query.get(session['usuario_id'])
    if not u: session.clear(); return redirect(url_for('login'))
    ultima = Sesion.query.filter_by(usuario_id=u.id).order_by(Sesion.fecha.desc()).first()
    return render_template('dashboard.html', usuario=u, ultima=ultima)

@app.route('/modo/<modo>')
def lista_ejercicios(modo):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    if modo not in ('analisis', 'rehabilitacion'): return redirect(url_for('dashboard'))
    u = Usuario.query.get(session['usuario_id'])
    if not u: session.clear(); return redirect(url_for('login'))
    ejercicios_dict = EJERCICIOS_ANALISIS if modo == 'analisis' else EJERCICIOS_REHAB
    lista = []
    for ej_id, ej_info in ejercicios_dict.items():
        nivel = u.get_progreso(modo, ej_id)
        lista.append({"id": ej_id, "nivel_actual": nivel, **ej_info})
    return render_template('lista_ejercicios.html', modo=modo, ejercicios=lista, usuario=u)

@app.route('/sesion/<modo>/<ejercicio_id>/<int:nivel>')
def sesion_ejercicio(modo, ejercicio_id, nivel):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    ejercicios = EJERCICIOS_ANALISIS if modo == 'analisis' else EJERCICIOS_REHAB
    niveles    = NIVELES_ANALISIS    if modo == 'analisis' else NIVELES_REHAB
    if ejercicio_id not in ejercicios or nivel not in niveles:
        return redirect(url_for('lista_ejercicios', modo=modo))

    ej_info      = ejercicios[ejercicio_id]
    nivel_config = niveles[nivel]

    # Guardar ejercicio activo para que la RPi lo consulte
    activo = EjercicioActivo.query.filter_by(usuario_id=session['usuario_id']).first()
    if not activo:
        activo = EjercicioActivo(usuario_id=session['usuario_id'])
        db.session.add(activo)
    activo.modo         = modo
    activo.ejercicio_id = ejercicio_id
    activo.nivel        = nivel
    activo.updated_at   = datetime.utcnow()
    db.session.commit()

    return render_template('sesion.html',
        modo=modo,
        ejercicio_id=ejercicio_id,
        ejercicio_nombre=ej_info['nombre'],
        ejercicio_desc=ej_info['descripcion'],
        nivel=nivel,
        nivel_config=nivel_config,
    )

@app.route('/historial')
def historial():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u = Usuario.query.get(session['usuario_id'])
    if not u: session.clear(); return redirect(url_for('login'))
    sesiones = Sesion.query.filter_by(usuario_id=u.id).order_by(Sesion.fecha.desc()).all()
    return render_template('historial.html', sesiones=sesiones)

@app.route('/estadisticas')
def estadisticas():
    if 'usuario_id' not in session: return redirect(url_for('login'))
    u = Usuario.query.get(session['usuario_id'])
    if not u: session.clear(); return redirect(url_for('login'))

    # Calcular medias por ejercicio
    stats = {}
    sesiones = Sesion.query.filter_by(usuario_id=u.id).all()
    for s in sesiones:
        key = f"{s.modo}_{s.ejercicio_id}"
        if key not in stats:
            stats[key] = {"nombre": s.nombre_ejercicio(), "modo": s.modo,
                          "hr": [], "emg": [], "equilibrio": [], "count": 0}
        stats[key]["hr"].append(s.hr_medio)
        stats[key]["emg"].append(s.emg_medio)
        stats[key]["equilibrio"].append(s.equilibrio_pct)
        stats[key]["count"] += 1

    for k in stats:
        d = stats[k]
        d["hr_medio"]         = round(sum(d["hr"])         / len(d["hr"]),         1) if d["hr"]         else 0
        d["emg_medio"]        = round(sum(d["emg"])        / len(d["emg"]),        3) if d["emg"]        else 0
        d["equilibrio_medio"] = round(sum(d["equilibrio"]) / len(d["equilibrio"]), 1) if d["equilibrio"] else 0

    return render_template('estadisticas.html', stats=stats, usuario=u)

@app.route('/detalle/<int:sesion_id>')
def detalle(sesion_id):
    if 'usuario_id' not in session: return redirect(url_for('login'))
    s = Sesion.query.get_or_404(sesion_id)
    if s.usuario_id != session['usuario_id']: return redirect(url_for('historial'))
    return render_template('detalle.html', sesion=s)

# ─── API RASPBERRY PI ───────────────────────────────────────

@app.route('/api/usuario_activo')
def api_usuario_activo():
    activo = UsuarioActivo.query.first()
    if activo and activo.usuario_id:
        u = Usuario.query.get(activo.usuario_id)
        if u:
            return jsonify({'usuario_id': activo.usuario_id, 'nombre': u.nombre})
    return jsonify({'usuario_id': None})

@app.route('/api/ejercicio_activo')
def api_ejercicio_activo():
    activo = EjercicioActivo.query.order_by(EjercicioActivo.updated_at.desc()).first()
    if activo:
        if activo.modo == 'analisis':
            cfg = NIVELES_ANALISIS.get(activo.nivel, NIVELES_ANALISIS[1])
            return jsonify({'modo': activo.modo, 'ejercicio_id': activo.ejercicio_id,
                            'nivel': activo.nivel, 'duracion_s': cfg['duracion_s'],
                            'reps': 0, 'intervalo_ms': 0, 'seleccionado': True})
        else:
            cfg = NIVELES_REHAB.get(activo.nivel, NIVELES_REHAB[1])
            return jsonify({'modo': activo.modo, 'ejercicio_id': activo.ejercicio_id,
                            'nivel': activo.nivel, 'duracion_s': 0,
                            'reps': cfg['reps'], 'intervalo_ms': cfg['intervalo_ms'],
                            'seleccionado': True})
    return jsonify({'modo': 'analisis', 'ejercicio_id': 'estatico',
                    'nivel': 1, 'duracion_s': 30, 'reps': 0, 'intervalo_ms': 0,
                    'seleccionado': False})

@app.route('/api/datos', methods=['POST'])
def api_datos():
    datos = request.get_json()
    if not datos: return jsonify({'error': 'Sin datos'}), 400
    if datos.get('tipo') == 'rep_completada':
        socketio.emit('rep_completada', {'rep': datos.get('rep'), 'total': datos.get('total')})
    else:
        socketio.emit('datos_sensores', datos)
    return jsonify({'ok': True})

@app.route('/api/sesion', methods=['POST'])
def api_sesion():
    datos = request.get_json()
    if not datos: return jsonify({'error': 'Sin datos'}), 400

    usuario_id   = datos.get('usuario_id')
    if not usuario_id: return jsonify({'error': 'Sin usuario_id'}), 400

    modo         = datos.get('modo',         'analisis')
    ejercicio_id = datos.get('ejercicio_id', 'estatico')
    nivel        = datos.get('nivel',        1)
    muestras     = datos.get('muestras',     [])
    reps         = datos.get('repeticiones', [])

    nueva = Sesion(
        usuario_id     = usuario_id,
        modo           = modo,
        ejercicio_id   = ejercicio_id,
        nivel          = nivel,
        duracion_s     = datos.get('duracion_s',    0),
        reps_total     = datos.get('reps_total',    len(reps)),
        hr_medio       = datos.get('hr_medio',      0),
        emg_medio      = datos.get('emg_medio',     0),
        equilibrio_pct = datos.get('equilibrio_pct',0),
        datos_json     = json.dumps(datos),
    )
    db.session.add(nueva)

    # Actualizar progreso
    niveles = NIVELES_ANALISIS if modo == 'analisis' else NIVELES_REHAB
    reps_necesarias = niveles.get(nivel, {}).get('reps', 0) if modo == 'rehabilitacion' else 1
    completada = (modo == 'analisis') or (len(reps) >= reps_necesarias)

    if completada:
        p = Progreso.query.filter_by(usuario_id=usuario_id, modo=modo, ejercicio_id=ejercicio_id).first()
        if not p:
            p = Progreso(usuario_id=usuario_id, modo=modo, ejercicio_id=ejercicio_id, nivel_actual=1)
            db.session.add(p)
        if p.nivel_actual == nivel and nivel < 5:
            p.nivel_actual = nivel + 1

    db.session.commit()

    socketio.emit('sesion_completada', {
        'sesion_id':    nueva.id,
        'modo':         modo,
        'ejercicio_id': ejercicio_id,
        'nivel':        nivel,
        'siguiente_nivel': min(nivel + 1, 5) if completada else nivel,
        'completada':   completada,
        'hr_medio':     datos.get('hr_medio', 0),
        'emg_medio':    datos.get('emg_medio', 0),
        'equilibrio':   datos.get('equilibrio_pct', 0),
        'duracion':     datos.get('duracion_s', 0),
        'reps':         len(reps),
    })

    return jsonify({'ok': True, 'sesion_id': nueva.id})

# ─── PWA ────────────────────────────────────────────────────

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "PhysioTrack",
        "short_name": "PhysioTrack",
        "description": "Plataforma de análisis biomecánico plantar",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#3b82f6",
        "orientation": "portrait",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ]
    })

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('js/sw.js'), 200, {'Content-Type': 'application/javascript'}

# ─── WEBSOCKET ──────────────────────────────────────────────

@socketio.on('connect')
def on_connect(): print('[WS] Cliente conectado')

@socketio.on('disconnect')
def on_disconnect(): print('[WS] Cliente desconectado')

# ─── ARRANQUE ───────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
