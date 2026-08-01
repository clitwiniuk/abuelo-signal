import sqlite3
import os
from datetime import datetime, timedelta
import json

DB_PATH = os.path.join(os.path.dirname(__file__), 'elite_academy.db')

def get_connection():
    """Obtener conexión a la base de datos"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Inicializar todas las tablas de la base de datos"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nivel_actual INTEGER DEFAULT 1,
            xp_total INTEGER DEFAULT 0,
            capital_virtual REAL DEFAULT 25000.0,
            capital_inicial_nivel REAL DEFAULT 25000.0,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ultimo_login TIMESTAMP,
            racha_dias INTEGER DEFAULT 0,
            ultimo_checkin DATE,
            trading_bloqueado_hasta TIMESTAMP,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de trades
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            simbolo TEXT NOT NULL,
            setup TEXT NOT NULL,
            tipo_operacion TEXT DEFAULT 'LONG',
            entrada REAL NOT NULL,
            salida REAL,
            size INTEGER NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            pnl REAL,
            pnl_porcentaje REAL,
            r_multiple REAL,
            cumplio_plan BOOLEAN DEFAULT 0,
            emocion_entrada TEXT,
            emocion_salida TEXT,
            notas TEXT,
            fecha_entrada TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_salida TIMESTAMP,
            slippage REAL DEFAULT 0,
            comision REAL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de daily reports (journal psicológico)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            fecha DATE UNIQUE NOT NULL,
            pre_market_score INTEGER CHECK(pre_market_score BETWEEN 1 AND 10),
            estado_emocional TEXT,
            cumplio_sueno BOOLEAN DEFAULT 0,
            trades_planeados INTEGER DEFAULT 0,
            trades_reales INTEGER DEFAULT 0,
            riesgo_maximo_hoy REAL,
            aprendizaje TEXT,
            siguio_plan TEXT,
            fomo_revenge TEXT,
            mejor_trade TEXT,
            peor_trade TEXT,
            completado BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de dominio de setups
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS setups_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            setup_type TEXT NOT NULL,
            trades_practicados INTEGER DEFAULT 0,
            trades_ganados INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0,
            dominado BOOLEAN DEFAULT 0,
            fecha_dominio TIMESTAMP,
            UNIQUE(user_id, setup_type),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de logros/badges
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            descripcion TEXT,
            fecha_desbloqueo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, badge_name),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de historial de niveles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nivel_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nivel_anterior INTEGER,
            nivel_nuevo INTEGER NOT NULL,
            xp_en_subida INTEGER,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de watchlists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            simbolo TEXT NOT NULL,
            setup_detectado TEXT,
            notas TEXT,
            fecha_agregado TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activo BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de sesiones de entrenamiento
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo_entrenamiento TEXT NOT NULL,
            setup_focus TEXT,
            fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_fin TIMESTAMP,
            ejercicios_completados INTEGER DEFAULT 0,
            puntuacion REAL,
            notas TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de configuración de usuario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            hotkey_compra TEXT DEFAULT 'F1',
            hotkey_venta TEXT DEFAULT 'F2',
            hotkey_cancelar TEXT DEFAULT 'ESC',
            tema TEXT DEFAULT 'dark',
            slippage_default REAL DEFAULT 0.002,
            comision_por_accion REAL DEFAULT 0.005,
            notificaciones BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Tabla de sesiones de replay
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS replay_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scenario_id TEXT NOT NULL,
            scenario_name TEXT,
            fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            fecha_fin TIMESTAMP,
            total_trades INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0,
            win_rate REAL DEFAULT 0,
            grade TEXT,
            xp_earned INTEGER DEFAULT 0,
            completada BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Insertar setups iniciales si no existen
    setups_default = [
        ('Morning Panic Dip', 'Kyle Williams', 'Caída >20% en primeros 15 min, volumen >2x, soporte psicológico'),
        ('VWAP Bounce', 'Alex Temiz', 'Precio cruza VWAP hacia abajo y rebota con volumen'),
        ('First Red Day', 'Short Selling', 'Después de 3+ días verdes, primer día rojo'),
        ('Opening Range Breakout', 'Lance Breitstein', 'Break de rango primeros 5-30 minutos')
    ]
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS setups_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            trader TEXT,
            descripcion TEXT,
            nivel_requerido INTEGER DEFAULT 1,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    for setup in setups_default:
        cursor.execute('''
            INSERT OR IGNORE INTO setups_info (nombre, trader, descripcion, nivel_requerido)
            VALUES (?, ?, ?, ?)
        ''', (setup[0], setup[1], setup[2], 1 if setup[0] != 'First Red Day' else 3))
    
    conn.commit()
    conn.close()
    print("Base de datos inicializada correctamente")

# Funciones CRUD para Usuarios
def create_user(username, email, password_hash):
    """Crear nuevo usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, capital_virtual, capital_inicial_nivel)
            VALUES (?, ?, ?, 25000.0, 25000.0)
        ''', (username, email, password_hash))
        user_id = cursor.lastrowid
        
        # Crear configuración default
        cursor.execute('''
            INSERT INTO user_settings (user_id) VALUES (?)
        ''', (user_id,))
        
        # Inicializar mastery de setups
        setups = ['Morning Panic Dip', 'VWAP Bounce', 'First Red Day', 'Opening Range Breakout']
        for setup in setups:
            cursor.execute('''
                INSERT INTO setups_mastery (user_id, setup_type) VALUES (?, ?)
            ''', (user_id, setup))
        
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    """Obtener usuario por username"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND activo = 1', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    """Obtener usuario por ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_capital(user_id, nuevo_capital):
    """Actualizar capital virtual del usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET capital_virtual = ? WHERE id = ?', (nuevo_capital, user_id))
    conn.commit()
    conn.close()

def add_xp_to_user(user_id, xp_amount):
    """Añadir XP a usuario y verificar subida de nivel"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT xp_total, nivel_actual FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        nuevo_xp = user['xp_total'] + xp_amount
        nivel_actual = user['nivel_actual']
        nuevo_nivel = calcular_nivel_por_xp(nuevo_xp)
        
        cursor.execute('UPDATE users SET xp_total = ? WHERE id = ?', (nuevo_xp, user_id))
        
        if nuevo_nivel > nivel_actual:
            # Subió de nivel
            cursor.execute('''
                INSERT INTO nivel_history (user_id, nivel_anterior, nivel_nuevo, xp_en_subida)
                VALUES (?, ?, ?, ?)
            ''', (user_id, nivel_actual, nuevo_nivel, nuevo_xp))
            cursor.execute('UPDATE users SET nivel_actual = ? WHERE id = ?', (nuevo_nivel, user_id))
            
            # Actualizar capital según nuevo nivel
            capital_nuevo = {
                1: 25000, 2: 50000, 3: 100000, 4: 250000, 5: 1000000
            }.get(nuevo_nivel, 1000000)
            
            cursor.execute('''
                UPDATE users SET capital_virtual = ?, capital_inicial_nivel = ? WHERE id = ?
            ''', (capital_nuevo, capital_nuevo, user_id))
        
        conn.commit()
    conn.close()

def calcular_nivel_por_xp(xp):
    """Calcular nivel basado en XP total"""
    if xp < 500:
        return 1
    elif xp < 1500:
        return 2
    elif xp < 3500:
        return 3
    elif xp < 7000:
        return 4
    else:
        return 5

# Funciones para Trades
def create_trade(user_id, simbolo, setup, entrada, size, stop_loss=None, 
                 take_profit=None, tipo_operacion='LONG', emocion_entrada=None):
    """Crear nuevo trade"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO trades (user_id, simbolo, setup, entrada, size, stop_loss, 
                           take_profit, tipo_operacion, emocion_entrada)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, simbolo, setup, entrada, size, stop_loss, take_profit, 
          tipo_operacion, emocion_entrada))
    
    trade_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return trade_id

def close_trade(trade_id, salida, pnl, pnl_porcentaje, r_multiple, 
                cumplio_plan, emocion_salida=None, notas=None):
    """Cerrar trade existente"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE trades 
        SET salida = ?, pnl = ?, pnl_porcentaje = ?, r_multiple = ?,
            cumplio_plan = ?, emocion_salida = ?, notas = ?, fecha_salida = ?
        WHERE id = ?
    ''', (salida, pnl, pnl_porcentaje, r_multiple, cumplio_plan, 
          emocion_salida, notas, datetime.now(), trade_id))
    
    conn.commit()
    conn.close()

