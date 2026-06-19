import os
import json
import logging
import tempfile
from datetime import datetime, timedelta
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

conversations: dict[int, list] = {}
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
SENT_REMINDERS_FILE = Path(__file__).parent.parent / "sent_reminders.json"


def _load_sent_reminders() -> set:
    if SENT_REMINDERS_FILE.exists():
        return set(json.loads(SENT_REMINDERS_FILE.read_text()))
    return set()


def _save_sent_reminders(sent: set):
    SENT_REMINDERS_FILE.write_text(json.dumps(list(sent)))


def _is_allowed(user_id: int) -> bool:
    return ALLOWED_USER_ID == 0 or user_id == ALLOWED_USER_ID


async def _transcribe_voice(file_path: str) -> str:
    """Transcreve áudio usando Gemini."""
    import google.generativeai as genai
    model = genai.GenerativeModel("gemini-1.5-flash")
    with open(file_path, "rb") as f:
        audio_data = f.read()
    response = model.generate_content([
        "Transcreva exatamente o que está sendo dito neste áudio em português. Retorne apenas a transcrição, sem comentários.",
        {"mime_type": "audio/ogg", "data": audio_data},
    ])
    return response.text.strip()


async def _process_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, user_text: str):
    """Processa texto (digitado ou transcrito) e responde."""
    user_id = update.effective_user.id
    if user_id not in conversations:
        conversations[user_id] = []

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = claude_agent.chat(conversations[user_id], user_text)
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000])
        else:
            await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro interno: {e}")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("Acesso não autorizado.")
        return
    conversations[update.effective_user.id] = []
    name = os.getenv("ASSISTANT_NAME", "Assistente")
    await update.message.reply_text(
        f"👋 Olá! Sou seu {name} pessoal.\n\n"
        "Posso ajudar com:\n"
        "📧 *Email* — ler, buscar, redigir e enviar\n"
        "📅 *Agenda* — ver e criar eventos\n"
        "📋 *Briefing diário* — resumo do dia\n"
        "🎙️ *Voz* — pode me mandar áudio também!\n\n"
        "É só me falar o que precisa!",
        parse_mode="Markdown",
    )


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return
    await update.message.reply_text("⏳ Gerando seu briefing do dia...")
    try:
        briefing = claude_agent.generate_daily_briefing()
        await update.message.reply_text(briefing)
    except Exception as e:
        logger.error(f"Erro no briefing: {e}")
        await update.message.reply_text(f"❌ Erro ao gerar briefing: {e}")


async def cmd_limpar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        return
    conversations[update.effective_user.id] = []
    await update.message.reply_text("🧹 Conversa limpa! Pode começar do zero.")


async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Comandos disponíveis:*\n\n"
        "/start — inicia o bot\n"
        "/briefing — resumo matinal do dia\n"
        "/limpar — limpa o histórico da conversa\n"
        "/ajuda — mostra esta mensagem\n\n"
        "Ou fale o que precisar — *texto ou áudio*!\n\n"
        "Exemplos:\n"
        "• _Quais emails não li hoje?_\n"
        "• _Cria reunião amanhã às 14h_\n"
        "• _O que tenho na agenda essa semana?_\n"
        "• _Redige um email para fulano pedindo desculpas_",
        parse_mode="Markdown",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("Acesso não autorizado.")
        return
    await _process_and_reply(update, context, update.message.text)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe áudio/voz, transcreve e processa como texto."""
    if not _is_allowed(update.effective_user.id):
        await update.message.reply_text("Acesso não autorizado.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Suporte a voice note e audio file
    audio = update.message.voice or update.message.audio
    if not audio:
        return

    try:
        # Baixa o arquivo de áudio
        tg_file = await context.bot.get_file(audio.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        await tg_file.download_to_drive(tmp_path)

        # Transcreve
        await update.message.reply_text("🎙️ Transcrevendo áudio...")
        transcribed = await _transcribe_voice(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)

        if not transcribed:
            await update.message.reply_text("❌ Não consegui entender o áudio. Tente novamente.")
            return

        # Confirma a transcrição e processa
        await update.message.reply_text(f"📝 _{transcribed}_", parse_mode="Markdown")
        await _process_and_reply(update, context, transcribed)

    except Exception as e:
        logger.error(f"Erro ao processar voz: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao processar áudio: {e}")


async def check_reminders(app: Application):
    allowed_id = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    if allowed_id == 0:
        return

    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    now = datetime.now(tz)
    sent = _load_sent_reminders()

    try:
        events = gs.list_events(days_ahead=2, max_results=30)
    except Exception as e:
        logger.warning(f"Erro ao buscar eventos para lembretes: {e}")
        return

    for event in events:
        start_str = event.get("start", "")
        if not start_str or "T" not in start_str:
            continue

        try:
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
            if abs((now - fire_time).total_seconds()) > 60:
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
                msg += f"\n📝 {event['description'][:200]}"

            try:
                await app.bot.send_message(chat_id=allowed_id, text=msg, parse_mode="Markdown")
                sent.add(reminder_key)
                logger.info(f"Lembrete enviado: {event['summary']} ({when_label})")
            except Exception as e:
                logger.error(f"Erro ao enviar lembrete: {e}")

    _save_sent_reminders(sent)


async def send_daily_briefing(app: Application):
    allowed_id = int(os.getenv("TELEGRAM_ALLOWED_USER_ID", "0"))
    if allowed_id == 0:
        return
    try:
        briefing = claude_agent.generate_daily_briefing()
        await app.bot.send_message(
            chat_id=allowed_id,
            text=f"🌅 *Briefing Matinal*\n\n{briefing}",
            parse_mode="Markdown",
        )
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    hour = int(os.getenv("BRIEFING_HOUR", "8"))
    minute = int(os.getenv("BRIEFING_MINUTE", "0"))

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(send_daily_briefing, "cron", hour=hour, minute=minute, args=[app])
    scheduler.add_job(check_reminders, "interval", minutes=1, args=[app])
    scheduler.start()

    logger.info(f"Bot iniciado! Briefing às {hour:02d}:{minute:02d} ({tz.zone})")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
