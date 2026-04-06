from fastapi import FastAPI, HTTPException, Request, Response, Form, Depends, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
import os
from pathlib import Path
import manager
import database

app = FastAPI()

# Sessions
SESSIONS = {}

def is_owner(user_id, project_id):
    projects = database.get_user_projects(user_id)
    return any(p['project_id'] == project_id for p in projects)

# Mascot & Avatars
MASCOT_URL = "https://i.pinimg.com/originals/7e/1a/7f/7e1a7f05327914856f6c9af7f34f8a0a.gif" 
PRESET_AVATARS = [
    "https://i.pinimg.com/originals/7e/1a/7f/7e1a7f05327914856f6c9af7f34f8a0a.gif",
    "https://media.tenor.com/f7A-jST_u2kAAAAC/anime-girl-hacking.gif",
    "https://i.ibb.co/L5r6f5P/skull-red.png",
    "https://i.ibb.co/YyYh4xP/robot-blue.png",
    "https://i.ibb.co/7gXvS6v/cat-neon.png",
    "https://i.ibb.co/3W2K4z8/knight-void.png",
    "https://cdn-icons-png.flaticon.com/512/4333/4333609.png",
    "https://cdn-icons-png.flaticon.com/512/4333/4333642.png",
    "https://cdn-icons-png.flaticon.com/512/9408/9408175.png"
]

CSS_SHARED = """
:root {
    --bg: #030712;
    --card-bg: rgba(17, 24, 39, 0.6);
    --accent: #8b5cf6;
    --accent-glow: rgba(139, 92, 246, 0.5);
    --text: #f3f4f6;
    --text-muted: #9ca3af;
    --border: rgba(255, 255, 255, 0.08);
    --success: #10b981;
    --danger: #ef4444;
}
.theme-cyber {
    --bg: #050505;
    --card-bg: rgba(10, 10, 15, 0.85);
    --accent: #00f2ff;
    --accent-glow: rgba(0, 242, 255, 0.4);
    --success: #39ff14;
    --danger: #ff003c;
}
.theme-anime {
    --bg: #1a1b26;
    --card-bg: rgba(36, 40, 59, 0.8);
    --accent: #ff757f;
    --accent-glow: rgba(255, 117, 127, 0.4);
    --success: #73daca;
    --danger: #f7768e;
}
body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', -apple-system, sans-serif;
    margin: 0;
    overflow-x: hidden;
    -webkit-font-smoothing: antialiased;
}
.glass {
    background: var(--card-bg);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border);
    border-radius: 16px;
    box-shadow: 0 4px 24px -2px rgba(0, 0, 0, 0.4), inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}
.btn-pro {
    background: linear-gradient(135deg, var(--accent) 0%, #6d28d9 100%);
    color: white;
    border: 1px solid rgba(255,255,255,0.1);
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 15px var(--accent-glow);
    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
.event-type { background: var(--accent); color: #fff; font-size: 10px; font-weight: 800; padding: 3px 8px; border-radius: 6px; text-transform: uppercase; margin-right: 8px; letter-spacing: 0.5px; box-shadow: 0 0 10px var(--accent-glow); }
.audit-box { background: rgba(0,0,0,0.5); border: 1px solid var(--border); border-radius: 12px; padding: 25px; margin-top: 20px; box-shadow: inset 0 2px 10px rgba(0,0,0,0.5); }
.shield-alert { color: var(--danger); font-weight: 800; display: flex; align-items: center; gap: 10px; margin-bottom: 15px; }
.ai-badge { display: inline-block; background: linear-gradient(90deg, #a371f7, #3fb950); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 900; letter-spacing: 1px; }
.audit-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }
.audit-key { color: var(--text-muted); }
.audit-val { color: var(--text); font-weight: 600; }
.btn-pro:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px var(--accent-glow), inset 0 1px 0 0 rgba(255,255,255,0.2);
    border-color: rgba(255,255,255,0.3);
}
.btn-pro:active {
    transform: translateY(0);
}
@keyframes float {
    0% { transform: translateY(0px) scale(1); }
    50% { transform: translateY(-12px) scale(1.02); }
    100% { transform: translateY(0px) scale(1); }
}
"""

async def get_current_user(request: Request):
    # 1. Token from query param (embedded in page HTML — most reliable)
    q_tok = request.query_params.get("_tok")
    if q_tok:
        user_id = database.get_session_user(q_tok)
        if user_id:
            return user_id

    # 2. DB-based session cookie (Telegram link login or migrated web login)
    token = request.cookies.get("session_token")
    if token:
        user_id = database.get_session_user(token)
        if user_id:
            return user_id
    
    # 3. Legacy in-memory session (web form login before fix, dies on restart)
    session_id = request.cookies.get("session_id")
    if session_id and session_id in SESSIONS:
        return SESSIONS[session_id]
    
    raise HTTPException(status_code=401, detail="Not authenticated")

@app.get("/login", response_class=HTMLResponse)
async def login_handler(token: str):
    user_id = database.get_session_user(token)
    if user_id:
        response = RedirectResponse(url="/dashboard", status_code=303)
        # Set secure cookie (HttpOnly)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)
        return response
    return HTMLResponse("<body style='background:#0b0e14;color:#f85149;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;'><h2>❌ Access Denied: Invalid or Expired Token</h2></body>")


