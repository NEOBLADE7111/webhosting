import sqlite3
import os
from datetime import datetime
import secrets
import string

# Railway Persistence
RAILWAY_MOUNT_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app/data")
if os.path.exists(RAILWAY_MOUNT_PATH):
    DB_PATH = os.path.join(RAILWAY_MOUNT_PATH, "bot_data.db")
else:
    DB_PATH = "god_host/bot_data.db"

def init_db():
    if os.path.exists(RAILWAY_MOUNT_PATH):
        os.makedirs(RAILWAY_MOUNT_PATH, exist_ok=True)
    else:
        os.makedirs("god_host", exist_ok=True)
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        referrals INTEGER DEFAULT 0,
        referrer_id INTEGER,
        slots INTEGER DEFAULT 2,
        is_admin BOOLEAN DEFAULT FALSE,
        web_id TEXT UNIQUE,
        password TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Migration: Add missing columns safely
    c.execute("PRAGMA table_info(users)")
    cols = [col[1] for col in c.fetchall()]
    
    if 'web_id' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN web_id TEXT UNIQUE")
    if 'password' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN password TEXT")
    if 'referrer_id' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
    if 'plan' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'FREE'")
    if 'plan_expiry' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN plan_expiry TEXT")
    if 'is_banned' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0")
    if 'balance' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
    if 'is_2fa_enabled' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN is_2fa_enabled INTEGER DEFAULT 0")
    if 'profile_pic' not in cols:
        c.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
        
    # Create global config table
    c.execute('''CREATE TABLE IF NOT EXISTS global_config
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO global_config (key, value) VALUES ('maintenance', '0')")

    # Wallets & Transactions
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        tx_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        type TEXT, -- 'deposit', 'purchase', 'referral'
        description TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Gift Codes
    c.execute('''CREATE TABLE IF NOT EXISTS gift_codes (
        code TEXT PRIMARY KEY,
        plan TEXT,
        slots INTEGER,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Web Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Project Performance (for Chart.js)
    c.execute('''CREATE TABLE IF NOT EXISTS project_performance (
        perf_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        cpu REAL,
        ram REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Marketplace Templates
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
        template_id TEXT PRIMARY KEY,
        name TEXT,
        repo_url TEXT,
        description TEXT,
        category TEXT
    )''')
    
    # Pre-populate some templates if empty
    c.execute("SELECT COUNT(*) FROM templates")
    if c.fetchone()[0] == 0:
        base_templates = [
            ('music_bot', '🎵 Music Bot', 'https://github.com/example/music-bot', 'A powerful Telegram music bot template.', 'Entertainment'),
            ('mod_bot', '🛡️ Mod Bot', 'https://github.com/example/mod-bot', 'Automated group moderation and protection.', 'Utility'),
            ('ai_bot', '🤖 AI ChatBot', 'https://github.com/example/ai-bot', 'ChatGPT-powered Telegram assistant.', 'AI')
        ]
        c.executemany("INSERT INTO templates (template_id, name, repo_url, description, category) VALUES (?, ?, ?, ?, ?)", base_templates)

    conn.commit()

    # Populate missing data for existing users
    c.execute("SELECT user_id FROM users WHERE web_id IS NULL OR password IS NULL")
    users_to_fix = c.fetchall()
    for u_id_row in users_to_fix:
        u_id = u_id_row[0]
        new_web_id = f"user_{secrets.token_hex(4)}"
        new_pass = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        c.execute("UPDATE users SET web_id = ?, password = ? WHERE user_id = ?", (new_web_id, new_pass, u_id))
    
    # Projects Table
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        project_id TEXT PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        type TEXT, -- 'py' or 'js'
        path TEXT,
        entry_point TEXT,
        status TEXT DEFAULT 'stopped',
        webhook_enabled INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )''')
    
    # Migration: Add webhook_enabled and is_approved to projects
    c.execute("PRAGMA table_info(projects)")
    p_cols = [col[1] for col in c.fetchall()]
    if 'webhook_enabled' not in p_cols:
        c.execute("ALTER TABLE projects ADD COLUMN webhook_enabled INTEGER DEFAULT 0")
    if 'is_approved' not in p_cols:
        c.execute("ALTER TABLE projects ADD COLUMN is_approved INTEGER DEFAULT 0")

    # Referrals Table (to prevent double counting)
    c.execute('''CREATE TABLE IF NOT EXISTS referral_logs (
        referred_id INTEGER PRIMARY KEY,
        referrer_id INTEGER,
        FOREIGN KEY (referrer_id) REFERENCES users (user_id)
    )''')
    
    # Project Events Table
    c.execute('''CREATE TABLE IF NOT EXISTS project_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        event_type TEXT,
        message TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Project Environment Variables
    c.execute('''CREATE TABLE IF NOT EXISTS project_env (
        project_id TEXT,
        key TEXT,
        value TEXT,
        PRIMARY KEY (project_id, key),
        FOREIGN KEY (project_id) REFERENCES projects (project_id)
    )''')

    # Project Snapshots Table (Backups/Rollbacks)
    c.execute('''CREATE TABLE IF NOT EXISTS project_snapshots (
        snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        snapshot_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Channels Table (Force Join / Promotion)
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        name TEXT,
        url TEXT,
        is_force INTEGER DEFAULT 1
    )''')

    # Initial Channels provided by User with valid IDs
    initial_channels = [
        ("@AbdulBotzOfficial", "Abdul Bots Official", "https://t.me/AbdulBotzOfficial", 1),
        ("@AbdulBotMakingTips", "Bot Making Tips", "https://t.me/AbdulBotMakingTips", 1),
        ("@LootifyXOfficial", "Lootify X Official", "https://t.me/LootifyXOfficial", 1),
        ("-1003586753317", "|×𝐃𝐀𝐑𝐊 𝐍𝐀𝐆𝐈×|", "https://t.me/+5MZILV8MCutjMTc1", 1),
        ("-1003246843633", "Nagi x Abdul Backup Official", "https://t.me/NAGIxAbdulBotZOfficial", 1)
    ]
    for cid, name, url, force in initial_channels:
        c.execute("INSERT OR REPLACE INTO channels (channel_id, name, url, is_force) VALUES (?, ?, ?, ?)", (cid, name, url, force))

    # Global Blacklist Table (For NAGI Shield)
    c.execute('''CREATE TABLE IF NOT EXISTS global_blacklist
                 (pattern TEXT PRIMARY KEY)''')
    
    # Pre-populate Blacklist with God-Level Security Patterns
    core_blocks = [
        'os.walk', 'os.listdir', 'glob.glob', 'pathlib',  # Anti-Scanning
        'vpsbybrother.pem', '.env', 'bot_data.db',        # Anti-Theft
        '/etc/passwd', '/root/', '/home/', '../',         # Anti-Traversal
        'shutil.rmtree', 'os.remove', 'os.system',        # Anti-Destruction
        'subprocess', 'pexpect', 'socket',                # Anti-System Control
        'pyngrok', 'ngrok', 'threading', 'multiprocessing' # Anti-Resource Abuse
    ]
    for p in core_blocks:
        c.execute("INSERT OR IGNORE INTO global_blacklist (pattern) VALUES (?)", (p,))

    conn.commit()
    conn.close()

def add_event(project_id, event_type, message):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO project_events (project_id, event_type, message) VALUES (?, ?, ?)",
              (project_id, event_type, message))
    conn.commit()
    conn.close()