def get_trades_by_user(user_id, limit=None, fecha_desde=None, fecha_hasta=None):
    """Obtener trades de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM trades WHERE user_id = ?'
    params = [user_id]
    
    if fecha_desde:
        query += ' AND DATE(fecha_entrada) >= ?'
        params.append(fecha_desde)
    if fecha_hasta:
        query += ' AND DATE(fecha_entrada) <= ?'
        params.append(fecha_hasta)
    
    query += ' ORDER BY fecha_entrada DESC'
    
    if limit:
        query += ' LIMIT ?'
        params.append(limit)
    
    cursor.execute(query, params)
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades

def get_trades_abiertos(user_id):
    """Obtener trades abiertos"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM trades WHERE user_id = ? AND salida IS NULL
        ORDER BY fecha_entrada DESC
    ''', (user_id,))
    trades = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return trades

# Funciones para Daily Reports
def create_or_update_daily_report(user_id, fecha, **kwargs):
    """Crear o actualizar daily report"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Verificar si existe
    cursor.execute('SELECT id FROM daily_reports WHERE user_id = ? AND fecha = ?', 
                   (user_id, fecha))
    existing = cursor.fetchone()
    
    if existing:
        # Actualizar
        fields = []
        values = []
        for key, value in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(value)
        values.extend([user_id, fecha])
        
        query = f"UPDATE daily_reports SET {', '.join(fields)} WHERE user_id = ? AND fecha = ?"
        cursor.execute(query, values)
    else:
        # Crear nuevo
        fields = ['user_id', 'fecha'] + list(kwargs.keys())
        placeholders = ['?'] * len(fields)
        values = [user_id, fecha] + list(kwargs.values())
        
        query = f"INSERT INTO daily_reports ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
        cursor.execute(query, values)
    
    conn.commit()
    conn.close()

def get_daily_report(user_id, fecha):
    """Obtener daily report de una fecha específica"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM daily_reports WHERE user_id = ? AND fecha = ?
    ''', (user_id, fecha))
    report = cursor.fetchone()
    conn.close()
    return dict(report) if report else None

