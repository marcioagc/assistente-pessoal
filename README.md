# Assistente Pessoal

Bot no Telegram que gerencia Gmail e Google Calendar com lembretes inteligentes por tipo de compromisso.

## Funcionalidades

- 📧 **Email** — ler não lidos, buscar, criar rascunhos, enviar
- 📅 **Agenda** — listar, criar e deletar eventos
- 🌅 **Briefing diário** — resumo automático todo dia às 8h
- ⏰ **Lembretes inteligentes via Telegram** baseados no tipo de evento:

| Tipo | Quando avisa |
|------|-------------|
| 🏥 Consulta / Exame / Dentista | 1 dia antes + 1h antes |
| 💼 Entrevista | 1 dia antes + 1h antes |
| ✈️ Voo / Viagem | 1 dia antes + 3h antes + 1h antes |
| 📋 Reunião / Call / Meeting | 30 min antes |
| 🎂 Aniversário / Festa | 3 dias antes + 1 dia antes |
| ⏰ Prazo / Deadline | 1 dia antes + 2h antes |
| 🏋️ Treino / Aula | 1h antes |
| 📅 Outros | 1h antes |

## Stack

- Python 3.12
- [python-telegram-bot](https://python-telegram-bot.org/)
- [Google Gemini API](https://aistudio.google.com/) (gratuita)
- Gmail API + Google Calendar API
- APScheduler

---

## Setup em uma nova máquina

### 1. Pré-requisitos

- Python 3.12+
- Git
- Conta Google (Gmail + Calendar)
- [Chave Gemini gratuita](https://aistudio.google.com/app/apikey)
- Bot do Telegram criado via [@BotFather](https://t.me/BotFather)

### 2. Clonar e instalar

```bash
git clone https://github.com/marcioagc/assistente-pessoal.git
cd assistente-pessoal

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar credenciais

Copie o arquivo de exemplo e preencha:

```bash
cp .env.example .env
```

Edite `.env`:

```
TELEGRAM_BOT_TOKEN=<token do @BotFather>
TELEGRAM_ALLOWED_USER_ID=<seu ID — use @userinfobot>
GEMINI_API_KEY=<chave do aistudio.google.com>
ASSISTANT_NAME=Assistente
BRIEFING_HOUR=8
BRIEFING_MINUTE=0
TIMEZONE=America/Sao_Paulo
```

### 4. Credenciais Google (Gmail + Calendar)

1. Acesse [console.cloud.google.com](https://console.cloud.google.com)
2. Crie um projeto → ative **Gmail API** e **Google Calendar API**
3. Crie credencial **OAuth 2.0 → Aplicativo para computador**
4. Baixe o JSON e salve como `credentials.json` na raiz do projeto
5. Em **Tela de permissão OAuth → Usuários de teste**, adicione seu email

### 5. Autorizar o Google (apenas uma vez)

```bash
python setup_google.py
```

Um navegador abrirá para você fazer login com sua conta Google. Após isso, `token.json` é criado e renovado automaticamente.

### 6. Iniciar o bot

```bash
python main.py
```

Abra o Telegram, encontre seu bot e envie `/start`.

---

## Comandos do bot

| Comando | Descrição |
|---------|-----------|
| `/start` | Inicia o bot |
| `/briefing` | Resumo matinal manual |
| `/limpar` | Limpa histórico da conversa |
| `/ajuda` | Lista de comandos |

Ou simplesmente escreva em linguagem natural:

> *"Quais emails não li hoje?"*
> *"Cria uma reunião amanhã às 14h"*
> *"O que tenho na agenda essa semana?"*
> *"Redige um email para fulano@email.com pedindo desculpas pelo atraso"*

---

## Rodar como serviço (Windows)

```bash
pip install pywin32
# Ou via pm2 (requer Node.js):
npm install -g pm2
pm2 start "python main.py" --name assistente
pm2 startup
pm2 save
```

## Arquivos que NÃO vão para o git (ver .gitignore)

| Arquivo | Conteúdo |
|---------|----------|
| `.env` | Tokens e chaves de API |
| `credentials.json` | OAuth client secret do Google |
| `token.json` | Token de acesso Google (gerado pelo setup) |
| `sent_reminders.json` | Controle de lembretes já enviados |
