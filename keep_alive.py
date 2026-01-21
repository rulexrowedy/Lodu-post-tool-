import time
import threading
import gc
import os
import psutil

class KeepAlive:
    def __init__(self):
        self.running = True
        self.last_activity = time.time()
        
    def get_memory_mb(self):
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0
    
    def cleanup(self):
        gc.collect()
        
    def heartbeat(self):
        self.last_activity = time.time()
        
    def monitor_loop(self):
        while self.running:
            try:
                mem = self.get_memory_mb()
                
                if mem > 350:
                    self.cleanup()
                
                self.heartbeat()
                
                time.sleep(30)
            except:
                time.sleep(30)
    
    def start(self):
        thread = threading.Thread(target=self.monitor_loop, daemon=True)
        thread.start()
        return thread
    
    def stop(self):
        self.running = False

_keeper = None

def get_keeper():
    global _keeper
    if _keeper is None:
        _keeper = KeepAlive()
        _keeper.start()
    return _keeper

def ping():
    keeper = get_keeper()
    keeper.heartbeat()
    return True

def get_status():
    keeper = get_keeper()
    return {
        'memory_mb': keeper.get_memory_mb(),
        'uptime': time.time() - keeper.last_activity,
        'running': keeper.running
    }
