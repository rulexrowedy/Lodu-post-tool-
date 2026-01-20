import json
import os
import threading
import time

DB_FILE = "sessions_registry.json"

class SessionManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.sessions = {}
        self._load()

    # ---------------- Load DB ----------------
    def _load(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f:
                    self.sessions = json.load(f)
            except:
                self.sessions = {}
        else:
            self.sessions = {}

    # ---------------- Save DB ----------------
    def _save(self):
        try:
            with open(DB_FILE, "w") as f:
                json.dump(self.sessions, f, indent=2)
        except:
            pass

    # ---------------- Create Session ----------------
    def create_session(self, sid):
        with self.lock:
            self.sessions[sid] = {
                "count": 0,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "running": True
            }
            self._save()

    # ---------------- Update Count ----------------
    def update_count(self, sid, count):
        with self.lock:
            if sid in self.sessions:
                self.sessions[sid]["count"] = count
                self._save()

    # ---------------- Stop Session ----------------
    def stop_session(self, sid):
        with self.lock:
            if sid in self.sessions:
                self.sessions[sid]["running"] = False
                self._save()

    # ---------------- Delete Session ----------------
    def delete_session(self, sid):
        with self.lock:
            if sid in self.sessions:
                del self.sessions[sid]
                self._save()

    # ---------------- Getters ----------------
    def get_session(self, sid):
        return self.sessions.get(sid)

    def get_all_sessions(self):
        return self.sessions

    def get_active_sessions(self):
        return {k:v for k,v in self.sessions.items() if v.get("running")}
