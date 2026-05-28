import sys
from datetime import datetime

# Guarda o stdout original
original_stdout = sys.stdout

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
            log_line = f"[{timestamp}] {clean_msg}"
            self.logs.append(log_line)
            # Escreve no stdout original de forma segura
            try:
                if original_stdout and hasattr(original_stdout, 'write') and not isinstance(original_stdout, str):
                    original_stdout.write(log_line + "\n")
                    original_stdout.flush()
                else:
                    sys.__stdout__.write(log_line + "\n")
                    sys.__stdout__.flush()
            except Exception:
                try:
                    sys.__stdout__.write(log_line + "\n")
                    sys.__stdout__.flush()
                except:
                    pass

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

class StdoutRedirector:
    def __init__(self, log_buffer, orig_stdout):
        self.log_buffer = log_buffer
        self.original_stdout = orig_stdout if (orig_stdout and hasattr(orig_stdout, 'write') and not isinstance(orig_stdout, str)) else sys.__stdout__
        self._line_buffer = ""

    def write(self, string):
        # 1. Escreve no stdout original para o terminal (defensivo contra encode/unicode e debugpy wrappers)
        try:
            self.original_stdout.write(string)
            self.original_stdout.flush()
        except UnicodeEncodeError:
            try:
                encoding = getattr(self.original_stdout, 'encoding', 'utf-8') or 'utf-8'
                safe_string = string.encode(encoding, errors='replace').decode(encoding)
                self.original_stdout.write(safe_string)
                self.original_stdout.flush()
            except:
                pass
        except Exception:
            try:
                sys.__stdout__.write(string)
                sys.__stdout__.flush()
            except:
                pass

        # 2. Acumula no buffer para processar linhas completas ou carriage return (\r)
        self._line_buffer += string
        
        while True:
            # Encontra quebras de linha ou de retorno de carro
            idx_lf = self._line_buffer.find('\n')
            idx_cr = self._line_buffer.find('\r', 1) # Procura a partir de 1 para evitar travar no \r inicial
            
            # Se o buffer tem tamanho 1 e começa com \r, aguarda mais dados
            if self._line_buffer.startswith('\r') and len(self._line_buffer) == 1:
                break
                
            if idx_lf == -1 and idx_cr == -1:
                break
                
            if idx_lf != -1 and (idx_cr == -1 or idx_lf < idx_cr):
                line = self._line_buffer[:idx_lf]
                self._line_buffer = self._line_buffer[idx_lf+1:]
                self._process_line(line)
            else:
                line = self._line_buffer[:idx_cr]
                self._line_buffer = self._line_buffer[idx_cr:] # Mantém o \r para o início do próximo comando
                self._process_line(line)

    def _process_line(self, line):
        is_overwrite = line.startswith('\r')
        clean = line.replace('\r', '').strip()
        if clean:
            prefix = "\r" if is_overwrite else ""
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_buffer.logs.append(f"{prefix}[{timestamp}] {clean}")

    def flush(self):
        try:
            self.original_stdout.flush()
        except:
            pass

sys.stdout = StdoutRedirector(log_sys, original_stdout)



