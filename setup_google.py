"""
Execute este script UMA VEZ para autorizar o acesso ao Gmail e Google Calendar.
Ele abrirá o navegador para você fazer login com sua conta Google.
"""
from dotenv import load_dotenv
load_dotenv()

from src.google_services import get_credentials

if __name__ == "__main__":
    print("Iniciando autorização do Google...")
    creds = get_credentials()
    print("✅ Autorização concluída! O arquivo token.json foi criado.")
    print("   Você não precisará fazer isso novamente (o token renova automaticamente).")
