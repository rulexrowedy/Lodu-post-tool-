# ===================== IMPORTS =====================
import streamlit as st
import time, threading, random, uuid, os, json, gc, requests
from collections import deque
from playwright.sync_api import sync_playwright

# ===================== PAGE CONFIG =====================
st.set_page_config(
    page_title="FB Comment Tool",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===================== KEEP ALIVE =====================
def keep_alive():
    def ping():
        while True:
            try: requests.get("http://127.0.0.1:8501", timeout=5)
            except: pass
            time.sleep(25)
    threading.Thread(target=ping, daemon=True).start()

keep_alive()

# ===================== KEEP ALIVE JS =====================
KEEP_ALIVE_JS = """
<script>
setInterval(()=>{fetch(window.location.href,{method:'HEAD'}).catch(()=>{})},25000);
setInterval(()=>{document.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:Math.random()*200,clientY:Math.random()*200}))},60000);
</script>
"""

# ===================== ORIGINAL CSS (UNCHANGED) =====================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
* { font-family: 'Poppins', sans-serif; }
.stApp { background-image:url('https://i.postimg.cc/TYhXd0gG/d0a72a8cea5ae4978b21e04a74f0b0ee.jpg'); background-size:cover; background-attachment:fixed; }
.main .block-container { background:rgba(255,255,255,0.08); backdrop-filter:blur(8px); border-radius:12px; padding:20px; }
.main-header { background:rgba(255,255,255,0.1); padding:1rem; border-radius:12px; text-align:center; }
.main-header h1 { background:linear-gradient(45deg,#ff6b6b,#4ecdc4); -webkit-background-clip:text; -webkit-text-fill-color:transparent; font-size:1.8rem; }
.stButton>button { background:linear-gradient(45deg,#ff6b6b,#4ecdc4); color:white; border-radius:8px; width:100%; }
.console-box { background:rgba(0,0,0,0.6); color:#00ff88; font-family:monospace; font-size:11px; padding:10px; border-radius:8px; }
</style>
"""

st.markdown(custom_css, unsafe_allow_html=True)
st.markdown(KEEP_ALIVE_JS, unsafe_allow_html=True)

# ===================== STORAGE =====================
LOGS_DIR = "session_logs"
DB_FILE = "sessions_registry.json"
MAX_LOGS = 30
os.makedirs(LOGS_DIR, exist_ok=True)

# ===================== SESSION =====================
class Session:
    __slots__ = ['id','running','count','idx','logs']
    def __init__(self,sid):
        self.id=sid; self.running=False; self.count=0; self.idx=0
        self.logs=deque(maxlen=MAX_LOGS)
    def log(self,m):
        t=time.strftime('%H:%M:%S'); line=f"[{t}] {m}"; self.logs.append(line)
        open(f"{LOGS_DIR}/{self.id}.log","a").write(line+"
")

# ===================== DB =====================
def load_db():
    return json.load(open(DB_FILE)) if os.path.exists(DB_FILE) else {}

def save_db(d): json.dump(d, open(DB_FILE,'w'))

# ===================== COOKIES =====================
# Supports:
# 1) Single paste cookies (textarea)
# 2) Upload cookies TXT (one line = one account, auto rotate)

def parse_cookie_string(cookie_str):
    ck = {}
    for p in cookie_str.split(';'):
        if '=' in p:
            k,v = p.split('=',1)
            ck[k.strip()] = v.strip()
    return ck


def load_cookies_from_upload(uploaded_file):
    cookies = []
    if not uploaded_file:
        return cookies
    content = uploaded_file.read().decode('utf-8')
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        cookies.append(parse_cookie_string(line))
    return cookies

# ===================== HUMAN ACTION =====================
def human(page):
    page.mouse.move(random.randint(50,400), random.randint(50,400))
    page.mouse.wheel(0, random.randint(50,200))

# ===================== BROWSER =====================
def launch():
    p=sync_playwright().start()
    b=p.firefox.launch(headless=True, firefox_user_prefs={
        'permissions.default.image':2,
        'media.autoplay.default':0,
        'dom.ipc.processCount':1,
        'browser.cache.disk.enable':False,
        'browser.cache.memory.enable':False
    })
    ctx=b.new_context(viewport={'width':1280,'height':720})
    return p,b,ctx,ctx.new_page()

# ===================== WORKER =====================
def worker(s,post,comments,delay):
    cookies=load_cookies(); ci=0
    while s.running:
        try:
            p,b,ctx,page=launch()
            page.goto('https://facebook.com',timeout=60000)
            time.sleep(5)
            if cookies:
                ck=cookies[ci%len(cookies)]; ci+=1
                ctx.add_cookies([{'name':k,'value':v,'domain':'.facebook.com','path':'/'} for k,v in ck.items()])
            page.goto(post,timeout=60000)
            page.wait_for_timeout(15000)
            while s.running:
                box=page.locator("div[contenteditable='true']").first
                box.click(); human(page)
                msg=comments[s.idx%len(comments)]; s.idx+=1
                for ch in msg:
                    box.type(ch, delay=random.randint(30,80))
                box.press('Enter')
                s.count+=1
                db=load_db(); db[s.id]['count']=s.count; save_db(db)
                s.log(f"Comment {s.count}")
                wait=max(10,int(delay+random.uniform(-10,10)))
                for _ in range(wait):
                    if not s.running: break
                    time.sleep(1)
        except Exception as e:
            s.log(f"Restart: {str(e)[:40]}")
        finally:
            try: ctx.close(); b.close(); p.stop()
            except: pass
            gc.collect(); time.sleep(5)

# ===================== UI =====================
st.markdown('<div class="main-header"><h1>FB Comment Tool</h1></div>',unsafe_allow_html=True)
post=st.text_input('Post URL')
delay=st.number_input('Delay (seconds)',10,3600,30)
comments=st.text_area('Comments (one per line)')

if st.button('START NEW SESSION'):
    sid=uuid.uuid4().hex[:8].upper()
    db=load_db(); db[sid]={'count':0,'running':True}; save_db(db)
    s=Session(sid); s.running=True
    threading.Thread(target=worker,args=(s,post,[c for c in comments.split('
') if c.strip()],delay),daemon=True).start()
    st.success(f"Session Started: {sid}")
