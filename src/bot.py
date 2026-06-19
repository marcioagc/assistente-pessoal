import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from . import claude_agent
from . import google_services as gs
from .reminders import classify_event, format_minutes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversas por usuário (em memória — reinicia com o bot)
conversations: dict[int, list] = {}

ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))

# Arquivo para registrar lembretes já enviados (evita duplicatas)
SENT_REMINDERS_FILE = Path(__file__).parent.parent / "sent_reminders.json"


def _load_sent_reminders() -> set:
    if SENT_REMINDERS_FILE.exists():
        return set(json.loads(SENT_REMINDERS_FILE.read_text()))
    return set()


def _save_sent_reminders(sent: set):
    SENT_REMINDERS_FILE.write_text(json.dumps(list(sent)))


def _is_allowed(user_id: int) -> bool:
    return ALLOWED_USER_ID == 0 or user_id == ALLOWED_USER_ID


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("Acesso não autorizado.")
        return
    conversations[user_id] = []
    name = os.getenv("ASSISTANT_NAME", "Assistente")
    await update.message.reply_text(
        f"👋 Olá! Sou seu {name} pessoal.\n\n"
        "Posso ajudar com:\n"
        "📧 *Email* — ler, buscar, redigir e enviar\n"
        "📅 *Agenda* — ver e criar eventos\n"
        "📋 *Briefing diário* — resumo do dia\n\n"
        "É só me falar o que precisa!",
        parse_mode="Markdown",
    )


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        return
    await update.message.reply_text("⏳ Gerando seu briefing do dia...")
    try:
        briefing = claude_agent.generate_daily_briefing()
        await update.message.reply_text(briefing)
    except Exception as e:
        logger.error(f"Erro no briefing: {e}")
        await update.message.reply_text(f"❌ Erro ao gerar briefing: {e}")


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        return
    conversations[user_id] = []
    await update.message.reply_text("🧹 Conversa limpa! Pode começar do zero.")


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Comandos disponíveis:*\n\n"
        "/start — inicia o bot\n"
        "/briefing — resumo matinal do dia\n"
        "/limpar — limpa o histórico da conversa\n"
        "/ajuda — mostra esta mensagem\n\n"
        "Ou simplesmente *escreva o que precisar* — entendo linguagem natural!\n\n"
        "Exemplos:\n"
        "• _Quais emails não li hoje?_\n"
        "• _Cria um evento de reunião amanhã às 14h_\n"
        "• _Redige um email para joão@email.com pedindo desculpas pelo atraso_\n"
        "• _O que tenho na agenda essa semana?_",
        parse_mode="Markdown",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("Acesso não autorizado.")
        return

    if user_id not in conversations:
        conversations[user_id] = []

    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = claude_agent.chat(conversations[user_id], user_text)
        # Telegram tem limite de 4096 chars por mensagem
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")
        await update.message.reply_text(f"❌ Erro interno: {e}")


async def check_reminders(app: Application):
    """Roda a cada minuto. Verifica eventos próximos e envia alertas no Telegram."""
    allowed_id = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    if allowed_id == 0:
        return

    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    now = datetime.now(tz)
    sent = _load_sent_reminders()

    try:
        # Busca eventos das próximas 25h para cobrir lembretes de "1 dia antes"
        events = gs.list_events(days_ahead=2, max_results=30)
    except Exception as e:
        logger.warning(f"Erro ao buscar eventos para lembretes: {e}")
        return

    for event in events:
        start_str = event.get("start", "")
        if not start_str or "T" not in start_str:
            continue  # eventos de dia inteiro — ignorar

        try:
            # Parse do datetime com fuso
            start_dt = datetime.fromisoformat(start_str)
            if start_dt.tzinfo is None:
                start_dt = tz.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(tz)
        except ValueError:
            continue

        rule = classify_event(event.get("summary", ""), event.get("description", ""))

        for minutes in rule.minutes_before:
            fire_time = start_dt - timedelta(minutes=minutes)
            # Janela de 1 minuto para não perder o disparo
            diff = abs((now - fire_time).total_seconds())
            if diff > 60:
                continue

            reminder_key = f"{event['id']}_{minutes}"
            if reminder_key in sent:
                continue

            when_label = format_minutes(minutes)
            start_fmt = start_dt.strftime("%d/%m às %H:%M")
            msg = (
                f"⏰ *Lembrete — {when_label}*\n\n"
                f"{rule.label}\n"
                f"📌 *{event['summary']}*\n"
                f"🕐 {start_fmt}"
            )
            if event.get("location"):
                msg += f"\n📍 {event['location']}"
            if event.get("description"):
                desc = event["description"][:200]
                msg += f"\n📝 {desc}"

            try:
                await app.bot.send_message(chat_id=allowed_id, text=msg, parse_mode="Markdown")
                sent.add(reminder_key)
                logger.info(f"Lembrete enviado: {event['summary']} ({when_label})")
            except Exception as e:
                logger.error(f"Erro ao enviar lembrete: {e}")

    # Limpa entradas antigas (eventos de mais de 2 dias atrás)
    _save_sent_reminders(sent)


async def send_daily_briefing(app: Application):
    allowed_id = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    if allowed_id == 0:
        return
    try:
        briefing = claude_agent.generate_daily_briefing()
        await app.bot.send_message(chat_id=allowed_id, text=f"🌅 *Briefing Matinal*\n\n{briefing}", parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no briefing agendado: {e}")


def run():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN não definido no .env")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(CommandHandler("limpar", cmd_limpar))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Briefing diário agendado
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    hour = int(os.getenv("BRIEFING_HOUR", "8"))
    minute = int(os.getenv("BRIEFING_MINUTE", "0"))

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(
        send_daily_briefing,
        "cron",
        hour=hour,
        minute=minute,
        args=[app],
    )
    # Verifica lembretes a cada minuto
    scheduler.add_job(
        check_reminders,
        "interval",
        minutes=1,
        args=[app],
    )
    scheduler.start()

    logger.info(f"Bot iniciado! Briefing agendado para {hour:02d}:{minute:02d} ({tz.zone})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