def get_events(project_id, limit=5):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM project_events WHERE project_id = ? ORDER BY timestamp DESC LIMIT ?", (project_id, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def set_project_env(project_id, key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO project_env (project_id, key, value) VALUES (?, ?, ?)", (project_id, key, value))
    conn.commit()
    conn.close()

def delete_project_env(project_id, key):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM project_env WHERE project_id = ? AND key = ?", (project_id, key))
    conn.commit()
    conn.close()

def get_project_envs(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT key, value FROM project_env WHERE project_id = ?", (project_id,))
    res = {r['key']: r['value'] for r in c.fetchall()}
    conn.close()
    return res

# --- New Future Core Features ---

def add_perf_log(project_id, cpu, ram):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO project_performance (project_id, cpu, ram) VALUES (?, ?, ?)", (project_id, cpu, ram))
    # Keep only last 100 logs per project
    c.execute("DELETE FROM project_performance WHERE perf_id IN (SELECT perf_id FROM project_performance WHERE project_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET 100)", (project_id,))
    conn.commit()
    conn.close()

def get_perf_history(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT cpu, ram, timestamp FROM project_performance WHERE project_id = ? ORDER BY timestamp ASC", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_templates():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM templates")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def redeem_gift_code(user_id, code):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM gift_codes WHERE code = ? AND is_used = 0", (code,))
    gc = c.fetchone()
    if not gc:
        conn.close()
        return False, "Invalid or already used code."
    
    # Apply rewards
    if gc['plan']:
        c.execute("UPDATE users SET plan = ? WHERE user_id = ?", (gc['plan'], user_id))
    if gc['slots']:
        c.execute("UPDATE users SET slots = slots + ? WHERE user_id = ?", (gc['slots'], user_id))
    
    c.execute("UPDATE gift_codes SET is_used = 1, used_by = ? WHERE code = ?", (user_id, code))
    conn.commit()
    conn.close()
    return True, "Code successfully redeemed!"

def update_balance(user_id, amount, tx_type, desc):
    conn = get_db()
    c = conn.cursor()
    tx_id = f"tx_{secrets.token_hex(6)}"
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    c.execute("INSERT INTO transactions (tx_id, user_id, amount, type, description) VALUES (?, ?, ?, ?, ?)",
              (tx_id, user_id, amount, tx_type, desc))
    conn.commit()
    conn.close()
    return tx_id

def toggle_project_webhook(project_id, enabled: bool):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE projects SET webhook_enabled = ? WHERE project_id = ?", (1 if enabled else 0, project_id))
    conn.commit()
    conn.close()

def get_leaderboard(limit=10):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id, username, referrals FROM users ORDER BY referrals DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# User Operations
def add_user(user_id, username, referrer_id=None):
    conn = get_db()
    c = conn.cursor()
    # Check if user exists
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    if not c.fetchone():
        web_id = f"user_{secrets.token_hex(4)}"
        password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        c.execute("INSERT INTO users (user_id, username, referrer_id, web_id, password) VALUES (?, ?, ?, ?, ?)", 
                  (user_id, username, referrer_id, web_id, password))
        
    referred_by = None
    if referrer_id:
        # Prevent self-referral or duplicate logs handled by referral_logs table
        c.execute("SELECT 1 FROM referral_logs WHERE referred_id = ?", (user_id,))
        if not c.fetchone():
            c.execute("INSERT INTO referral_logs (referred_id, referrer_id) VALUES (?, ?)", (user_id, referrer_id))
            
            # --- REWARD LOGIC ---
            # 1. Increment Referral Count
            c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
            
            # 2. Add Balance Reward (e.g. 5.0 credits)
            reward_amount = 5.0
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward_amount, referrer_id))
            
            # 3. Handle slot logic: 3 referrals = 1 slot
            c.execute("SELECT referrals FROM users WHERE user_id = ?", (referrer_id,))
            row = c.fetchone()
            if row:
                refs = row['referrals']
                if refs > 0 and refs % 3 == 0:
                    c.execute("UPDATE users SET slots = slots + 1 WHERE user_id = ?", (referrer_id,))
            
            referred_by = referrer_id

    conn.commit()
    conn.close()
    return referred_by

