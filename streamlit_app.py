import os
import time

# Auto-install Playwright and Firefox
os.system("playwright install firefox")

import streamlit as st
import threading
import gc
import json
import uuid
import random
from pathlib import Path
from collections import deque
from playwright.sync_api import sync_playwright
import psutil

st.set_page_config(
    page_title="FB Comment Tool",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

KEEP_ALIVE_JS = """
<script>
    setInterval(function() { fetch(window.location.href, {method: 'HEAD'}).catch(function(){}); }, 25000);
    setInterval(function() { document.dispatchEvent(new MouseEvent('mousemove', {bubbles: true, clientX: Math.random()*1920, clientY: Math.random()*1080})); }, 60000);
    setInterval(function() { window.scrollBy(0, Math.random()*100 - 50); }, 90000);
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
    .stButton>button:hover { opacity: 0.9; }
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
        background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 8px; color: white; padding: 0.6rem;
    }
    label { color: white !important; font-weight: 500 !important; font-size: 13px !important; }
    .console-box {
        background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(78, 205, 196, 0.5);
        border-radius: 8px; padding: 10px; font-family: 'Courier New', monospace;
        font-size: 11px; color: #00ff88; max-height: 250px; overflow-y: auto; min-height: 100px;
    }
    .log-line { padding: 3px 6px; border-left: 2px solid #4ecdc4; margin: 2px 0; background: rgba(0,0,0,0.3); word-break: break-all; }
    .status-running { background: linear-gradient(135deg, #84fab0, #8fd3f4); padding: 8px; border-radius: 8px; color: #000; text-align: center; font-weight: 600; }
    .status-stopped { background: linear-gradient(135deg, #fa709a, #fee140); padding: 8px; border-radius: 8px; color: #000; text-align: center; font-weight: 600; }
    [data-testid="stMetricValue"] { color: #4ecdc4; font-weight: 700; }
    .session-id-box { background: linear-gradient(45deg, #667eea, #764ba2); padding: 10px 15px; border-radius: 8px; color: white; font-weight: 600; font-family: monospace; text-align: center; margin: 10px 0; }
    .active-sessions { background: rgba(0,0,0,0.4); border: 1px solid rgba(78, 205, 196, 0.5); border-radius: 10px; padding: 15px; margin-top: 20px; }
    .session-row { background: rgba(255,255,255,0.1); padding: 10px; border-radius: 6px; margin: 5px 0; display: flex; justify-content: space-between; align-items: center; }
    .danger-btn { background: linear-gradient(45deg, #fa709a, #fee140) !important; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)
st.markdown(KEEP_ALIVE_JS, unsafe_allow_html=True)

SESSIONS_FILE = "sessions_registry.json"
LOGS_DIR = "session_logs"
MAX_LOGS = 40

os.makedirs(LOGS_DIR, exist_ok=True)

class Session:
    def __init__(self, sid):
        self.id = sid
        self.running = False
        self.count = 0
        self.logs = deque(maxlen=MAX_LOGS)
        self.idx = 0
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.start_time = None
        self.profile_id = None
        self.cookies_list = []
    
    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        profile_str = f" {self.profile_id}" if self.profile_id else ""
        log_entry = f"[{ts}]{profile_str} {msg}"
        self.logs.append(log_entry)
        try:
            with open(f"{LOGS_DIR}/{self.id}.log", "a") as f:
                f.write(log_entry + "\n")
        except:
            pass

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
                            s.running = info.get('running', False)
                            s.start_time = info.get('start_time')
                            self.sessions[sid] = s
            except:
                pass
    
    def _save_registry(self):
        try:
            data = {}
            for sid, s in self.sessions.items():
                data[sid] = {
                    'count': s.count,
                    'running': s.running,
                    'start_time': s.start_time
                }
            with open(SESSIONS_FILE, 'w') as f:
                json.dump(data, f)
        except:
            pass
    
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
            self.cleanup_resources(s)
            self._save_registry()
    
    def delete_session(self, sid):
        s = self.sessions.get(sid)
        if s:
            s.running = False
            self.cleanup_resources(s)
            del self.sessions[sid]
            try:
                os.remove(f"{LOGS_DIR}/{sid}.log")
            except:
                pass
            self._save_registry()
            gc.collect()

    def cleanup_resources(self, s):
        try:
            if s.context: s.context.close()
            if s.browser: s.browser.close()
            if s.playwright: s.playwright.stop()
        except:
            pass
        s.context = None
        s.browser = None
        s.playwright = None
        s.page = None
    
    def get_logs(self, sid, limit=30):
        log_file = f"{LOGS_DIR}/{sid}.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    return lines[-limit:]
            except:
                pass
        s = self.sessions.get(sid)
        if s:
            return list(s.logs)[-limit:]
        return []
    
    def update_count(self, sid, count):
        s = self.sessions.get(sid)
        if s:
            s.count = count
            self._save_registry()

manager = get_session_manager()

def parse_cookies(cookie_string):
    cookies = []
    if not cookie_string:
        return cookies
    for c in cookie_string.split(';'):
        c = c.strip()
        if c and '=' in c:
            i = c.find('=')
            name = c[:i].strip()
            value = c[i+1:].strip()
            cookies.append({'name': name, 'value': value, 'domain': '.facebook.com', 'path': '/'})
    return cookies

def setup_browser(session):
    session.log('Setting up Firefox (RAM Optimized)...')
    try:
        p = sync_playwright().start()
        session.playwright = p
        # Use a more robust launch strategy
        browser = p.firefox.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        session.browser = browser
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
            viewport={'width': 1280, 'height': 720}
        )
        session.context = context
        page = context.new_page()
        session.page = page
        session.log('Browser ready!')
        return page
    except Exception as e:
        error_msg = str(e)
        session.log(f'Browser setup error: {error_msg}')
        if "playwright install" in error_msg.lower() or "executable" in error_msg.lower():
            session.log("Installing missing browser binaries (First time setup)...")
            import subprocess
            subprocess.run(["playwright", "install", "firefox"], check=True)
            # Try again after install
            return setup_browser(session)
        raise e

def run_session(session, post_id, cookies_list, comments_list, prefix, delay):
    retries = 0
    session.cookies_list = cookies_list
    
    while session.running and retries < 5:
        try:
            if not session.page:
                setup_browser(session)
            
            current_cookies_raw = random.choice(session.cookies_list)
            current_cookies = parse_cookies(current_cookies_raw)
            
            session.log('Navigating to Facebook...')
            session.page.goto('https://www.facebook.com/', wait_until='domcontentloaded', timeout=60000)
            
            if current_cookies:
                session.log('Adding cookies...')
                session.context.add_cookies(current_cookies)
                session.log('✅ Cookies Added')
            
            session.log(f'Opening post...')
            url = post_id if post_id.startswith('http') else f'https://www.facebook.com/{post_id}'
            session.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            time.sleep(5)
            
            input_not_found_count = 0
            while session.running:
                try:
                    # Improved interaction logic
                    session.log('Finding comment input...')
                    selectors = [
                        'div[contenteditable="true"][role="textbox"]',
                        'div[aria-label*="comment" i][contenteditable="true"]',
                        'div[role="textbox"]',
                        '[placeholder*="comment" i]',
                        'textarea'
                    ]
                    
                    comment_input = None
                    for sel in selectors:
                        try:
                            comment_input = session.page.wait_for_selector(sel, timeout=10000)
                            if comment_input:
                                break
                        except:
                            continue

                    if not comment_input:
                        input_not_found_count += 1
                        if input_not_found_count >= 3:
                            session.log('❌ Comment input not found')
                            session.running = False
                            break
                        session.page.reload(wait_until='domcontentloaded')
                        time.sleep(10)
                        continue
                    
                    input_not_found_count = 0
                    base_comment = comments_list[session.idx % len(comments_list)]
                    session.idx += 1
                    comment_to_send = f"{prefix} {base_comment}" if prefix else base_comment
                    
                    session.log(f'Typing: {comment_to_send[:25]}...')
                    comment_input.click()
                    comment_input.fill(comment_to_send)
                    time.sleep(1)
                    
                    # Try both keyboard and click for reliability
                    session.log('Clicking send...')
                    try:
                        # Find the send button
                        send_button = session.page.query_selector('div[aria-label*="Post" i][role="button"], div[aria-label*="Send" i][role="button"]')
                        if send_button:
                            send_button.click()
                        else:
                            session.page.keyboard.press('Enter')
                    except:
                        session.page.keyboard.press('Enter')
                        
                    time.sleep(3)
                    
                    session.count += 1
                    manager.update_count(session.id, session.count)
                    session.log(f'Comment #{session.count} sent!')
                    
                    wait_time = int(delay + random.uniform(-30, 30))
                    wait_time = max(10, wait_time)
                    session.log(f'⏳ Waiting {wait_time}s...')
                    for _ in range(wait_time):
                        if not session.running: break
                        time.sleep(1)
                    
                    if session.count % 5 == 0:
                        gc.collect()
                        
                except Exception as e:
                    session.log(f'Error: {str(e)[:50]}')
                    time.sleep(5)
                    break
        except Exception as e:
            session.log(f'Global Error: {str(e)[:50]}')
            retries += 1
            manager.cleanup_resources(session)
            time.sleep(10)

    session.running = False
    manager.cleanup_resources(session)
    session.log('Session Ended')

# UI Implementation
st.markdown('<div class="main-header"><h1>FB Comment Tool (Firefox Edition)</h1></div>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown('<div class="active-sessions">', unsafe_allow_html=True)
    post_id = st.text_input("Post ID / Link", placeholder="Enter post ID or full URL")
    comment_prefix = st.text_input("Comment Prefix", placeholder="(Optional)")
    delay = st.number_input("Delay (Seconds)", min_value=30, value=30, step=10)
    
    # Cookie File Upload
    cookie_file = st.file_uploader("Upload Cookies File (.txt)", type=["txt"])
    raw_cookies = ""
    if cookie_file:
        raw_cookies = cookie_file.read().decode('utf-8')
    else:
        raw_cookies = st.text_area("Or Paste Cookies (one per line)", placeholder="Cookie 1\nCookie 2...")
    
    # Comment File Upload
    cmt_file = st.file_uploader("Upload Comments File (.txt)", type=["txt"])
    comments_text = ""
    if cmt_file:
        comments_text = cmt_file.read().decode('utf-8')
    else:
        comments_text = st.text_area("Or Paste Comments (one per line)", placeholder="Cmt 1\nCmt 2...", height=150)
    
    if st.button("🚀 Start Non-stop Automation"):
        if not post_id or not raw_cookies or not comments_text:
            st.error("Please fill all required fields!")
        else:
            cookies_list = [c.strip() for c in raw_cookies.replace('|', '\n').split('\n') if c.strip()]
            cmts = [c.strip() for c in comments_text.split('\n') if c.strip()]
            
            session = manager.create_session()
            session.running = True
            session.start_time = time.time()
            threading.Thread(target=run_session, args=(session, post_id, cookies_list, cmts, comment_prefix, delay), daemon=True).start()
            st.success(f"Session {session.id} started!")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="active-sessions">', unsafe_allow_html=True)
    st.subheader("📊 Active Sessions")
    if st.button("🔄 Refresh Task List"):
        st.rerun()
    
    for s in manager.get_all_sessions():
        status_class = "status-running" if s.running else "status-stopped"
        status_text = "Running" if s.running else "Stopped"
        
        with st.expander(f"Session {s.id} - {status_text}", expanded=s.running):
            st.markdown(f'<div class="{status_class}">{status_text}</div>', unsafe_allow_html=True)
            st.metric("Comments Sent", s.count)
            
            logs = manager.get_logs(s.id)
            log_content = "".join([f'<div class="log-line">{l}</div>' for l in logs])
            st.markdown(f'<div class="console-box">{log_content}</div>', unsafe_allow_html=True)
            
            if s.running:
                if st.button(f"🛑 Stop {s.id}", key=f"stop_{s.id}"):
                    manager.stop_session(s.id)
                    st.rerun()
            else:
                if st.button(f"🗑️ Delete {s.id}", key=f"del_{s.id}"):
                    manager.delete_session(s.id)
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Resource Monitoring
st.sidebar.markdown("### 🖥️ Server Status")
process = psutil.Process(os.getpid())
mem_mb = process.memory_info().rss / 1024 / 1024
st.sidebar.metric("RAM Usage", f"{mem_mb:.1f} MB")
if mem_mb > 450:
    gc.collect()
    st.sidebar.warning("High Memory! Cleaning up...")
