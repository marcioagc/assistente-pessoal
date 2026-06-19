# Configuração do Assistente Pessoal

## Pré-requisitos
- Python 3.11+
- Conta Google (Gmail + Calendar)
- Conta Telegram
- Chave da API Anthropic (Claude)

---

## Passo 1 — Criar o Bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome (ex: *Meu Assistente*) e um username (ex: *meu_assistente_bot*)
4. Copie o **token** que o BotFather enviar

5. Para descobrir seu **User ID**:
   - Procure por **@userinfobot** no Telegram e envie qualquer mensagem
   - Copie o número que aparecer em "Id"

---

## Passo 2 — Criar credenciais Google (Gmail + Calendar)

1. Acesse https://console.cloud.google.com/
2. Crie um projeto novo (ex: *Assistente Pessoal*)
3. No menu lateral: **APIs e serviços → Biblioteca**
   - Ative: **Gmail API**
   - Ative: **Google Calendar API**
4. No menu lateral: **APIs e serviços → Credenciais**
   - Clique em **Criar credenciais → ID do cliente OAuth**
   - Tipo de aplicativo: **App para computador**
   - Baixe o arquivo JSON e salve como `credentials.json` na pasta do projeto
5. Em **Tela de permissão OAuth → Usuários de teste**, adicione seu email Google

---

## Passo 3 — Chave da API Anthropic

1. Acesse https://console.anthropic.com/
2. Crie uma chave em **API Keys**

---

## Passo 4 — Configurar o .env

Copie `.env.example` para `.env` e preencha:

```
TELEGRAM_BOT_TOKEN=<token do BotFather>
TELEGRAM_ALLOWED_USER_ID=<seu User ID>
ANTHROPIC_API_KEY=<sua chave Anthropic>
BRIEFING_HOUR=8
BRIEFING_MINUTE=0
TIMEZONE=America/Sao_Paulo
```

---

## Passo 5 — Instalar dependências e autorizar o Google

```bash
# Criar ambiente virtual
python -m venv venv
venv\Scripts\activate   # Windows

# Instalar dependências
pip install -r requirements.txt

# Autorizar Google (abre o navegador uma vez)
python setup_google.py
```

---

## Passo 6 — Iniciar o bot

```bash
python main.py
```

Pronto! Abra o Telegram, encontre seu bot e envie `/start`.

---

## Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `/start` | Inicia o bot |
| `/briefing` | Resumo matinal (emails + agenda) |
| `/limpar` | Limpa histórico da conversa |
| `/ajuda` | Lista de comandos |

## Exemplos de uso

- *"Quais emails não li?"*
- *"Resuma os emails importantes de hoje"*
- *"Cria uma reunião amanhã às 14h com o título Revisão do projeto"*
- *"O que tenho na agenda essa semana?"*
- *"Redige um email para cliente@empresa.com agradecendo pela reunião de ontem"*
- *"Marca um compromisso médico na sexta às 10h"*

---

## Rodar como serviço (opcional — para manter 24h)

### Windows (via Task Scheduler)
1. Abra o Agendador de Tarefas
2. Crie uma tarefa básica
3. Ação: iniciar `pythonw main.py` na pasta do projeto

### Ou usar pm2 (Node.js)
```bash
npm install -g pm2
pm2 start "python main.py" --name assistente
pm2 startup
pm2 save
```
