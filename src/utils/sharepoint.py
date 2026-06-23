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

    def baixar_arquivo(self, caminho_sharepoint):
        """
        Baixa o conteúdo de um arquivo do SharePoint usando o caminho relativo à raiz.
        Retorna o conteúdo binário (bytes) do arquivo.
        """
        if not self.token:
            self.obter_token()

        if not self.drive_id:
            raise ValueError("DRIVE_ID não configurado.")

        # Converte barras invertidas para barras normais, limpa barras nas pontas e faz URL encode seguro
        caminho_limpo = caminho_sharepoint.replace("\\", "/").strip("/")
        caminho_encoded = urllib.parse.quote(caminho_limpo)
        
        url = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{caminho_encoded}:/content"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            # Segue redirecionamentos automaticamente
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.content
        except Exception as e:
            raise RuntimeError(f"Erro ao baixar arquivo '{caminho_sharepoint}' do SharePoint: {str(e)}")

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
        url_drive = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res_drive = requests.get(url_drive, headers=headers, timeout=10)
            if res_drive.status_code == 200:
                resultado["drive_acessivel"] = True
            else:
                resultado["erro_drive"] = f"Código {res_drive.status_code}: {res_drive.text}"
                return resultado
        except Exception as e:
            resultado["erro_drive"] = str(e)
            return resultado

        # Validar caminhos dos arquivos se fornecido
        if caminhos:
            for nome_campo, caminho in caminhos.items():
                if not caminho:
                    resultado["arquivos"][nome_campo] = {"status": "nao_configurado"}
                    continue
                
                caminho_limpo = caminho.replace("\\", "/").strip("/")
                caminho_encoded = urllib.parse.quote(caminho_limpo)
                url_meta = f"https://graph.microsoft.com/v1.0/drives/{self.drive_id}/root:/{caminho_encoded}"
                
                try:
                    res_meta = requests.get(url_meta, headers=headers, timeout=10)
                    if res_meta.status_code == 200:
                        resultado["arquivos"][nome_campo] = {"status": "ok", "nome": res_meta.json().get("name")}
                    else:
                        resultado["arquivos"][nome_campo] = {"status": "erro", "detalhe": f"Status {res_meta.status_code}"}
                except Exception as e:
                    resultado["arquivos"][nome_campo] = {"status": "erro", "detalhe": str(e)}

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