def get_daily_reports_stats(user_id, dias=30):
    """Obtener estadísticas de daily reports"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM daily_reports 
        WHERE user_id = ? AND fecha >= date('now', '-{} days')
        ORDER BY fecha DESC
    '''.format(dias), (user_id,))
    reports = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reports

# Funciones para Estadísticas
def get_trading_stats(user_id, dias=30):
    """Obtener estadísticas de trading"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_trades,
            SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as trades_ganados,
            SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as trades_perdidos,
            SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gross_profit,
            SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as gross_loss,
            AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_winner,
            AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loser,
            AVG(pnl) as avg_trade,
            AVG(r_multiple) as avg_r_multiple,
            SUM(pnl) as total_pnl,
            SUM(CASE WHEN cumplio_plan = 1 THEN 1 ELSE 0 END) as trades_plan_cumplido
        FROM trades 
        WHERE user_id = ? AND salida IS NOT NULL
        AND DATE(fecha_entrada) >= date('now', '-{} days')
    '''.format(dias), (user_id,))
    
    stats = cursor.fetchone()
    conn.close()
    
    if stats:
        result = dict(stats)
        # Calcular métricas derivadas
        total = result['total_trades'] or 0
        if total > 0:
            result['win_rate'] = (result['trades_ganados'] / total) * 100
            result['loss_rate'] = (result['trades_perdidos'] / total) * 100
        else:
            result['win_rate'] = 0
            result['loss_rate'] = 0
        
        # Profit Factor
        gross_loss = result['gross_loss'] or 0
        if gross_loss > 0:
            result['profit_factor'] = (result['gross_profit'] or 0) / gross_loss
        else:
            result['profit_factor'] = float('inf') if (result['gross_profit'] or 0) > 0 else 0
        
        # Expected Value
        win_rate = result['win_rate'] / 100
        loss_rate = result['loss_rate'] / 100
        avg_winner = result['avg_winner'] or 0
        avg_loser = abs(result['avg_loser'] or 0)
        result['expected_value'] = (win_rate * avg_winner) - (loss_rate * avg_loser)
        
        return result
    return {}

def get_consecutive_stats(user_id):
    """Obtener estadísticas de rachas consecutivas"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT pnl FROM trades 
        WHERE user_id = ? AND salida IS NOT NULL
        ORDER BY fecha_entrada ASC
    ''', (user_id,))
    
    trades = cursor.fetchall()
    conn.close()
    
    if not trades:
        return {'max_consecutive_wins': 0, 'max_consecutive_losses': 0}
    
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0
    
    for trade in trades:
        if trade['pnl'] > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(max_wins, current_wins)
        elif trade['pnl'] < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(max_losses, current_losses)
    
    return {
        'max_consecutive_wins': max_wins,
        'max_consecutive_losses': max_losses
    }

