import os
from dotenv import load_dotenv
load_dotenv()
import subprocess
import sys
import shutil
import zipfile
import psutil
import signal
import uuid
import google.generativeai as genai
from pathlib import Path
from datetime import datetime
import re
import database

ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", -1003253928645))
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# Railway Persistence
RAILWAY_MOUNT_PATH = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "/app/data")

if os.path.exists(RAILWAY_MOUNT_PATH):
    BASE_DIR = Path(RAILWAY_MOUNT_PATH) / "projects"
    LOGS_DIR = Path(RAILWAY_MOUNT_PATH) / "logs"
else:
    BASE_DIR = Path(__file__).resolve().parent / "projects"
    LOGS_DIR = Path("god_host/logs")

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

running_processes = {} # {project_id: subprocess.Popen}

def cleanup_orphans():
    print("🔍 Scanning for orphaned processes...")
    my_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        try:
            # Skip if it's us or no command line
            if proc.info['pid'] == my_pid or not proc.info['cmdline']:
                continue
            
            # Check if processing is running from our projects directory
            # Windows uses backslashes, Linux uses forward slashes
            path_marker = str(BASE_DIR).lower()
            cmdline_str = " ".join(proc.info['cmdline']).lower()
            
            if path_marker in cmdline_str:
                print(f"💀 Killing orphan: {proc.info['pid']} ({proc.info['name']})")
                proc.kill()
        except: continue

def get_source_audit(project_id, user_id="Unknown"):
    """Performs deep analysis and returns structured data for TG/Web."""
    p_path = BASE_DIR / project_id
    
    suspicious_patterns = {
        r"os\.remove|shutil\.rmtree": "File/Dir Deletion",
        r"subprocess\.|os\.system|pexpect": "System Shell Commands",
        r"getattr\(os|base64\.b64decode": "Obfuscated OS Calls",
        r"socket\.|bot\.send_document": "Data Exfiltration Risk",
        r"exec\(|eval\(": "Dynamic Code Injection",
        r"os\.walk|os\.listdir|glob\.": "File System Scanning",
        r"\.\.\/|\/etc\/passwd|\/root\/": "Path Traversal/Leaking",
        r"rm -rf|format C:|truncate": "Destructive Commands",
    }
    
    frameworks = []
    commands = []
    ui_elements = []
    security_findings = []
    
    for file in p_path.rglob("*.py"):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "aiogram" in content: frameworks.append("Aiogram")
                if "telebot" in content or "pyTelegramBotAPI" in content: frameworks.append("Telebot")
                if "pyrogram" in content: frameworks.append("Pyrogram")
                cmds = re.findall(r"['\"]/(\w+)['\"]", content)
                commands.extend(cmds)
                if "InlineKeyboardMarkup" in content: ui_elements.append("Inline Buttons")
                if "ReplyKeyboardMarkup" in content: ui_elements.append("Reply Buttons")
                if "templates" in content: ui_elements.append("Web Interface")
                for pattern, desc in suspicious_patterns.items():
                    if re.search(pattern, content):
                        security_findings.append(desc)
        except: pass

    # AI Audit with fresh key check
    key = os.getenv("GEMINI_API_KEY")
    ai_audit = "<i>AI Analysis not available (Key missing).</i>"
    if key:
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.0-flash')
            code_snippet = ""
            files = list(p_path.rglob("*.py"))
            # Get snippets from more files if possible to be accurate
            for file in files[:5]:
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    code_snippet += f"\n--- {file.name} ---\n{f.read()[:2000]}\n"
            
            prompt = (
                "Analyze this Telegram bot source code and provide a structured report in 100 words:\n"
                "1. **Bot Name/Title**: (Identify from code or filename)\n"
                "2. **Bot Category**: (e.g. Music, AI, Shop, Utility)\n"
                "3. **Functional Workflow**: (How it works and what the user does)\n"
                "4. **Security Risks**: (Any potential backdoors or risky calls)\n\n"
                f"Source Snippets:\n{code_snippet}"
            )
            response = model.generate_content(prompt)
            ai_audit = response.text
        except Exception as e:
            ai_audit = f"<i>AI Error: {str(e)}</i>"

    return {
        "engine": "/".join(set(frameworks)) if frameworks else "Unknown/Script",
        "ui": list(set(ui_elements)),
        "commands": sorted(list(set(commands)))[:10],
        "security": list(set(security_findings)),
        "ai_audit": ai_audit,
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def analyze_source_and_log(project_id, user_id, bot_instance):
    """Bridge for legacy bot logging."""
    audit = get_source_audit(project_id, user_id)
    
    report = f"👑 <b>NEO SOURCE ANALYZER V2.0</b>\n\n" \
             f"👤 <b>Uploader:</b> <code>{user_id}</code>\n" \
             f"🆔 <b>Project:</b> <code>{project_id}</code>\n" \
             f"📅 <b>Analyzed At:</b> {audit['timestamp']}\n" \
             f"────────────────────\n\n" \
             f"⚙️ <b>Engine:</b> <code>{audit['engine']}</code>\n"
    
    if audit['ui']: report += f"🎨 <b>UI Look:</b> {', '.join(audit['ui'])}\n"
    if audit['commands']: report += f"🕹 <b>Commands:</b> <code>/{', /'.join(audit['commands'])}</code>\n"
    
    report += f"\n🤖 <b>GEMINI AI AUDIT:</b>\n{audit['ai_audit']}\n"
    
    if audit['security']:
        report += f"\n🚨 <b>SHIELD ALERT:</b>\n" + "\n".join([f"• {f}" for f in audit['security']]) + "\n"
    else:
        report += f"\n🔒 <b>SECURITY:</b> Shield says it's 100% safe.\n"

    report += f"\n────────────────────\n"
    report += f"📝 <i>Source code is attached below for inspection.</i>"

    async def send_log():
        try:
            from aiogram.types import FSInputFile
            zip_path = get_project_zip(project_id)
            if zip_path:
                await bot_instance.send_document(LOG_CHANNEL_ID, FSInputFile(zip_path), caption=report, parse_mode="HTML")
            else:
                await bot_instance.send_message(LOG_CHANNEL_ID, report, parse_mode="HTML")
        except Exception as e:
            print(f"Logging Error: {e}")

    return send_log

def create_project_env(project_id, p_type):
    project_path = BASE_DIR / project_id
    os.makedirs(project_path, exist_ok=True)
    
    if p_type == "py":
        # Create Virtual Environment
        venv_path = project_path / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv_path)], check=True)
        return str(venv_path)
    return None

