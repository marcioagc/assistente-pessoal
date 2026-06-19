import os
import json
from datetime import datetime
import pytz
import google.generativeai as genai
from . import google_services as gs
from .reminders import classify_event, reminder_summary

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

TOOLS_DECLARATION = [
    {
        "name": "listar_emails_nao_lidos",
        "description": "Lista os emails não lidos da caixa de entrada do usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "quantidade": {"type": "integer", "description": "Número máximo de emails a retornar (padrão: 10)"}
            },
        },
    },
    {
        "name": "ler_email",
        "description": "Lê o conteúdo completo de um email específico pelo seu ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "ID do email"}
            },
            "required": ["id"],
        },
    },
    {
        "name": "buscar_emails",
        "description": "Busca emails por palavra-chave, remetente, assunto, data etc.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca Gmail (ex: 'from:joao@email.com', 'subject:reunião')"},
                "quantidade": {"type": "integer", "description": "Número máximo de resultados (padrão: 5)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "criar_rascunho",
        "description": "Cria um rascunho de email no Gmail.",
        "parameters": {
            "type": "object",
            "properties": {
                "para": {"type": "string", "description": "Endereço de email do destinatário"},
                "assunto": {"type": "string", "description": "Assunto do email"},
                "corpo": {"type": "string", "description": "Corpo do email"},
            },
            "required": ["para", "assunto", "corpo"],
        },
    },
    {
        "name": "enviar_email",
        "description": "Envia um email. Use somente quando o usuário confirmar explicitamente.",
        "parameters": {
            "type": "object",
            "properties": {
                "para": {"type": "string", "description": "Endereço de email do destinatário"},
                "assunto": {"type": "string", "description": "Assunto do email"},
                "corpo": {"type": "string", "description": "Corpo do email"},
            },
            "required": ["para", "assunto", "corpo"],
        },
    },
    {
        "name": "listar_eventos",
        "description": "Lista os próximos eventos do Google Calendar.",
        "parameters": {
            "type": "object",
            "properties": {
                "dias": {"type": "integer", "description": "Quantos dias à frente verificar (padrão: 7)"},
                "quantidade": {"type": "integer", "description": "Número máximo de eventos (padrão: 20)"},
            },
        },
    },
    {
        "name": "criar_evento",
        "description": "Cria um novo evento no Google Calendar com lembretes automáticos.",
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título do evento"},
                "inicio": {"type": "string", "description": "Data/hora de início ISO 8601 (ex: 2024-06-20T14:00:00)"},
                "fim": {"type": "string", "description": "Data/hora de fim ISO 8601"},
                "descricao": {"type": "string", "description": "Descrição ou notas do evento"},
                "local": {"type": "string", "description": "Local do evento"},
            },
            "required": ["titulo", "inicio", "fim"],
        },
    },
    {
        "name": "deletar_evento",
        "description": "Remove um evento do Google Calendar pelo ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "ID do evento"}
            },
            "required": ["id"],
        },
    },
]


def _execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "listar_emails_nao_lidos":
            emails = gs.list_unread_emails(inputs.get("quantidade", 10))
            return json.dumps(emails, ensure_ascii=False)
        elif name == "ler_email":
            return json.dumps(gs.get_email_body(inputs["id"]), ensure_ascii=False)
        elif name == "buscar_emails":
            emails = gs.search_emails(inputs["query"], inputs.get("quantidade", 5))
            return json.dumps(emails, ensure_ascii=False)
        elif name == "criar_rascunho":
            draft_id = gs.create_draft(inputs["para"], inputs["assunto"], inputs["corpo"])
            return f"Rascunho criado. ID: {draft_id}"
        elif name == "enviar_email":
            gs.send_email(inputs["para"], inputs["assunto"], inputs["corpo"])
            return "Email enviado com sucesso."
        elif name == "listar_eventos":
            events = gs.list_events(inputs.get("dias", 7), inputs.get("quantidade", 20))
            return json.dumps(events, ensure_ascii=False)
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
    return (
        f"Você é um assistente pessoal inteligente e proativo.\n"
        f"Data/hora atual: {now} (fuso: {tz.zone})\n\n"
        "Você gerencia email (Gmail) e agenda (Google Calendar) do usuário.\n"
        "Responda sempre em português brasileiro, de forma clara e objetiva.\n\n"
        "Diretrizes:\n"
        "- Apresente listas de emails/eventos de forma organizada e legível\n"
        "- Para ENVIAR emails, sempre peça confirmação antes. Pode criar rascunhos sem confirmar.\n"
        "- Ao criar eventos, confirme detalhes ambíguos com o usuário\n"
        "- Para datas relativas ('amanhã', 'semana que vem'), calcule com base na data atual\n"
        "- Use emojis para organizar: 📧 email, 📅 agenda, ✅ concluído, ⚠️ atenção"
    )


def _get_model():
    return genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=_system_prompt(),
        tools=TOOLS_DECLARATION,
    )


def chat(conversation_history: list, user_message: str) -> str:
    model = _get_model()

    # Reconstrói o histórico no formato Gemini
    history = []
    for msg in conversation_history:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [msg["content"]]})

    chat_session = model.start_chat(history=history)
    response = chat_session.send_message(user_message)

    # Processa chamadas de ferramenta
    max_rounds = 5
    for _ in range(max_rounds):
        fn_calls = [p for p in response.parts if hasattr(p, "function_call") and p.function_call.name]
        if not fn_calls:
            break

        tool_responses = []
        for part in fn_calls:
            fc = part.function_call
            args = dict(fc.args)
            result = _execute_tool(fc.name, args)
            tool_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        response = chat_session.send_message(tool_responses)

    text = "".join(p.text for p in response.parts if hasattr(p, "text"))

    # Atualiza histórico
    conversation_history.append({"role": "user", "content": user_message})
    conversation_history.append({"role": "assistant", "content": text})

    return text


def generate_daily_briefing() -> str:
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    today = datetime.now(tz).strftime("%A, %d/%m/%Y")

    emails = gs.list_unread_emails(max_results=15)
    events = gs.list_events(days_ahead=1, max_results=10)

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
        model_name="gemini-1.5-flash",
        system_instruction=_system_prompt(),
    )
    response = model.generate_content(prompt)
    return response.text
