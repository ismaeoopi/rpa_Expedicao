import os
import requests
import urllib.parse
from dotenv import load_dotenv, set_key

import sys

# Caminho para o arquivo .env no diretório raiz do projeto ou na pasta do executável
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ENV_PATH = os.path.join(BASE_DIR, ".env")

class SharePointClient:
    def __init__(self, tenant_id=None, client_id=None, client_secret=None, drive_id=None):
        # Carrega variáveis existentes do .env
        load_dotenv(ENV_PATH)
        
        self.tenant_id = tenant_id or os.getenv("SHAREPOINT_TENANT_ID")
        self.client_id = client_id or os.getenv("SHAREPOINT_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("SHAREPOINT_CLIENT_SECRET")
        self.drive_id = drive_id or os.getenv("SHAREPOINT_DRIVE_ID")
        
        self.token = None

    def obter_token(self):
        """Obtém o token de acesso via fluxo Client Credentials."""
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError("Credenciais incompletas (TENANT_ID, CLIENT_ID ou CLIENT_SECRET ausente).")

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials"
        }

        try:
            response = requests.post(url, headers=headers, data=data, timeout=15)
            response.raise_for_status()
            res_data = response.json()
            self.token = res_data.get("access_token")
            return self.token
        except Exception as e:
            raise RuntimeError(f"Erro ao obter token de acesso: {str(e)}")

    def extrair_item_id_ou_caminho(self, input_str):
        """
        Extrai o GUID/Item ID ou limpa o caminho relativo a partir de uma string ou URL do SharePoint.
        """
        if not input_str:
            return "", False
        
        # Remove caracteres de espaço e aspas
        s = str(input_str).strip()
        
        # Se for uma URL do SharePoint contendo sourcedoc
        if "sourcedoc=" in s.lower():
            import re
            match = re.search(r'sourcedoc=%7B([A-F0-9\-]+)%7D', s, re.IGNORECASE) or re.search(r'sourcedoc=\{([A-F0-9\-]+)\}', s, re.IGNORECASE)
            if match:
                return match.group(1), True
                
        # Se for um GUID direto ou entre chaves
        s_clean = s.strip("{}")
        import re
        if re.match(r'^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$', s_clean, re.IGNORECASE):
            return s_clean, True
            
        return s, False

    def obter_controladoria_drive_id(self):
        """Obtém o drive ID do site ControladoriaEstratgica."""
        if not self.token:
            self.obter_token()
        url_site = "https://graph.microsoft.com/v1.0/sites/valgroupco.sharepoint.com:/sites/ControladoriaEstratgica"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            r = requests.get(url_site, headers=headers, timeout=10)
            if r.status_code == 200:
                site_id = r.json().get("id")
                r_drives = requests.get(f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives", headers=headers, timeout=10)
                if r_drives.status_code == 200:
                    drives = r_drives.json().get("value", [])
                    if drives:
                        return drives[0].get("id")
        except Exception:
            pass
        return "b!veMcz6MGokS-D9yfDrj8DS6diuWEWhpDh2SSDeSd-GzsNB81ur5LRr-lNRC3yjtQ"

    def baixar_arquivo(self, caminho_sharepoint, drive_id_custom=None):
        """
        Baixa o conteúdo de um arquivo do SharePoint usando caminho relativo, URL ou Item ID (GUID).
        Retorna o conteúdo binário (bytes) do arquivo.
        """
        if not self.token:
            self.obter_token()

        item_or_path, is_guid = self.extrair_item_id_ou_caminho(caminho_sharepoint)
        target_drives = [drive_id_custom] if drive_id_custom else []
        if self.drive_id and self.drive_id not in target_drives:
            target_drives.append(self.drive_id)
        
        # Inclui o Drive da ControladoriaEstratgica por padrão se for GUID
        controladoria_drive = self.obter_controladoria_drive_id()
        if controladoria_drive and controladoria_drive not in target_drives:
            target_drives.append(controladoria_drive)

        headers = {"Authorization": f"Bearer {self.token}"}

        if is_guid:
            for d_id in target_drives:
                if not d_id:
                    continue
                url = f"https://graph.microsoft.com/v1.0/drives/{d_id}/items/{item_or_path}/content"
                try:
                    response = requests.get(url, headers=headers, timeout=45, allow_redirects=True)
                    if response.status_code == 200:
                        return response.content
                except Exception:
                    continue
            raise RuntimeError(f"Erro ao baixar arquivo por ID '{item_or_path}' no SharePoint.")
        else:
            # Baixa por caminho relativo
            caminho_limpo = item_or_path.replace("\\", "/").strip("/")
            caminho_encoded = urllib.parse.quote(caminho_limpo)
            
            for d_id in target_drives:
                if not d_id:
                    continue
                url = f"https://graph.microsoft.com/v1.0/drives/{d_id}/root:/{caminho_encoded}:/content"
                try:
                    response = requests.get(url, headers=headers, timeout=45, allow_redirects=True)
                    if response.status_code == 200:
                        return response.content
                except Exception:
                    continue
            raise RuntimeError(f"Erro ao baixar arquivo '{caminho_sharepoint}' do SharePoint.")

    def testar_conexao(self, caminhos=None):
        """
        Valida a autenticação e confere se uma lista de caminhos existe e está acessível.
        Retorna um dicionário com o status de cada item.
        """
        resultado = {
            "autenticado": False,
            "drive_acessivel": False,
            "arquivos": {}
        }
        
        try:
            self.obter_token()
            resultado["autenticado"] = True
        except Exception as e:
            resultado["erro_autenticacao"] = str(e)
            return resultado

        # Validar acesso ao Drive
        target_drives = [self.drive_id, self.obter_controladoria_drive_id()]
        headers = {"Authorization": f"Bearer {self.token}"}
        resultado["drive_acessivel"] = True

        # Validar caminhos/IDs dos arquivos se fornecido
        if caminhos:
            for nome_campo, caminho in caminhos.items():
                if not caminho:
                    resultado["arquivos"][nome_campo] = {"status": "nao_configurado"}
                    continue
                
                item_or_path, is_guid = self.extrair_item_id_ou_caminho(caminho)
                achou = False
                
                for d_id in target_drives:
                    if not d_id:
                        continue
                    if is_guid:
                        url_meta = f"https://graph.microsoft.com/v1.0/drives/{d_id}/items/{item_or_path}"
                    else:
                        caminho_limpo = item_or_path.replace("\\", "/").strip("/")
                        caminho_encoded = urllib.parse.quote(caminho_limpo)
                        url_meta = f"https://graph.microsoft.com/v1.0/drives/{d_id}/root:/{caminho_encoded}"
                        
                    try:
                        res_meta = requests.get(url_meta, headers=headers, timeout=10)
                        if res_meta.status_code == 200:
                            resultado["arquivos"][nome_campo] = {"status": "ok", "nome": res_meta.json().get("name")}
                            achou = True
                            break
                    except Exception:
                        pass
                
                if not achou:
                    resultado["arquivos"][nome_campo] = {"status": "erro", "detalhe": "Arquivo não encontrado ou sem permissão"}

        return resultado

def salvar_configuracoes_env(config_dict):
    """
    Grava as chaves passadas no arquivo .env local.
    """
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("# Configurações RPA Expedição\n")
            
    for chave, valor in config_dict.items():
        set_key(ENV_PATH, chave, valor or "")