# Funciones para Logros
def unlock_achievement(user_id, badge_name, badge_icon, descripcion):
    """Desbloquear un logro"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO achievements (user_id, badge_name, badge_icon, descripcion)
            VALUES (?, ?, ?, ?)
        ''', (user_id, badge_name, badge_icon, descripcion))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_achievements(user_id):
    """Obtener logros de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM achievements WHERE user_id = ? ORDER BY fecha_desbloqueo DESC
    ''', (user_id,))
    achievements = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return achievements

def check_achievement_exists(user_id, badge_name):
    """Verificar si un usuario ya tiene un logro"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 1 FROM achievements WHERE user_id = ? AND badge_name = ?
    ''', (user_id, badge_name))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

# Funciones para Setups Mastery
def update_setup_mastery(user_id, setup_type, ganado=False):
    """Actualizar progreso de dominio de un setup"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM setups_mastery WHERE user_id = ? AND setup_type = ?
    ''', (user_id, setup_type))
    
    mastery = cursor.fetchone()
    
    if mastery:
        trades_total = mastery['trades_practicados'] + 1
        trades_ganados = mastery['trades_ganados'] + (1 if ganado else 0)
        win_rate = (trades_ganados / trades_total) * 100 if trades_total > 0 else 0
        
        dominado = win_rate >= 60 and trades_total >= 20
        
        cursor.execute('''
            UPDATE setups_mastery 
            SET trades_practicados = ?, trades_ganados = ?, win_rate = ?, dominado = ?,
                fecha_dominio = CASE WHEN ? = 1 AND fecha_dominio IS NULL THEN ? ELSE fecha_dominio END
            WHERE user_id = ? AND setup_type = ?
        ''', (trades_total, trades_ganados, win_rate, dominado, 
              1 if dominado else 0, datetime.now(), user_id, setup_type))
        
        conn.commit()
    
    conn.close()

def get_setups_mastery(user_id):
    """Obtener dominio de setups de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sm.*, si.trader, si.descripcion, si.nivel_requerido
        FROM setups_mastery sm
        JOIN setups_info si ON sm.setup_type = si.nombre
        WHERE sm.user_id = ?
    ''', (user_id,))
    setups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return setups

# Funciones para Watchlist
def add_to_watchlist(user_id, simbolo, setup_detectado=None, notas=None):
    """Añadir símbolo a watchlist"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO watchlists (user_id, simbolo, setup_detectado, notas)
            VALUES (?, ?, ?, ?)
        ''', (user_id, simbolo, setup_detectado, notas))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_watchlist(user_id):
    """Obtener watchlist del usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM watchlists WHERE user_id = ? AND activo = 1
        ORDER BY fecha_agregado DESC
    ''', (user_id,))
    watchlist = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return watchlist

def remove_from_watchlist(user_id, simbolo):
    """Eliminar de watchlist"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE watchlists SET activo = 0 WHERE user_id = ? AND simbolo = ?
    ''', (user_id, simbolo))
    conn.commit()
    conn.close()

# Funciones para Replay Sessions
def create_replay_session(user_id, scenario_id, scenario_name=None):
    """Crear nueva sesion de replay"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO replay_sessions (user_id, scenario_id, scenario_name)
        VALUES (?, ?, ?)
    ''', (user_id, scenario_id, scenario_name))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def close_replay_session(user_id, scenario_id, total_trades=0, total_pnl=0.0,
                         win_rate=0.0, grade="", xp_earned=0):
    """Cerrar sesion de replay con resultados"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE replay_sessions
        SET fecha_fin = ?, total_trades = ?, total_pnl = ?, win_rate = ?,
            grade = ?, xp_earned = ?, completada = 1
        WHERE user_id = ? AND scenario_id = ? AND completada = 0
        ORDER BY id DESC LIMIT 1
    ''', (datetime.now(), total_trades, total_pnl, win_rate, grade,
          xp_earned, user_id, scenario_id))
    conn.commit()
    conn.close()


def get_replay_history(user_id, limit=20):
    """Obtener historial de replays de un usuario"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM replay_sessions
        WHERE user_id = ? AND completada = 1
        ORDER BY fecha_fin DESC
        LIMIT ?
    ''', (user_id, limit))
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions


# Inicializar base de datos al importar
if __name__ == '__main__':
    init_database()