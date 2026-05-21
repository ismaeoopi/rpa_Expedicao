from datetime import datetime

class LogBuffer:
    def __init__(self):
        self.logs = []
        self.is_running = False

    def write(self, msg):
        clean_msg = str(msg).strip()
        if clean_msg:
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.logs.append(f"[{timestamp}] {clean_msg}")
            print(f"[{timestamp}] {clean_msg}") # Mantém no terminal do desenvolvedor

    def fetch_new(self):
        to_return = list(self.logs)
        self.logs.clear()
        return to_return

log_sys = LogBuffer()
