from datetime import datetime

class LogBuffer:
    def __init__(self):
        self.logs = []
        self.is_running = False
        self.stop_requested = False
        self.pause_requested = False

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

    def check_control(self):
        if self.stop_requested:
            self.stop_requested = False
            self.pause_requested = False
            raise InterruptedError("Processo interrompido pelo operador.")
        
        if self.pause_requested:
            self.write("⏸️ Processo pausado. Aguardando liberação...")
            import time
            while self.pause_requested:
                time.sleep(0.5)
                if self.stop_requested:
                    self.stop_requested = False
                    self.pause_requested = False
                    raise InterruptedError("Processo interrompido pelo operador.")
            self.write("▶️ Processo retomado.")

log_sys = LogBuffer()

