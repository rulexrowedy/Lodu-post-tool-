import streamlit as st
import time
import threading
import gc
import json
import os
import uuid
import random
from pathlib import Path
from collections import deque
from playwright.sync_api import sync_playwright
import database
from flask import Flask
from threading import Thread

# Auto-install Firefox for Playwright
os.system("playwright install firefox")

# --- Keep Alive System (Embedded) ---
app = Flask('')

@app.route('/')
def home():
    return "Server is Always Active"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Streamlit Config ---
st.set_page_config(
    page_title="FB Comment Tool",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

KEEP_ALIVE_JS = """
<script>
    setInterval(function() { fetch(window.location.href, {method: 'HEAD'}).catch(function(){}); }, 25000);
    setInterval(function() { document.dispatchEvent(new MouseEvent('mousemove', {bubbles: true, clientX: Math.random()*200, clientY: Math.random()*200})); }, 60000);
</script>
"""

custom_css = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    * { font-family: 'Poppins', sans-serif; }
    .stApp {
        background-image: url('https://i.postimg.cc/TYhXd0gG/d0a72a8cea5ae4978b21e04a74f0b0ee.jpg');
        background-size: cover; background-position: center; background-attachment: fixed;
    }
    .main .block-container {
        background: rgba(255, 255, 255, 0.08); backdrop-filter: blur(8px);
        border-radius: 12px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .main-header {
        background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px);
        padding: 1rem; border-radius: 12px; text-align: center; margin-bottom: 1rem;
    }
    .main-header h1 {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 1.8rem; font-weight: 700; margin: 0;
    }
    .stButton>button {
        background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
        color: white; border: none; border-radius: 8px; padding: 0.6rem 1.5rem;
        font-weight: 600; width: 100%;
    }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
        background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 8px; color: white; padding: 0.6rem;
    }
    label { color: white !important; font-weight: 500 !important; font-size: 13px !important; }
    .console-box {
        background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(78, 205, 196, 0.5);
        border-radius: 8px; padding: 10px; font-family: 'Courier New', monospace;
        font-size: 11px; color: #00ff88; max-height: 200px; overflow-y: auto;
        min-height: 100px;
    }
    .log-line { padding: 3px 6px; border-left: 2px solid #4ecdc4; margin: 2px 0; background: rgba(0,0,0,0.3); }
    .status-running { background: linear-gradient(135deg, #84fab0, #8fd3f4); padding: 8px; border-radius: 8px; color: white; text-align: center; font-weight: 600; }
    .status-stopped { background: linear-gradient(135deg, #fa709a, #fee140); padding: 8px; border-radius: 8px; color: white; text-align: center; font-weight: 600; }
    .online-indicator {
        display: inline-block; width: 10px; height: 10px; background-color: #00ff00;
        border-radius: 50%; margin-right: 5px; box-shadow: 0 0 5px #00ff00;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 5px rgba(0, 255, 0, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
    }
    [data-testid="stMetricValue"] { color: #4ecdc4; font-weight: 700; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)
st.markdown(KEEP_ALIVE_JS, unsafe_allow_html=True)

SESSIONS_FILE = "sessions_registry.json"
LOGS_DIR = "session_logs"
MAX_LOGS = 30
os.makedirs(LOGS_DIR, exist_ok=True)

class Session:
    __slots__ = ['id', 'running', 'count', 'logs', 'idx', 'browser', 'start_time', 'profile_id']
    def __init__(self, sid):
        self.id = sid
        self.running = False
        self.count = 0
        self.logs = deque(maxlen=MAX_LOGS)
        self.idx = 0
        self.browser = None
        self.start_time = None
        self.profile_id = None
    
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        profile_str = f" {self.profile_id}" if self.profile_id else ""
        log_entry = f"[{ts}]{profile_str} {msg}"
        self.logs.append(log_entry)
        try:
            with open(f"{LOGS_DIR}/{self.id}.log", "a") as f:
                f.write(log_entry + "\n")
        except: pass

@st.cache_resource
def get_session_manager():
    return SessionManager()

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.Lock()
        self._load_registry()
    
    def _load_registry(self):
        if os.path.exists(SESSIONS_FILE):
            try:
                with open(SESSIONS_FILE, 'r') as f:
                    data = json.load(f)
                    for sid, info in data.items():
                        if sid not in self.sessions:
                            s = Session(sid)
                            s.count = info.get('count', 0)
                            s.running = False
                            s.start_time = info.get('start_time')
                            self.sessions[sid] = s
            except: pass
    
    def _save_registry(self):
        try:
            data = {}
            for sid, s in self.sessions.items():
                data[sid] = {'count': s.count, 'running': s.running, 'start_time': s.start_time}
            with open(SESSIONS_FILE, 'w') as f:
                json.dump(data, f)
        except: pass
    
    def create_session(self):
        with self.lock:
            sid = uuid.uuid4().hex[:8].upper()
            s = Session(sid)
            self.sessions[sid] = s
            self._save_registry()
            return s
    
    def get_session(self, sid):
        return self.sessions.get(sid)
    
    def get_all_sessions(self):
        return list(self.sessions.values())
    
    def get_active_sessions(self):
        return [s for s in self.sessions.values() if s.running]
    
    def stop_session(self, sid):
        s = self.sessions.get(sid)
        if s:
            s.running = False
            self._save_registry()

    def delete_session(self, sid):
        with self.lock:
            s = self.sessions.get(sid)
            if s:
                s.running = False
                del self.sessions[sid]
                try: os.remove(f"{LOGS_DIR}/{sid}.log")
                except: pass
                self._save_registry()
                gc.collect()
    
    def get_logs(self, sid, limit=30):
        log_file = f"{LOGS_DIR}/{sid}.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return lines[-limit:]
            except: pass
        s = self.sessions.get(sid)
        if s: return list(s.logs)[-limit:]
        return []
    
    def update_count(self, sid, count):
        s = self.sessions.get(sid)
        if s:
            s.count = count
            self._save_registry()
            database.update_session(sid, count)

manager = get_session_manager()

def parse_cookies(cookies_text):
    cookies = []
    for line in cookies_text.split('\n'):
        line = line.strip()
        if line: cookies.append(line)
    return cookies

def format_cookies(cookie_str):
    pw_cookies = []
    for part in cookie_str.split(';'):
        if '=' in part:
            name, value = part.strip().split('=', 1)
            pw_cookies.append({'name': name.strip(), 'value': value.strip(), 'domain': '.facebook.com', 'path': '/'})
    return pw_cookies

def run_session(session, target_url, cookies_list, comments_list, delay):
    with sync_playwright() as p:
        try:
            browser = p.firefox.launch(headless=True)
            session.browser = browser
            cookie_idx = 0
            
            while session.running:
                cookie_str = cookies_list[cookie_idx % len(cookies_list)]
                cookie_idx += 1
                
                context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0")
                context.add_cookies(format_cookies(cookie_str))
                
                page = context.new_page()
                session.log("ID Online - Navigating...")
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                
                comment = random.choice(comments_list)
                session.log(f"Commenting: {comment[:20]}...")
                
                selectors = ['div[contenteditable="true"][role="textbox"]', 'div[aria-label="Write a comment"]']
                comment_box = None
                for sel in selectors:
                    try:
                        comment_box = page.wait_for_selector(sel, timeout=10000)
                        if comment_box: break
                    except: pass
                
                if comment_box:
                    comment_box.click()
                    page.keyboard.type(comment)
                    page.keyboard.press("Enter")
                    time.sleep(5)
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f"Comment #{session.count} sent!")
                else:
                    session.log("Input box not found.")
                
                context.close()
                
                jitter = random.randint(-30, 30)
                wait_time = max(10, delay + jitter)
                session.log(f"Waiting {wait_time}s (Jitter: {jitter}s)...")
                for _ in range(wait_time):
                    if not session.running: break
                    time.sleep(1)
                if not session.running: break
        except Exception as e:
            session.log(f"Error: {str(e)[:100]}")
        finally:
            if session.browser: session.browser.close()
            session.running = False
            session.log("Stopped.")

def start_session_playwright(session, target_url, cookies_text, comments_text, delay):
    session.running = True
    session.logs = deque(maxlen=MAX_LOGS)
    session.count = 0
    session.idx = 0
    session.start_time = time.strftime("%H:%M:%S")
    
    cookies_list = parse_cookies(cookies_text)
    comments_list = [c.strip() for c in comments_text.split('\n') if c.strip()]
    
    if not cookies_list or not comments_list:
        session.log("Missing cookies or comments.")
        session.running = False
        return

    database.create_session(session.id, "running", 0)
    session.log(f"Started with {len(cookies_list)} profiles.")
    threading.Thread(target=run_session, args=(session, target_url, cookies_list, comments_list, delay), daemon=True).start()

# --- UI ---
st.markdown('<div class="main-header"><h1>FB Comment Tool</h1></div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)
all_sessions = manager.get_all_sessions()
active_sessions = manager.get_active_sessions()
total_comments = sum(s.count for s in all_sessions)

col1.metric("Total Comments", total_comments)
col2.metric("Active Sessions", len(active_sessions))
with col3:
    if st.button("+ New Session"):
        manager.create_session()
        st.rerun()

st.markdown("---")

if 'view_session' not in st.session_state: st.session_state.view_session = None

if st.session_state.view_session:
    sid = st.session_state.view_session
    s = manager.get_session(sid)
    if s:
        st.markdown(f"### Session: `{sid}`")
        if s.running:
            st.markdown(f'<div class="status-running"><span class="online-indicator"></span>RUNNING - {s.count} comments</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-stopped">STOPPED</div>', unsafe_allow_html=True)
            
        logs = manager.get_logs(sid, 25)
        logs_html = '<div class="console-box">' + ''.join([f'<div class="log-line">{l.strip()}</div>' for l in logs]) + '</div>'
        st.markdown(logs_html, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Back to List"): st.session_state.view_session = None; st.rerun()
        with c2:
            if st.button("Stop Session", disabled=not s.running): manager.stop_session(sid); st.rerun()
        with c3:
            if st.button("Delete Session"): manager.delete_session(sid); st.session_state.view_session = None; st.rerun()
else:
    c1, c2 = st.columns(2)
    with c1:
        target_url = st.text_input("FB Post URL")
        delay = st.number_input("Fix Delay (seconds)", min_value=30, value=60)
    with c2:
        cookie_file = st.file_uploader("Upload Cookies File (.txt)", type=["txt"])
        cookies_manual = st.text_area("OR Paste Cookies (One profile per line)")
    
    comment_file = st.file_uploader("Upload Comments File (.txt)", type=["txt"])
    comments_manual = st.text_area("OR Paste Comments (One per line)")

    if st.button("Start Automation"):
        cookies = cookie_file.read().decode() if cookie_file else cookies_manual
        comments = comment_file.read().decode() if comment_file else comments_manual
        
        if target_url and cookies and comments:
            s = manager.create_session()
            start_session_playwright(s, target_url, cookies, comments, delay)
            st.session_state.view_session = s.id
            st.rerun()
        else:
            st.error("Fill all fields.")

    st.markdown('<div class="active-sessions"><h3>Active Sessions</h3>', unsafe_allow_html=True)
    for s in all_sessions:
        with st.container():
            col_a, col_b = st.columns([4, 1])
            status_text = "Running" if s.running else "Stopped"
            col_a.write(f"Session {s.id} | Status: {status_text} | Comments: {s.count}")
            if col_b.button("View", key=f"v_{s.id}"):
                st.session_state.view_session = s.id
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

keep_alive()
database.create_tables()
