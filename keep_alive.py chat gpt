import threading
import time
import requests
import os

def keep_alive(port=8501):
    def ping():
        url = f"http://127.0.0.1:{port}"
        while True:
            try:
                requests.get(url, timeout=5)
            except:
                pass
            time.sleep(25)   # every 25 seconds

    t = threading.Thread(target=ping, daemon=True)
    t.start()
