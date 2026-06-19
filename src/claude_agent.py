import os
import json
import re
from datetime import datetime
import pytz
import google.generativeai as genai
from . import google_services as gs
from .reminders import classify_event, reminder_summary

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def _execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "listar_emails_nao_lidos":
            return json.dumps(gs.list_unread_emails(inputs.get("quantidade", 10)), ensure_ascii=False)
        elif name == "ler_email":
            return json.dumps(gs.get_email_body(inputs["id"]), ensure_ascii=False)
        elif name == "buscar_emails":
            return json.dumps(gs.search_emails(inputs["query"], inputs.get("quantidade", 5)), ensure_ascii=False)
        elif name == "criar_rascunho":
            draft_id = gs.create_draft(inputs["para"], inputs["assunto"], inputs["corpo"])
            return f"Rascunho criado. ID: {draft_id}"
        elif name == "enviar_email":
            gs.send_email(inputs["para"], inputs["assunto"], inputs["corpo"])
            return "Email enviado com sucesso."
        elif name == "listar_eventos":
            return json.dumps(gs.list_events(inputs.get("dias", 7), inputs.get("quantidade", 20)), ensure_ascii=False)
        elif name == "criar_evento":
            rule = classify_event(inputs["titulo"], inputs.get("descricao", ""))
            link, _ = gs.create_event(
                inputs["titulo"], inputs["inicio"], inputs["fim"],
                inputs.get("descricao", ""), inputs.get("local", ""),
                reminder_minutes=rule.minutes_before,
            )
            return f"Evento criado: {link}\n⏰ Lembretes: {reminder_summary(rule)}"
        elif name == "deletar_evento":
            gs.delete_event(inputs["id"])
            return "Evento removido."
        else:
            return f"Ferramenta desconhecida: {name}"
    except Exception as e:
        return f"Erro em {name}: {str(e)}"


def _system_prompt():
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    now = datetime.now(tz).strftime("%A, %d/%m/%Y %H:%M")
    return f"""Você é um assistente pessoal inteligente que gerencia Gmail e Google Calendar.
Data/hora atual: {now} (fuso: America/Sao_Paulo)
Responda SEMPRE em português brasileiro.

Você tem acesso às seguintes ferramentas. Quando precisar usá-las, responda SOMENTE com um bloco JSON no formato abaixo (sem texto antes ou depois):

{{"tool": "nome_da_ferramenta", "args": {{...}}}}

Ferramentas disponíveis:

- listar_emails_nao_lidos: lista emails não lidos
  args: {{"quantidade": 10}}

- ler_email: lê um email completo pelo ID
  args: {{"id": "id_do_email"}}

- buscar_emails: busca emails por query Gmail
  args: {{"query": "from:alguem@email.com", "quantidade": 5}}

- criar_rascunho: cria rascunho no Gmail (NÃO envia)
  args: {{"para": "email", "assunto": "texto", "corpo": "texto"}}

- enviar_email: envia email (só com confirmação explícita do usuário)
  args: {{"para": "email", "assunto": "texto", "corpo": "texto"}}

- listar_eventos: lista próximos eventos do Calendar
  args: {{"dias": 7, "quantidade": 20}}

- criar_evento: cria evento com lembretes automáticos por tipo
  args: {{"titulo": "texto", "inicio": "2024-06-20T14:00:00", "fim": "2024-06-20T15:00:00", "descricao": "", "local": ""}}

- deletar_evento: remove evento pelo ID
  args: {{"id": "id_do_evento"}}

Regras:
- Para listar emails ou eventos, SEMPRE chame a ferramenta correspondente — nunca invente dados
- Para enviar email, peça confirmação antes; para rascunho, pode criar direto
- Use emojis: 📧 email, 📅 agenda, ✅ concluído, ⚠️ atenção
- Datas relativas ("amanhã", "semana que vem") calcule a partir da data atual acima
- Quando receber resultado de ferramenta, responda de forma clara e organizada em texto normal"""


def _extract_tool_call(text: str):
    """Extrai chamada de ferramenta do texto do modelo, se houver."""
    text = text.strip()
    # Tenta encontrar JSON puro
    match = re.search(r'\{[^{}]*"tool"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            if "tool" in data and "args" in data:
                return data["tool"], data["args"]
        except json.JSONDecodeError:
            pass
    return None, None


def chat(conversation_history: list, user_message: str) -> str:
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_system_prompt(),
    )

    # Reconstrói histórico no formato Gemini
    history = []
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [{"text": msg["content"]}]})

    chat_session = model.start_chat(history=history)
    response = chat_session.send_message(user_message)
    reply_text = response.text

    # Loop de tool calling (até 5 rodadas)
    for _ in range(5):
        tool_name, tool_args = _extract_tool_call(reply_text)
        if not tool_name:
            break

        tool_result = _execute_tool(tool_name, tool_args)

        # Devolve resultado ao modelo
        follow_up = f"[Resultado da ferramenta {tool_name}]:\n{tool_result}"
        response = chat_session.send_message(follow_up)
        reply_text = response.text

    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": reply_text})
    return reply_text


def generate_daily_briefing() -> str:
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    today = datetime.now(tz).strftime("%A, %d/%m/%Y")

    try:
        emails = gs.list_unread_emails(max_results=15)
        events = gs.list_events(days_ahead=1, max_results=10)
    except Exception as e:
        return f"❌ Erro ao buscar dados para o briefing: {e}"

    prompt = (
        f"Gere um briefing matinal para hoje ({today}).\n\n"
        f"Emails não lidos ({len(emails)}):\n"
        f"{json.dumps(emails, ensure_ascii=False, indent=2)}\n\n"
        f"Eventos de hoje:\n"
        f"{json.dumps(events, ensure_ascii=False, indent=2)}\n\n"
        "O briefing deve ter:\n"
        "1. Saudação com dia e data\n"
        "2. Resumo dos emails mais importantes\n"
        "3. Agenda do dia com horários\n"
        "4. Itens urgentes\n"
        "5. Mensagem motivacional curta\n\n"
        "Use emojis para organizar visualmente. Seja conciso mas completo."
    )

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_system_prompt(),
    )
    response = model.generate_content(prompt)
    return response.text