def get_user_by_web_id(web_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE web_id = ?", (web_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {key: row[key] for key in row.keys()}
    return None

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {key: row[key] for key in row.keys()}
    return None

def get_user_projects(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects WHERE user_id = ?", (user_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

# Project Operations
def add_project(project_id, user_id, name, p_type, path, entry_point):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO projects (project_id, user_id, name, type, path, entry_point) VALUES (?, ?, ?, ?, ?, ?)",
              (project_id, user_id, name, p_type, path, entry_point))
    conn.commit()
    conn.close()

def delete_project(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()

def update_project_status(project_id, status):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE projects SET status = ? WHERE project_id = ?", (status, project_id))
    conn.commit()
    conn.close()

def approve_project(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE projects SET is_approved = 1 WHERE project_id = ?", (project_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
def get_total_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_total_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM projects")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def update_user_status(user_id, plan=None, expiry=None, slots_add=0, ban=None):
    conn = get_db()
    c = conn.cursor()
    if plan: c.execute("UPDATE users SET plan = ? WHERE user_id = ?", (plan, user_id))
    if expiry: c.execute("UPDATE users SET plan_expiry = ? WHERE user_id = ?", (expiry, user_id))
    if ban is not None: c.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if ban else 0, user_id))
    if slots_add != 0: c.execute("UPDATE users SET slots = slots + ? WHERE user_id = ?", (slots_add, user_id))
    conn.commit()
    conn.close()

def update_user_avatar(user_id, url):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET profile_pic = ? WHERE user_id = ?", (url, user_id))
    conn.commit()
    conn.close()

def generate_gift_codes(plan, slots, count=5):
    conn = get_db()
    c = conn.cursor()
    codes = []
    for _ in range(count):
        code = f"Neo-{plan}-{secrets.token_hex(3).upper()}"
        c.execute("INSERT INTO gift_codes (code, plan, slots) VALUES (?, ?, ?)", (code, plan, slots))
        codes.append(code)
    conn.commit()
    conn.close()
    return codes

def get_global_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE plan = 'VIP'")
    vip_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM projects")
    total_projects = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM projects WHERE status = 'running'")
    running_projects = c.fetchone()[0]
    c.execute("SELECT SUM(balance) FROM users")
    total_revenue = c.fetchone()[0] or 0.0
    conn.close()
    return {
        "users": total_users,
        "vip": vip_users,
        "projects": total_projects,
        "running": running_projects,
        "revenue": total_revenue
    }

def add_snapshot(project_id, path):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO project_snapshots (project_id, snapshot_path) VALUES (?, ?)", (project_id, path))
    conn.commit()
    conn.close()

def get_snapshots(project_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM project_snapshots WHERE project_id = ? ORDER BY created_at DESC LIMIT 5", (project_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def get_blacklist():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT pattern FROM global_blacklist")
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows

def add_blacklist_pattern(pattern):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO global_blacklist (pattern) VALUES (?)", (pattern,))
    conn.commit()
    conn.close()

def remove_blacklist_pattern(pattern):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM global_blacklist WHERE pattern = ?", (pattern,))
    conn.commit()
    conn.close()

def get_all_projects():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM projects")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def add_channel(channel_id, name, url, is_force=1):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO channels (channel_id, name, url, is_force) VALUES (?, ?, ?, ?)", (str(channel_id), name, url, is_force))
    conn.commit()
    conn.close()

def get_channels():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM channels")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def delete_channel(channel_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM channels WHERE channel_id = ?", (str(channel_id),))
    conn.commit()
    conn.close()

def get_force_channels():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM channels WHERE is_force = 1")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def set_maintenance(status: bool):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE global_config SET value = ? WHERE key = 'maintenance'", ('1' if status else '0',))
    conn.commit()
    conn.close()

def is_maintenance():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM global_config WHERE key = 'maintenance'")
    res = c.fetchone()
    conn.close()
    return res and res[0] == '1'

def create_session(user_id):
    import uuid
    token = str(uuid.uuid4())
    conn = get_db()
    c = conn.cursor()
    # Keep old sessions — deleting them would invalidate tokens already embedded in open pages
    c.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    conn.commit()
    conn.close()
    return token

def get_session_user(token):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    return row['user_id'] if row else None