def extract_zip(zip_path, project_id):
    project_path = BASE_DIR / project_id
    os.makedirs(project_path, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        # Extract to a temporary folder inside project_path to avoid conflicts
        temp_extract = project_path / "_temp"
        zip_ref.extractall(temp_extract)
        
        # Check for nested structure (e.g., a single folder inside the zip)
        items = list(temp_extract.iterdir())
        if len(items) == 1 and items[0].is_dir():
            # Move contents up
            for sub_item in items[0].iterdir():
                dest = project_path / sub_item.name
                if dest.exists():
                    if dest.is_dir(): shutil.rmtree(dest)
                    else: os.remove(dest)
                shutil.move(str(sub_item), str(project_path))
            shutil.rmtree(temp_extract)
        else:
            # Move everything from temp to project_path
            for item in items:
                dest = project_path / item.name
                if dest.exists():
                    if dest.is_dir(): shutil.rmtree(dest)
                    else: os.remove(dest)
                shutil.move(str(item), str(project_path))
            shutil.rmtree(temp_extract)
            
    # Sanitize: some folders might have trailing spaces or special chars
    # This is a basic pass; in a real scenario, you'd be more thorough.
    return project_path

def clone_repo(repo_url, project_id):
    project_path = BASE_DIR / project_id
    try:
        # Clone repo using git command with timeout and no interactive prompts
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(["git", "clone", repo_url, str(project_path)], env=env, check=True, timeout=30)
        return True, "Success"
    except subprocess.TimeoutExpired:
        return False, "Clone timed out (30s). Is it a large repo or private?"
    except Exception as e:
        return False, str(e)

def git_pull(project_id):
    """Pulls the latest code from the cloned repository."""
    project_path = BASE_DIR / project_id
    if not (project_path / ".git").exists():
        return False, "Not a git repository."
    try:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        subprocess.run(["git", "pull"], cwd=str(project_path), env=env, check=True, timeout=30)
        return True, "Code pulled successfully."
    except Exception as e:
        return False, str(e)

def detect_entry_point(project_id):
    project_path = BASE_DIR / project_id
    # Priority for specialized bot files
    options = ["main.py", "bot.py", "app.py", "start.py", "run.py", "index.js", "app.js", "server.js"]
    for opt in options:
        if (project_path / opt).exists():
            return opt
    
    # Check for all .py files and find the one that might be main
    py_files = list(project_path.glob("*.py"))
    if py_files:
        # If there's only one, it's the one
        if len(py_files) == 1:
            return py_files[0].name
        # Try to find one with 'main' or 'bot' in name
        for f in py_files:
            if "main" in f.name.lower() or "bot" in f.name.lower():
                print(f"DEBUG: Found bot/main file: {f.name}")
                return f.name
        return py_files[0].name
        
    return "main.py" 

def extract_env_from_files(project_id):
    """Searches for .env files and parses standard KEY=VAL pairs."""
    p_path = BASE_DIR / project_id
    env_vars = {}
    
    # Check common .env file names
    env_files = [".env", "config.env", "vars.env"]
    for env_name in env_files:
        f_path = p_path / env_name
        if f_path.exists():
            try:
                with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"): continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            # Remove quotes if present
                            val = val.strip().strip("'").strip('"')
                            env_vars[key.strip()] = val
            except: pass
            
    # Also scan for secrets.json if exists
    secrets_json = p_path / "secrets.json"
    if secrets_json.exists():
        try:
            import json
            with open(secrets_json, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, (str, int, float)):
                            env_vars[str(k)] = str(v)
        except: pass
        
    return env_vars

def get_executable(project_id, p_type):
    project_path = BASE_DIR / project_id
    if p_type == "py":
        if os.name == "nt":
            return str(project_path / "venv" / "Scripts" / "python.exe")
        return str(project_path / "venv" / "bin" / "python")
    elif p_type == "js":
        return "node"
    return None

def get_project_stats(project_id):
    proc = running_processes.get(project_id)
    if not proc:
        return {"cpu": 0, "ram": 0, "status": "Offline"}
    
    try:
        p = psutil.Process(proc.pid)
        cpu = p.cpu_percent(interval=0.1)
        ram = p.memory_info().rss / (1024 * 1024) # MB
        return {"cpu": round(cpu, 1), "ram": round(ram, 1), "status": "Online"}
    except:
        return {"cpu": 0, "ram": 0, "status": "Crashing"}

def log_all_project_stats():
    """Loops through all running projects and logs their stats to the DB."""
    for pid in list(running_processes.keys()):
        stats = get_project_stats(pid)
        if stats['status'] == "Online":
            database.add_perf_log(pid, stats['cpu'], stats['ram'])


def get_project_zip(project_id):
    """Zips the project directory and returns the path to the zip file."""
    project_path = BASE_DIR / project_id
    if not project_path.exists():
        return None
    
    # Create zip in logs directory for temporary storage
    archive_name = LOGS_DIR / f"{project_id}_backup"
    shutil.make_archive(str(archive_name), 'zip', str(project_path))
    return f"{archive_name}.zip"

def auto_install_dependencies(project_id, file_path, pip_exe):
    """Scans a python file for imports and tries to install missing ones."""
    import re
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Regex to find imports
        imports = re.findall(r"^(?:from|import)\s+([\w\d.-]+)", content, re.M)
        
        # Filter out common standard libs and our own modules
        std_libs = {"os", "sys", "time", "datetime", "json", "re", "math", "random", "asyncio", "logging", "shutil", "pathlib", "subprocess", "threading", "uuid", "secrets", "io", "stat"}
        to_install = set()
        for imp in imports:
            base_mod = imp.split('.')[0]
            if base_mod not in std_libs and not (Path(file_path).parent / f"{base_mod}.py").exists():
                # Map common import names to pip names
                mapping = {"telebot": "pyTelegramBotAPI", "PIL": "Pillow", "cv2": "opencv-python", "bs4": "beautifulsoup4"}
                to_install.add(mapping.get(base_mod, base_mod))
        
        if to_install:
            print(f"📦 Auto-installing missing deps for {project_id}: {to_install}")
            subprocess.run([pip_exe, "install", *list(to_install)], check=False)
    except Exception as e:
        print(f"⚠️ Auto-install error: {e}")

def start_project(project_id, p_type, entry_point):
    project_path = BASE_DIR / project_id
    executable = get_executable(project_id, p_type)
    
    if not executable:
        return False, "Executable not found"

    # Enforce Approval System
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT is_approved, is_banned FROM projects JOIN users ON projects.user_id = users.user_id WHERE project_id = ?", (project_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        if row['is_banned']: return False, "Owner is banned from hosting."
        if not row['is_approved']: return False, "Project pending admin approval."
    
    log_file = LOGS_DIR / f"{project_id}.log"
    # Clear old log
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- Project Started at {datetime.now()} ---\n")

    try:
        # Install requirements if they exist (for Python)
        if p_type == "py":
            req_file = project_path / "requirements.txt"
            if req_file.exists():
                pip_exe = executable.replace("python", "pip")
                subprocess.run([pip_exe, "install", "-r", str(req_file)], check=False)
            else:
                # No requirements.txt? Try to auto-scan the entry point!
                pip_exe = executable.replace("python", "pip")
                auto_install_dependencies(project_id, project_path / entry_point, pip_exe)

        # Fix UTF-8 issue: Check if entry point has encoding declared
        if p_type == "py":
            e_file = project_path / entry_point
            if e_file.exists():
                with open(e_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                if lines and not ("coding:" in lines[0] or "coding:" in lines[1]):
                    content = "# -*- coding: utf-8 -*-\n" + "".join(lines)
                    with open(e_file, "w", encoding="utf-8") as f:
                        f.write(content)

        # Run project
        with open(log_file, "a", encoding="utf-8") as f:
            # Set UTF-8 encoding environment variable
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            
            # Inject Project Specific Envs from DB
            project_envs = database.get_project_envs(project_id)
            if project_envs:
                env.update(project_envs)
            proc = subprocess.Popen(
                [executable, entry_point],
                cwd=project_path,
                stdout=f,
                stderr=f,
                stdin=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            )
        
        running_processes[project_id] = proc
        database.add_event(project_id, "DEPLOY", "Engine booted successfully.")
        return True, proc.pid
    except Exception as e:
        database.add_event(project_id, "ERROR", f"Boot failed: {str(e)}")
        return False, str(e)

def stop_project(project_id):
    proc = running_processes.get(project_id)
    if not proc:
        return False
        
    try:
        # Get the process object
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        
        # Kill children first
        for child in children:
            try:
                child.kill()
            except: pass
            
        # Kill parent
        parent.kill()
        proc.wait(timeout=2)
    except:
        # Fallback for Windows if psutil fails
        if os.name == 'nt':
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            try: proc.kill()
            except: pass
            
    if project_id in running_processes:
        del running_processes[project_id]
    database.add_event(project_id, "STOP", "Engine stopped by user.")
    return True

def get_logs(project_id, lines=20):
    log_file = LOGS_DIR / f"{project_id}.log"
    if not log_file.exists():
        return "No logs found."
    
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.readlines()
        return "".join(content[-lines:])

def delete_project_files(project_id):
    stop_project(project_id)
    import time
    time.sleep(1) # Give OS time to release locks
    import stat
    def remove_readonly(func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    project_path = BASE_DIR / project_id
    if project_path.exists():
        shutil.rmtree(project_path, onerror=remove_readonly)
    database.delete_project(project_id)
    log_file = LOGS_DIR / f"{project_id}.log"
    if log_file.exists():
        os.remove(log_file)

def scan_project_code(project_id):
    """Scans all files in project for blacklisted patterns."""
    p_path = BASE_DIR / project_id
    blacklist = database.get_blacklist()
    
    for file in p_path.rglob("*.py"):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                for pattern in blacklist:
                    if pattern in content:
                        return False, f"Dangerous pattern found in {file.name}: {pattern}"
        except: pass
    return True, None

def create_snapshot(project_id):
    """Creates a local zip backup (snapshot) of the project."""
    import time
    timestamp = int(time.time())
    snap_dir = Path("god_host/snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    
    zip_name = f"{project_id}_{timestamp}.zip"
    zip_path = snap_dir / zip_name
    
    project_path = BASE_DIR / project_id
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_path):
            if "venv" in root: continue
            for file in files:
                abs_path = Path(root) / file
                zipf.write(abs_path, abs_path.relative_to(project_path))
                
    database.add_snapshot(project_id, str(zip_path))
    return True

def restore_snapshot(project_id, snapshot_id):
    """Restores files from a specific snapshot."""
    snapshots = database.get_snapshots(project_id)
    snap = next((s for s in snapshots if s['snapshot_id'] == int(snapshot_id)), None)
    if not snap: return False, "Snapshot not found."
    
    stop_project(project_id)
    p_path = BASE_DIR / project_id
    
    # Simple restore: extract over existing files
    with zipfile.ZipFile(snap['snapshot_path'], 'r') as zipf:
        zipf.extractall(p_path)
    
    database.add_event(project_id, "ROLLBACK", f"Project restored from snapshot #{snapshot_id}")
    return True, "Restored successfully."

def auto_restart_projects():
    """Restarts all projects that were 'running' in DB."""
    projects = database.get_all_projects()
    restarted = 0
    for p in projects:
        if p['status'] == 'running':
            print(f"🔄 Auto-restarting project {p['project_id']}...")
            start_project(p['project_id'], p['type'], p['entry_point'])
            restarted += 1
    return restarted