@app.get("/", response_class=HTMLResponse)
async def login_page(u: str = None):
    avatar_url = MASCOT_URL
    if u:
        user = database.get_user_by_web_id(u)
        if user: avatar_url = user.get('profile_pic') or MASCOT_URL
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Neo -IDE | Access Denied</title>
        <style>
            {CSS_SHARED}
            body {{ display: flex; align-items: center; justify-content: center; height: 100vh; background: radial-gradient(circle at center, #1b112e 0%, #0b0e14 100%); }}
            .login-box {{ width: 400px; padding: 40px; text-align: center; position: relative; }}
            .mascot {{ width: 140px; height: 140px; border-radius: 50%; border: 3px solid var(--accent); margin-bottom: 25px; animation: float 4s ease-in-out infinite; object-fit: cover; box-shadow: 0 0 20px var(--accent-glow); }}
            input {{ width: 100%; padding: 14px; margin: 10px 0; background: rgba(0,0,0,0.3); border: 1px solid var(--border); border-radius: 8px; color: white; box-sizing: border-box; outline: none; }}
            input:focus {{ border-color: var(--accent); }}
            h2 {{ margin: 0 0 10px; font-weight: 800; letter-spacing: -1px; }}
            .glow-text {{ color: var(--accent); text-shadow: 0 0 10px var(--accent-glow); }}
        </style>
    </head>
    <body>
        <div class="login-box glass">
            <img src="{avatar_url}" class="mascot">
            <h2>Neo <span class="glow-text">GOD CONSOLE</span></h2>
            <p style="font-size: 13px; color: #8b949e; margin-bottom: 25px;">Enter credentials to unlock the engine.</p>
            <form action="/login" method="post">
                <input type="text" name="web_id" placeholder="User Identifier" value="{u or ''}" required>
                <input type="password" name="password" placeholder="Access Token" required>
                <button type="submit" class="btn-pro" style="width: 100%; margin-top: 15px;">AUTHENTICATE</button>
            </form>
        </div>
    </html>
    """

@app.post("/login")
async def login(web_id: str = Form(...), password: str = Form(...)):
    user = database.get_user_by_web_id(web_id)
    if user and user['password'] == password:
        # Use DB-based session (persists across server restarts)
        token = database.create_session(user['user_id'])
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)
        # Also keep in-memory for backward compat
        session_id = os.urandom(16).hex()
        SESSIONS[session_id] = user['user_id']
        response.set_cookie(key="session_id", value=session_id)
        return response
    return HTMLResponse("<body style='background:#0b0e14;color:#f85149;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;'><h2>❌ Access Denied: Invalid Credentials</h2></body>")

@app.get("/u/{web_id}")
async def user_direct_entry(web_id: str):
    return RedirectResponse(url=f"/?u={web_id}")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    # DB session first, then in-memory fallback
    user_id = None
    token = request.cookies.get("session_token")
    if token:
        user_id = database.get_session_user(token)
    if not user_id:
        session_id = request.cookies.get("session_id")
        if session_id and session_id in SESSIONS:
            user_id = SESSIONS[session_id]
    
    if not user_id:
        return RedirectResponse(url="/")
    
    user = database.get_user(user_id)
    projects = database.get_user_projects(user_id)
    
    avatar_url = user.get('profile_pic') or MASCOT_URL
    
    proj_cards = ""
    for p in projects:
        status_color = "#3fb950" if p['status'] == 'running' else "#f85149"
        status_text = "ENGINE ONLINE" if p['status'] == 'running' else "ENGINE OFFLINE"
        proj_cards += f'''
        <div class="proj-card glass" onclick="location.href='/edit/{p["project_id"]}'">
            <div class="status-dot" style="background: {status_color}"></div>
            <div class="proj-name">{p["name"]}</div>
            <div class="proj-meta">{p["type"].upper()} CORE • {status_text}</div>
            <div class="proj-hover">LAUNCH EDITOR →</div>
        </div>
        '''

    avatar_options = "".join([f'<img src="{url}" class="avatar-item" onclick="setAvatar(\'{url}\')">' for url in PRESET_AVATARS])

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard | God Console</title>
        <style>
            {CSS_SHARED}
            body {{ padding: 60px 10%; background: linear-gradient(to bottom, #0d1117, #0b0e14); min-height: 100vh; }}
            .header {{ display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 50px; }}
            h1 {{ margin: 0; font-size: 38px; font-weight: 900; letter-spacing: -1.5px; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 25px; }}
            .proj-card {{ padding: 30px; cursor: pointer; position: relative; transition: 0.3s; overflow: hidden; }}
            .proj-card:hover {{ transform: translateY(-8px); border-color: var(--accent); }}
            .status-dot {{ width: 10px; height: 10px; border-radius: 50%; margin-bottom: 15px; box-shadow: 0 0 10px currentColor; }}
            .proj-name {{ font-size: 20px; font-weight: 700; margin-bottom: 5px; }}
            .proj-meta {{ font-size: 12px; color: #8b949e; letter-spacing: 1px; }}
            .proj-hover {{ margin-top: 20px; font-size: 13px; font-weight: 800; color: var(--accent); opacity: 0; transition: 0.3s; }}
            .proj-card:hover .proj-hover {{ opacity: 1; }}
            .logout-btn {{ background: #21262d; border: 1px solid var(--border); color: #8b949e; padding: 10px 20px; border-radius: 8px; cursor: pointer; }}
            .logout-btn:hover {{ color: #f85149; border-color: #f85149; }}
            
            .user-avatar {{ width: 50px; height: 50px; border-radius: 50%; border: 2px solid var(--accent); cursor: pointer; transition: 0.3s; object-fit: cover; }}
            .user-avatar:hover {{ transform: scale(1.1); box-shadow: 0 0 15px var(--accent-glow); }}
            
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); align-items: center; justify-content: center; z-index: 1000; backdrop-filter: blur(5px); }}
            .modal-content {{ width: 380px; padding: 30px; text-align: center; }}
            .avatar-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-top: 25px; }}
            .avatar-item {{ width: 90px; height: 90px; border-radius: 50%; cursor: pointer; border: 2px solid transparent; transition: 0.3s; object-fit: cover; background: #000; }}
            .avatar-item:hover {{ border-color: var(--accent); transform: scale(1.05); }}
        </style>
    </head>
    <body class="{'theme-cyber' if user.get('theme') == 'theme-cyber' else 'theme-anime' if user.get('theme') == 'theme-anime' else ''}">
        <div class="header">
            <div>
                <p style="color: var(--accent); font-weight: 800; margin: 0; letter-spacing: 2px;">COMMAND CENTER</p>
                <h1>My <span style="color: var(--accent);">Projects</span></h1>
            </div>
            <div style="display: flex; align-items: center; gap: 20px;">
                <img src="{avatar_url}" class="user-avatar" onclick="openAvatarModal()">
                <button class="logout-btn" onclick="window.open('https://t.me/HostifyZip_bot', '_blank')">BOT LINK</button>
                <button class="logout-btn" onclick="location.href='/logout'">DISCONNECT</button>
            </div>
        </div>
        <div class="grid">{proj_cards}</div>
        
        <div id="avatarModal" class="modal">
            <div class="modal-content glass">
                <h3 style="margin: 0;">Change Avatar</h3>
                <p style="font-size: 12px; color: #8b949e;">Select a gaming persona</p>
                <div class="avatar-grid">
                    {avatar_options}
                </div>
                <button class="btn-pro" style="margin-top: 30px; width: 100%;" onclick="closeAvatarModal()">CANCEL</button>
            </div>
        </div>

        <script>
            function openAvatarModal() {{ document.getElementById('avatarModal').style.display = 'flex'; }}
            function closeAvatarModal() {{ document.getElementById('avatarModal').style.display = 'none'; }}
            async function setAvatar(url) {{
                await fetch('/api/user/avatar', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ avatar_url: url }})
                }});
                location.reload();
            }}
        </script>

        <div style="margin-top: 60px; text-align: center; color: #30363d; font-size: 12px; font-weight: 700;">
            Neo HOSTING X • V2.0 PREMIUM
        </div>
    </body>
    </html>
    """

@app.get("/edit/{project_id}", response_class=HTMLResponse)
async def edit_page(project_id: str, request: Request):
    # DB session first, then in-memory fallback
    user_id = None
    token = request.cookies.get("session_token")
    if token:
        user_id = database.get_session_user(token)
    if not user_id:
        session_id = request.cookies.get("session_id")
        if session_id and session_id in SESSIONS:
            user_id = SESSIONS[session_id]
            # migrate to DB session
            token = database.create_session(user_id)
    
    if not user_id:
        return RedirectResponse(url="/")
    
    # store token for embedding in HTML (so API calls can use it)
    user_token = token or ""
    
    projects = database.get_user_projects(user_id)
    if not any(p['project_id'] == project_id for p in projects):
        return RedirectResponse(url="/dashboard")
    
    project_path = manager.BASE_DIR / project_id
    files = [f.name for f in project_path.iterdir() if f.is_file() and not f.name.startswith('.')]
    
    def file_icon(name):
        ext = name.rsplit('.', 1)[-1] if '.' in name else ''
        icons = {'py': '\U0001f40d', 'js': '\u26a1', 'json': '\U0001f4cb', 'html': '\U0001f310', 'css': '\U0001f3a8', 'md': '\U0001f4dd', 'txt': '\U0001f4c4', 'sh': '\U0001f4df', 'env': '\U0001f512', 'yml': '\u2699\ufe0f', 'yaml': '\u2699\ufe0f', 'toml': '\u2699\ufe0f'}
        return icons.get(ext, '\U0001f4c4')
    
    files_html = "".join([f'<div class="file-item" onclick="loadFile(\'{name}\', this)"><span class="file-icon">{file_icon(name)}</span> {name}</div>' for name in sorted(files)])

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Editor | {project_id}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/dracula.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/shell/shell.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/selection/active-line.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/display/placeholder.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            {CSS_SHARED}
            * { box-sizing: border-box; }
            body { height: 100vh; display: flex; flex-direction: column; font-family: 'Inter', sans-serif; }
            .layout { flex: 1; display: flex; overflow: hidden; }

            /* SIDEBAR */
            #sidebar { width: 260px; min-width: 260px; background: #0c1018; border-right: 1px solid rgba(255,255,255,0.06); display: flex; flex-direction: column; }
            .sidebar-header { padding: 16px 20px; border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; align-items: center; gap: 10px; }
            .sidebar-header i { color: var(--accent); font-size: 14px; }
            .sidebar-header span { font-size: 11px; font-weight: 700; color: #8b949e; letter-spacing: 1.5px; text-transform: uppercase; }
            .file-list { flex: 1; overflow-y: auto; padding: 8px 0; }
            .file-item { padding: 8px 20px; cursor: pointer; font-size: 13px; transition: all 0.15s; color: #8b949e; display: flex; align-items: center; gap: 10px; font-family: 'JetBrains Mono', monospace; border-left: 3px solid transparent; }
            .file-item:hover { background: rgba(255,255,255,0.03); color: #c9d1d9; }
            .file-item.active { color: #e6edf3; background: rgba(163,113,247,0.08); border-left-color: var(--accent); }
            .file-icon { font-size: 15px; width: 20px; text-align: center; }

            /* HEADER BAR */
            .top-bar { height: 52px; background: linear-gradient(180deg, #0d1117 0%, #0c1018 100%); border-bottom: 1px solid rgba(255,255,255,0.06); display: flex; justify-content: space-between; align-items: center; padding: 0 20px; flex-shrink: 0; }
            .top-bar-left { display: flex; align-items: center; gap: 16px; }
            .back-btn { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08); color: #8b949e; padding: 6px 14px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
            .back-btn:hover { background: rgba(255,255,255,0.08); color: #e6edf3; }
            .breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; }
            .breadcrumb .sep { color: #484f58; }
            .breadcrumb .proj { color: #8b949e; }
            .breadcrumb .fname { color: var(--accent); font-weight: 600; font-family: 'JetBrains Mono', monospace; }
            .top-bar-right { display: flex; align-items: center; gap: 10px; }
            .stat-pill { font-size: 11px; color: #8b949e; background: rgba(255,255,255,0.04); padding: 5px 14px; border-radius: 20px; border: 1px solid rgba(255,255,255,0.06); font-family: 'JetBrains Mono', monospace; }
            .stat-pill .val { color: var(--accent); font-weight: 600; }
            .btn-sm { background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08); color: #c9d1d9; padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 12px; font-weight: 600; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
            .btn-sm:hover { background: rgba(255,255,255,0.1); }
            .deploy-btn { background: linear-gradient(135deg, #238636, #2ea44f) !important; color: #fff !important; border: none !important; box-shadow: 0 2px 12px rgba(46,164,79,0.3); }
            .deploy-btn:hover { box-shadow: 0 4px 20px rgba(46,164,79,0.5); transform: translateY(-1px); }
            .deploy-btn.loading { opacity: 0.7; pointer-events: none; }

            /* TABS */
            .tab-bar { display: flex; background: #010409; border-bottom: 1px solid rgba(255,255,255,0.06); flex-shrink: 0; }
            .tab { padding: 10px 22px; cursor: pointer; color: #484f58; font-size: 12px; font-weight: 600; transition: all 0.15s; border-bottom: 2px solid transparent; letter-spacing: 0.3px; }
            .tab:hover { color: #8b949e; background: rgba(255,255,255,0.02); }
            .tab.active { color: var(--accent); border-bottom-color: var(--accent); background: rgba(163,113,247,0.04); }

            /* EDITOR */
            #editor-container { flex: 1; display: flex; flex-direction: column; background: #0b0e14; min-width: 0; }
            #editor-view { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
            .CodeMirror { flex: 1; font-family: 'JetBrains Mono', monospace !important; font-size: 14px !important; line-height: 1.65 !important; background: #0b0e14 !important; }
            .CodeMirror-gutters { background: #0c1018 !important; border-right: 1px solid rgba(255,255,255,0.04) !important; }
            .CodeMirror-linenumber { color: #484f58 !important; font-size: 12px !important; }
            .CodeMirror-activeline-background { background: rgba(255,255,255,0.02) !important; }
            .CodeMirror-cursor { border-left-color: var(--accent) !important; }
            .CodeMirror-selected { background: rgba(163,113,247,0.15) !important; }
            .cm-s-dracula .CodeMirror-gutters { background: #0c1018 !important; }
            .tab-content { display: none; }
            #editor-view { display: flex; }

            /* TERMINAL */
            #terminal { height: 180px; background: #010409; border-top: 1px solid rgba(255,255,255,0.06); display: flex; flex-direction: column; flex-shrink: 0; }
            .term-header { font-size: 11px; font-weight: 700; color: #8b949e; padding: 10px 20px; display: flex; align-items: center; gap: 8px; border-bottom: 1px solid rgba(255,255,255,0.04); letter-spacing: 0.5px; }
            .term-body { flex: 1; overflow-y: auto; padding: 12px 20px; }
            .term-logs { color: #7ee787; font-family: 'JetBrains Mono', monospace; font-size: 12px; white-space: pre-wrap; line-height: 1.6; }

            /* STATUS BAR */
            .status-bar { height: 28px; background: #0c1018; border-top: 1px solid rgba(255,255,255,0.04); display: flex; align-items: center; padding: 0 16px; font-size: 11px; color: #484f58; font-family: 'JetBrains Mono', monospace; gap: 16px; flex-shrink: 0; }
            .status-bar .status-item { display: flex; align-items: center; gap: 5px; }
            .status-bar .accent { color: var(--accent); }

            /* PANEL STYLES */
            .env-input { background: #0d1117; border: 1px solid rgba(255,255,255,0.08); color: #e6edf3; padding: 10px 14px; border-radius: 8px; flex: 1; outline: none; font-family: 'JetBrains Mono', monospace; font-size: 13px; transition: border 0.2s; }
            .env-input:focus { border-color: var(--accent); }
            .env-row { display: flex; gap: 10px; margin-bottom: 12px; align-items: center; background: rgba(255,255,255,0.02); padding: 12px 16px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.04); }
            .env-key { font-family: 'JetBrains Mono', monospace; font-weight: 600; width: 180px; color: var(--accent); font-size: 13px; }
            .env-val { flex: 1; font-family: 'JetBrains Mono', monospace; background: rgba(0,0,0,0.3); padding: 6px 12px; border-radius: 6px; color: #8b949e; font-size: 13px; }

            /* TOAST */
            .toast { position: fixed; top: 20px; right: 20px; padding: 14px 24px; border-radius: 10px; color: #fff; font-weight: 600; font-size: 13px; z-index: 9999; animation: slideIn 0.3s ease, fadeOut 0.5s 2.5s forwards; box-shadow: 0 8px 32px rgba(0,0,0,0.6); backdrop-filter: blur(8px); }
            .toast-success { background: linear-gradient(135deg, #238636, #2ea44f); }
            .toast-error { background: linear-gradient(135deg, #da3633, #f85149); }
            .toast-info { background: linear-gradient(135deg, #7928ca, #a371f7); }
            @keyframes slideIn { from { transform: translateX(120%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
            @keyframes fadeOut { to { opacity: 0; transform: translateY(-20px); } }

            @media (max-width: 768px) { #sidebar { width: 180px; min-width: 180px; } .top-bar { padding: 0 10px; } .tab { padding: 8px 12px; font-size: 10px; } .breadcrumb { display: none; } }
        </style>
    </head>
    <body>
        <div class="top-bar">
            <div class="top-bar-left">
                <button class="back-btn" onclick="location.href='/dashboard'"><i class="fas fa-chevron-left"></i> Dashboard</button>
                <div class="breadcrumb">
                    <span class="proj">{project_id}</span>
                    <span class="sep">/</span>
                    <span class="fname" id="cur-file-name">No file selected</span>
                </div>
            </div>
            <div class="top-bar-right">
                <div class="stat-pill" id="res-stats">CPU <span class="val" id="cpu-load">0%</span> &middot; RAM <span class="val" id="ram-load">0MB</span></div>
                <button class="btn-sm" onclick="location.href='/api/backup/{project_id}'"><i class="fas fa-download"></i> Backup</button>
                <button class="btn-sm deploy-btn" id="deploy-btn" onclick="saveFile()"><i class="fas fa-rocket"></i> Deploy</button>
            </div>
        </div>
        <div class="layout">
            <div id="sidebar">
                <div class="sidebar-header"><i class="fas fa-folder-open"></i> <span>Explorer</span></div>
                <div class="file-list">
                    {files_html}
                </div>
            </div>
            <div id="editor-container">
                <div class="tab-bar">
                    <div class="tab active" onclick="showTab('editor-view')" id="tab-editor"><i class="fas fa-code" style="margin-right:5px;font-size:10px;"></i> Code</div>
                    <div class="tab" onclick="showTab('env-view')" id="tab-env"><i class="fas fa-key" style="margin-right:5px;font-size:10px;"></i> Env</div>
                    <div class="tab" onclick="showTab('pkg-view')" id="tab-pkg"><i class="fas fa-cube" style="margin-right:5px;font-size:10px;"></i> Packages</div>
                    <div class="tab" onclick="showTab('events-view')" id="tab-events"><i class="fas fa-bolt" style="margin-right:5px;font-size:10px;"></i> Events</div>
                    <div class="tab" onclick="showTab('audit-view')" id="tab-audit"><i class="fas fa-shield-alt" style="margin-right:5px;font-size:10px;"></i> Audit</div>
                    <div class="tab" onclick="showTab('stats-view')" id="tab-stats"><i class="fas fa-chart-line" style="margin-right:5px;font-size:10px;"></i> Analytics</div>
                    <div class="tab" onclick="showTab('settings-view')" id="tab-settings"><i class="fas fa-cog" style="margin-right:5px;font-size:10px;"></i> Settings</div>
                </div>
                <div id="editor-view" class="tab-content" style="display:flex;">
                    <textarea id="editor-area" style="display:none;"></textarea>
                </div>
                <div id="env-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin-top:0;">Environment Variables</h3>
                        <p style="color: #8b949e; font-size: 13px;">Variables available via <code style="background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">os.environ</code></p>
                        <hr style="border: 0.5px solid rgba(255,255,255,0.06); margin: 20px 0;">
                        <div id="env-list"></div>
                        <div style="margin-top: 20px; display: flex; gap: 10px;">
                            <input type="text" id="new-env-key" placeholder="KEY" class="env-input">
                            <input type="text" id="new-env-val" placeholder="Value" class="env-input">
                            <button class="btn-pro" onclick="addEnv()" style="padding: 10px 20px;"><i class="fas fa-plus"></i></button>
                        </div>
                    </div>
                </div>
                <div id="pkg-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin-top:0;">Package Manager</h3>
                        <p style="color: #8b949e; font-size: 13px;">Install Python/Node packages directly.</p>
                        <div style="margin-top: 20px; display: flex; gap: 10px;">
                            <input type="text" id="pkg-name" placeholder="Package name (e.g. requests)" class="env-input">
                            <button class="btn-pro" onclick="installPkg()"><i class="fas fa-download"></i> Install</button>
                        </div>
                        <div id="pkg-log" style="margin-top: 20px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #7ee787; background: rgba(0,0,0,0.4); padding: 16px; border-radius: 10px; display: none; border: 1px solid rgba(255,255,255,0.04);"></div>
                    </div>
                </div>
                <div id="events-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin-top:0;">Activity Log</h3>
                        <div id="event-list"></div>
                    </div>
                </div>
                <div id="audit-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin: 0;">Security Audit</h3>
                        <p style="color: #8b949e; font-size: 13px;">Code analysis by Neo Shield & Gemini AI.</p>
                        <div id="audit-results">
                            <div class="audit-box" style="text-align: center;">
                                <button class="btn-pro" onclick="loadAudit()"><i class="fas fa-play"></i> Run Audit</button>
                            </div>
                        </div>
                    </div>
                </div>
                <div id="stats-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin-top:0;">Performance</h3>
                        <canvas id="usageChart" style="margin-top: 20px;"></canvas>
                    </div>
                </div>
                <div id="settings-view" class="tab-content" style="padding: 40px; overflow-y: auto;">
                    <div class="glass" style="padding: 30px; max-width: 800px; margin: 0 auto;">
                        <h3 style="margin-top:0;">Settings</h3>
                        <div class="env-row">
                            <div class="env-key">Theme</div>
                            <select id="theme-selector" onchange="changeTheme(this.value)" class="env-input">
                                <option value="default">Neo Dark</option>
                                <option value="theme-cyber">Cyberpunk</option>
                                <option value="theme-anime">Anime Pastel</option>
                            </select>
                        </div>
                        <div class="env-row">
                            <div class="env-key">Webhook</div>
                            <button class="btn-pro" onclick="toggleWebhook()" id="webhook-btn" style="padding:8px 16px;">Enable</button>
                        </div>
                        <hr style="border:0.5px solid rgba(255,255,255,0.06); margin:20px 0;">
                        <h3>Snapshots</h3>
                        <div id="snapshot-list">
                            <div style="text-align:center;"><button class="btn-pro" onclick="createSnapshot()"><i class="fas fa-camera"></i> Create Snapshot</button></div>
                        </div>
                    </div>
                </div>
                <div id="terminal">
                    <div class="term-header">
                        <i class="fas fa-terminal" style="color:var(--accent);"></i> TERMINAL
                        <div style="margin-left:auto; display:flex; align-items:center; gap:15px;">
                            <button class="btn-sm" style="padding: 4px 10px; font-size: 10px; background: rgba(163,113,247,0.15); color: var(--accent); border-color: rgba(163,113,247,0.3);" onclick="installRequirements()"><i class="fas fa-box-open"></i> Install Packages</button>
                            <span id="log-status" style="font-size:10px;color:#7ee787;">&#9679; LIVE</span>
                        </div>
                    </div>
                    <div class="term-body">
                        <div class="term-logs" id="log-box">Connecting...</div>
                    </div>
                </div>
            </div>
        </div>
        <div class="status-bar">
            <div class="status-item"><i class="fas fa-circle" style="font-size:8px;color:#7ee787;"></i> Ready</div>
            <div class="status-item">Ln <span class="accent" id="sb-line">1</span>, Col <span class="accent" id="sb-col">1</span></div>
            <div class="status-item" id="sb-lang">Python</div>
            <div class="status-item" style="margin-left:auto;">{project_id}</div>
        </div>
        <script>
            let curFile = null;
            let usageChart = null;
            const PID = "{project_id}";
            const TOK = "{user_token}";
            let cmEditor = null;
            let usingCM = false;

            // Try CodeMirror, fall back to textarea
            try {
                if(typeof CodeMirror !== 'undefined') {
                    const edView = document.getElementById('editor-view');
                    cmEditor = CodeMirror(edView, {
                        theme: 'dracula',
                        lineNumbers: true,
                        matchBrackets: true,
                        autoCloseBrackets: true,
                        styleActiveLine: true,
                        tabSize: 4,
                        indentWithTabs: false,
                        lineWrapping: false,
                        mode: 'python'
                    });
                    cmEditor.on('cursorActivity', function() {
                        var pos = cmEditor.getCursor();
                        document.getElementById('sb-line').innerText = pos.line + 1;
                        document.getElementById('sb-col').innerText = pos.ch + 1;
                    });
                    usingCM = true;
                    console.log('CodeMirror loaded OK');
                } else { throw new Error('CodeMirror not available'); }
            } catch(err) {
                console.warn('CodeMirror failed, using textarea:', err);
                var ta = document.getElementById('editor-area');
                if(ta) {
                    ta.style.display = 'block';
                    ta.style.flex = '1';
                    ta.style.background = 'transparent';
                    ta.style.color = '#babbbd';
                    ta.style.border = 'none';
                    ta.style.padding = '20px';
                    ta.style.fontFamily = "'JetBrains Mono', monospace";
                    ta.style.fontSize = '14px';
                    ta.style.outline = 'none';
                    ta.style.resize = 'none';
                    ta.style.lineHeight = '1.6';
                    ta.spellcheck = false;
                    ta.placeholder = '// Select a file to start editing...';
                }
            }

            function editorGetValue() {
                if(usingCM && cmEditor) return cmEditor.getValue();
                var ta = document.getElementById('editor-area');
                return ta ? ta.value : '';
            }
            function editorSetValue(val) {
                if(usingCM && cmEditor) { cmEditor.setValue(val); cmEditor.clearHistory(); return; }
                var ta = document.getElementById('editor-area');
                if(ta) ta.value = val;
            }
            function editorSetMode(name) {
                if(!usingCM || !cmEditor) return;
                var ext = name.split('.').pop().toLowerCase();
                var modes = {py:'python',js:'javascript',json:{name:'javascript',json:true},html:'htmlmixed',htm:'htmlmixed',css:'css',sh:'shell',bash:'shell',xml:'xml'};
                cmEditor.setOption('mode', modes[ext] || 'python');
            }
            function editorRefresh() {
                if(usingCM && cmEditor) { try { cmEditor.refresh(); } catch(e){} }
            }
            function editorFocus() {
                if(usingCM && cmEditor) { try { cmEditor.focus(); } catch(e){} }
                else { var ta = document.getElementById('editor-area'); if(ta) ta.focus(); }
            }

            function getModeName(name) {
                var ext = name.split('.').pop().toLowerCase();
                var langMap = {py:'Python',js:'JavaScript',json:'JSON',html:'HTML',htm:'HTML',css:'CSS',sh:'Shell',bash:'Shell',xml:'XML',md:'Markdown',txt:'Text',yml:'YAML',yaml:'YAML',toml:'TOML'};
                return langMap[ext] || 'Text';
            }

            function toast(msg, type) {
                type = type || 'info';
                var t = document.createElement('div');
                t.className = 'toast toast-' + type;
                t.innerText = msg;
                document.body.appendChild(t);
                setTimeout(function() { t.remove(); }, 3200);
            }

            async function safeFetch(url, opts) {
                try {
                    opts = opts || {};
                    opts.credentials = 'include';
                    // append token as query param (fallback for cookie issues)
                    var sep = url.includes('?') ? '&' : '?';
                    if(TOK) url = url + sep + '_tok=' + encodeURIComponent(TOK);
                    var res = await fetch(url, opts);
                    if(!res.ok) {
                        if(res.status === 401) {
                            toast('Auth failed (' + res.status + '). Token: ' + (TOK ? TOK.substring(0,8)+'...' : 'EMPTY'), 'error');
                            return null;
                        }
                        toast('Server error: ' + res.status, 'error'); return null;
                    }
                    return await res.json();
                } catch(e) { toast('Network error: ' + e.message, 'error'); return null; }
            }

            function showTab(tabId) {
                try {
                    document.querySelectorAll('.tab-content').forEach(function(c) { c.style.display = 'none'; });
                    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
                    var panel = document.getElementById(tabId);
                    if(panel) panel.style.display = (tabId === 'editor-view') ? 'flex' : 'block';
                    var tabBtn = document.getElementById('tab-' + tabId.split('-')[0]);
                    if(tabBtn) tabBtn.classList.add('active');
                    if(tabId === 'editor-view') setTimeout(editorRefresh, 50);
                    if(tabId === 'env-view') loadEnvs();
                    if(tabId === 'stats-view') initChart();
                    if(tabId === 'events-view') loadEvents();
                } catch(e) { console.error('showTab error:', e); }
            }

            function changeTheme(theme) {
                document.body.className = theme === 'default' ? '' : theme;
                localStorage.setItem('nagi-theme', theme);
            }

            async function installRequirements() {
                var btn = document.querySelector('#terminal .btn-sm');
                var originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Installing...';
                btn.disabled = true;
                
                var box = document.getElementById('log-box');
                box.innerText += '\\n[INSTALL] Starting requirements installation...\\n';
                box.parentElement.scrollTop = box.parentElement.scrollHeight;

                var data = await safeFetch('/api/pkg/install_reqs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ project_id: PID })
                });

                btn.innerHTML = originalHTML;
                btn.disabled = false;

                if (data) {
                    box.innerText += '\\n[INSTALL] Output:\\n' + data.output + '\\n';
                    box.parentElement.scrollTop = box.parentElement.scrollHeight;
                    toast('Installation finished!', 'success');
                } else {
                    box.innerText += '\\n[INSTALL] Request failed.\\n';
                    box.parentElement.scrollTop = box.parentElement.scrollHeight;
                    toast('Failed to install requirements.', 'error');
                }
            }

            async function installPkg() {
                var pkg = document.getElementById('pkg-name').value;
                if(!pkg) return;
                var log = document.getElementById('pkg-log');
                log.style.display = 'block';
                log.innerText = 'Installing ' + pkg + '...';
                var data = await safeFetch('/api/pkg/install', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ project_id: PID, pkg: pkg })
                });
                if(data) { log.innerText = data.output || 'Done.'; toast('Package installed!', 'success'); }
                else { log.innerText = 'Failed to install. Check session.'; }
            }

            function initChart() {
                try {
                    if(usageChart) return;
                    if(typeof Chart === 'undefined') return;
                    var ctx = document.getElementById('usageChart').getContext('2d');
                    usageChart = new Chart(ctx, {
                        type: 'line',
                        data: { labels: [], datasets: [
                            { label: 'CPU %', borderColor: '#a371f7', data: [], fill: false, tension: 0.4 },
                            { label: 'RAM MB', borderColor: '#3fb950', data: [], fill: false, tension: 0.4 }
                        ]},
                        options: { responsive: true, scales: { y: { beginAtZero: true }, x: { grid: { display: false } } } }
                    });
                    updateChart();
                } catch(e) { console.error('Chart init error:', e); }
            }

            async function updateChart() {
                if(!usageChart) return;
                var data = await safeFetch('/api/perf/' + PID);
                if(!data || !Array.isArray(data)) return;
                usageChart.data.labels = data.map(function(h) { return (h.timestamp || '').split(' ')[1] || ''; });
                usageChart.data.datasets[0].data = data.map(function(h) { return h.cpu || 0; });
                usageChart.data.datasets[1].data = data.map(function(h) { return h.ram || 0; });
                usageChart.update();
            }

            async function loadAudit() {
                var box = document.getElementById('audit-results');
                box.innerHTML = '<div style="text-align:center;padding:20px;color:#8b949e;"><i class="fas fa-circle-notch fa-spin"></i> Analyzing...</div>';
                var data = await safeFetch('/api/audit/' + PID);
                if(!data) { box.innerHTML = '<div style="text-align:center;color:#f85149;">Audit failed. Try again.</div>'; return; }
                var html = '<div style="padding:15px;">';
                if(data.security && data.security.length > 0) {
                    html += '<div style="color:#f85149;font-weight:700;margin-bottom:10px;"><i class="fas fa-exclamation-triangle"></i> Security Issues</div>';
                    data.security.forEach(function(s) { html += '<div style="margin-bottom:5px;color:#f85149;">- ' + s + '</div>'; });
                } else {
                    html += '<div style="color:#3fb950;font-weight:700;"><i class="fas fa-shield-alt"></i> No risks found</div>';
                }
                html += '<hr style="border:0.5px solid rgba(255,255,255,0.06);margin:15px 0;">';
                html += '<div style="color:#8b949e;font-size:13px;">Engine: ' + (data.engine||'N/A') + '</div>';
                if(data.ai_audit) html += '<div style="margin-top:15px;color:#e6edf3;font-size:13px;line-height:1.6;">' + data.ai_audit + '</div>';
                html += '</div>';
                box.innerHTML = html;
            }

            async function loadEvents() {
                var events = await safeFetch('/api/events/' + PID);
                var box = document.getElementById('event-list');
                if(!events || !Array.isArray(events)) { box.innerHTML = '<div style="color:#8b949e;text-align:center;">No events yet.</div>'; return; }
                box.innerHTML = events.map(function(e) {
                    return '<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);align-items:center;">' +
                        '<span style="background:rgba(163,113,247,0.15);color:var(--accent);padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;">' + (e.event_type||'') + '</span>' +
                        '<span style="color:#c9d1d9;font-size:13px;flex:1;">' + (e.message||'') + '</span>' +
                        '<span style="color:#484f58;font-size:11px;">' + ((e.timestamp||'').split(' ')[1]||'') + '</span></div>';
                }).join('');
            }

            async function loadSnapshots() {
                var data = await safeFetch('/api/snapshots/' + PID);
                var list = document.getElementById('snapshot-list');
                list.innerHTML = '<div style="text-align:center;margin-bottom:15px;"><button class="btn-pro" onclick="createSnapshot()"><i class="fas fa-camera"></i> Create Snapshot</button></div>';
                if(!data || !Array.isArray(data)) return;
                data.forEach(function(s) {
                    list.innerHTML += '<div style="display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid rgba(255,255,255,0.04);"><span style="color:#c9d1d9;font-size:13px;">Snap #' + s.snapshot_id + ' - ' + s.created_at + '</span><button class="btn-pro" style="padding:4px 10px;font-size:10px;background:#f85149;" onclick="restoreSnapshot(' + s.snapshot_id + ')">Rollback</button></div>';
                });
            }

            async function createSnapshot() {
                await safeFetch('/api/snapshot/create/' + PID, {method: 'POST'});
                toast('Snapshot created!', 'success');
                loadSnapshots();
            }

            async function restoreSnapshot(sid) {
                if(!confirm('Restore this version?')) return;
                await safeFetch('/api/snapshot/restore/' + PID + '/' + sid, {method: 'POST'});
                toast('Snapshot restored!', 'success');
                setTimeout(function() { location.reload(); }, 1000);
            }

            async function loadEnvs() {
                var list = document.getElementById('env-list');
                list.innerHTML = '<div style="color:#8b949e;">Loading...</div>';
                var envs = await safeFetch('/api/env/' + PID);
                if(!envs) {
                    list.innerHTML = '<div style="color:#f85149;padding:10px;">⚠️ Failed to load. Token: ' + (TOK ? TOK.substring(0,8)+'...' : 'MISSING') + '</div>';
                    return;
                }
                list.innerHTML = '';
                var keys = Object.keys(envs);
                if(keys.length === 0) { list.innerHTML = '<div style="color:#8b949e;">No variables set yet.</div>'; return; }
                for(var k in envs) {
                    if(!envs.hasOwnProperty(k)) continue;
                    list.innerHTML += '<div class="env-row"><div class="env-key">' + k + '</div><div class="env-val">********</div><button onclick="deleteEnv(\'' + k + '\')" style="background:transparent;border:none;color:#f85149;cursor:pointer;"><i class="fas fa-trash"></i></button></div>';
                }
            }

            async function addEnv() {
                var key = document.getElementById('new-env-key').value;
                var value = document.getElementById('new-env-val').value;
                if(!key || !value) { toast('Fill both fields', 'error'); return; }
                var data = await safeFetch('/api/env/save', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ project_id: PID, key: key, value: value }) });
                if(data) { toast('Variable added!', 'success'); document.getElementById('new-env-key').value = ''; document.getElementById('new-env-val').value = ''; loadEnvs(); }
            }

            async function deleteEnv(key) {
                if(!confirm('Delete variable ' + key + '?')) return;
                await safeFetch('/api/env/delete', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ project_id: PID, key: key, value: '' }) });
                toast('Variable deleted', 'info');
                loadEnvs();
            }

            async function loadFile(name, el) {
                curFile = name;
                document.getElementById('cur-file-name').innerText = name;
                document.querySelectorAll('.file-item').forEach(function(e) { e.classList.remove('active'); });
                if(el) el.classList.add('active');
                editorSetMode(name);
                document.getElementById('sb-lang').innerText = getModeName(name);
                var data = await safeFetch('/api/file?filename=' + encodeURIComponent(name) + '&project_id=' + PID);
                if(data) { editorSetValue(data.content || ''); }
                else { editorSetValue('// Error loading file'); }
                showTab('editor-view');
                setTimeout(function() { editorRefresh(); editorFocus(); }, 100);
            }

            async function saveFile() {
                if(!curFile) { toast('Select a file first!', 'error'); return; }
                var btn = document.getElementById('deploy-btn');
                btn.classList.add('loading');
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deploying...';
                var content = editorGetValue();
                document.getElementById('log-box').innerText += '\n[DEPLOY] Saving ' + curFile + '...';
                var data = await safeFetch('/api/save', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ project_id: PID, filename: curFile, content: content }) });
                btn.classList.remove('loading');
                btn.innerHTML = '<i class="fas fa-rocket"></i> Deploy';
                if(data && data.status === 'ok') { toast('Deployed successfully!', 'success'); }
                else { toast('Deploy failed. Check logs.', 'error'); }
            }

            // Log stream
            setInterval(async function() {
                try {
                    var tokParam = TOK ? '?_tok=' + encodeURIComponent(TOK) : '';
                    var res = await fetch('/api/logs/' + PID + tokParam, {credentials: 'include'});
                    if(!res.ok) { document.getElementById('log-status').innerHTML = '&#9679; DISCONNECTED'; document.getElementById('log-status').style.color = '#f85149'; return; }
                    var data = await res.json();
                    document.getElementById('log-status').innerHTML = '&#9679; LIVE';
                    document.getElementById('log-status').style.color = '#7ee787';
                    var box = document.getElementById('log-box');
                    var logs = data.logs || 'No logs available.';
                    if(logs !== box.innerText) { box.innerText = logs; box.parentElement.scrollTop = box.parentElement.scrollHeight; }
                } catch(e) { document.getElementById('log-status').innerHTML = '&#9679; OFFLINE'; document.getElementById('log-status').style.color = '#f85149'; }
            }, 2500);

            // Stats
            setInterval(async function() {
                try {
                    var tokParam = TOK ? '?_tok=' + encodeURIComponent(TOK) : '';
                    var res = await fetch('/api/stats/' + PID + tokParam, {credentials: 'include'});
                    if(!res.ok) return;
                    var data = await res.json();
                    document.getElementById('cpu-load').innerText = (data.cpu || 0) + '%';
                    document.getElementById('ram-load').innerText = (data.ram || 0) + 'MB';
                } catch(e) {}
            }, 3500);

            // Periodic refresh
            setInterval(function() {
                try {
                    if(document.getElementById('stats-view').style.display === 'block') updateChart();
                    if(document.getElementById('events-view').style.display === 'block') loadEvents();
                } catch(e) {}
            }, 10000);

            async function toggleWebhook() {
                var btn = document.getElementById('webhook-btn');
                var isEnabled = btn.innerText.includes('Disable');
                await safeFetch('/api/webhooks/toggle', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ project_id: PID, enabled: !isEnabled }) });
                btn.innerText = isEnabled ? 'Enable' : 'Disable';
                btn.style.background = isEnabled ? '' : '#2ea44f';
            }

            window.onload = function() {
                var savedTheme = localStorage.getItem('nagi-theme');
                if(savedTheme) changeTheme(savedTheme);
                editorRefresh();
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html
        .replace("{project_id}", project_id)
        .replace("{user_token}", user_token)
        .replace("{CSS_SHARED}", CSS_SHARED)
        .replace("{files_html}", files_html)
    )

@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/")
    response.delete_cookie("session_id")
    response.delete_cookie("session_token")
    return response

@app.get("/api/debug")
async def debug_endpoint(request: Request):
    token = request.cookies.get("session_token")
    session_id = request.cookies.get("session_id")
    user_from_token = database.get_session_user(token) if token else None
    user_from_session = SESSIONS.get(session_id) if session_id else None
    return {
        "has_session_token": bool(token),
        "has_session_id": bool(session_id),
        "token_user": user_from_token,
        "session_user": user_from_session,
        "active_sessions_count": len(SESSIONS),
        "auth_working": bool(user_from_token or user_from_session)
    }

# API Endpoints
class SaveData(BaseModel):
    project_id: str
    filename: str
    content: str

@app.get("/api/file")
async def get_file(project_id: str, filename: str, user_id: int = Depends(get_current_user)):
    # Verify ownership
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    path = manager.BASE_DIR / project_id / filename
    return {"content": open(path, encoding='utf-8', errors='ignore').read()}

@app.post("/api/save")
async def save_file(data: SaveData, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, data.project_id): raise HTTPException(403, "Unauthorized")
    path = manager.BASE_DIR / data.project_id / data.filename
    # Ensure directory exists (critical fix)
    if not (manager.BASE_DIR / data.project_id).exists():
        (manager.BASE_DIR / data.project_id).mkdir(parents=True, exist_ok=True)
        
    with open(path, 'w', encoding='utf-8') as f: f.write(data.content)
    manager.stop_project(data.project_id)
    entry = manager.detect_entry_point(data.project_id)
    manager.start_project(data.project_id, "js" if entry.endswith(".js") else "py", entry)
    return {"status": "ok"}

@app.get("/api/logs/{project_id}")
async def get_logs(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    return {"logs": manager.get_logs(project_id, 30)}

@app.get("/api/stats/{project_id}")
async def get_project_stats(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    return manager.get_project_stats(project_id)

@app.get("/api/backup/{project_id}")
async def download_backup(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    zip_path = manager.get_project_zip(project_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Backup failed")
    return FileResponse(zip_path, filename=f"project_{project_id}.zip")

# --- Environment API ---
@app.get("/api/env/{project_id}")
async def get_envs(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    return database.get_project_envs(project_id)

class EnvData(BaseModel):
    project_id: str
    key: str
    value: str

@app.post("/api/env/save")
async def save_env(data: EnvData, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, data.project_id): raise HTTPException(403, "Unauthorized")
    database.set_project_env(data.project_id, data.key, data.value)
    return {"status": "ok"}

@app.post("/api/env/delete")
async def delete_env(data: EnvData, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, data.project_id): raise HTTPException(403, "Unauthorized")
    database.delete_project_env(data.project_id, data.key)
    return {"status": "ok"}

@app.post("/api/pkg/install")
async def install_package(data: dict, user_id: int = Depends(get_current_user)):
    pid = data['project_id']
    if not is_owner(user_id, pid): raise HTTPException(403, "Unauthorized")
    pkg = data['pkg']
    p_path = manager.BASE_DIR / pid
    is_py = any(p_path.glob("*.py"))
    
    try:
        import subprocess
        if is_py:
            exe = manager.get_executable(pid, "py").replace("python", "pip")
            cmd = [exe, "install", pkg]
        else:
            cmd = ["npm", "install", pkg]
            
        res = subprocess.run(cmd, cwd=str(p_path), capture_output=True, text=True, timeout=60)
        return {"output": res.stdout + res.stderr}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}

@app.post("/api/pkg/install_reqs")
async def install_requirements(data: dict, user_id: int = Depends(get_current_user)):
    pid = data['project_id']
    if not is_owner(user_id, pid): raise HTTPException(403, "Unauthorized")
    p_path = manager.BASE_DIR / pid
    is_py = any(p_path.glob("*.py"))
    
    try:
        import subprocess
        if is_py:
            req_file = p_path / "requirements.txt"
            if not req_file.exists():
                return {"output": "requirements.txt not found. Please create it first."}
            exe = manager.get_executable(pid, "py").replace("python", "pip")
            cmd = [exe, "install", "-r", "requirements.txt"]
        else:
            pkg_file = p_path / "package.json"
            if not pkg_file.exists():
                return {"output": "package.json not found. Please create it first."}
            cmd = ["npm", "install"]
            
        res = subprocess.run(cmd, cwd=str(p_path), capture_output=True, text=True, timeout=120)
        return {"output": res.stdout + res.stderr}
    except Exception as e:
        return {"output": f"Error: {str(e)}"}

@app.get("/api/perf/{project_id}")
async def get_perf(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    return database.get_perf_history(project_id)

@app.post("/api/webhooks/toggle")
async def toggle_webhook(data: dict, user_id: int = Depends(get_current_user)):
    pid = data['project_id']
    if not is_owner(user_id, pid): raise HTTPException(403, "Unauthorized")
    database.toggle_project_webhook(pid, data['enabled'])
    return {"status": "ok"}

@app.post("/webhook/{project_id}")
async def github_webhook(project_id: str):
    success, msg = manager.git_pull(project_id)
    if success:
        manager.stop_project(project_id)
        ep = manager.detect_entry_point(project_id)
        manager.start_project(project_id, "js" if ep.endswith(".js") else "py", ep)
        database.add_event(project_id, "WEBHOOK", "Auto-updated via GitHub push.")
    return {"status": "received"}

@app.post("/api/user/avatar")
async def update_avatar(data: dict, user_id: int = Depends(get_current_user)):
    database.update_user_avatar(user_id, data['avatar_url'])
    return {"status": "ok"}

@app.get("/api/events/{project_id}")
async def get_project_events(project_id: str):
    return database.get_events(project_id, limit=20)

@app.get("/api/audit/{project_id}")
async def get_project_audit(project_id: str, user_id: int = Depends(get_current_user)):
    if not is_owner(user_id, project_id): raise HTTPException(403, "Unauthorized")
    return manager.get_source_audit(project_id, str(user_id))

@app.get("/api/snapshots/{project_id}")
async def get_snapshots(project_id: str):
    return database.get_snapshots(project_id)

@app.post("/api/snapshot/create/{project_id}")
async def create_snapshot(project_id: str):
    manager.create_snapshot(project_id)
    return {"status": "ok"}

@app.post("/api/snapshot/restore/{project_id}/{snapshot_id}")
async def restore_snapshot(project_id: str, snapshot_id: str):
    success, msg = manager.restore_snapshot(project_id, snapshot_id)
    return {"status": "ok" if success else "error", "message": msg}
