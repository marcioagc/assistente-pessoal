"""
Sistema de lembretes inteligentes baseados no tipo de compromisso.

Categorias e regras:
  consulta / médico / exame / dentista    → 1 dia antes + 1h antes
  entrevista / processo seletivo          → 1 dia antes + 1h antes
  reunião / meeting / call / sync         → 30 min antes
  voo / viagem / embarque                 → 1 dia antes + 3h antes + 1h antes
  aniversário / birthday                  → 3 dias antes + no dia (manhã)
  prazo / deadline / entrega              → 1 dia antes + 2h antes
  academia / treino / aula                → 1h antes
  outros                                  → 1h antes (padrão seguro)
"""

import re
from dataclasses import dataclass

@dataclass
class ReminderRule:
    label: str           # nome exibido ao usuário
    minutes_before: list[int]  # quantos minutos antes disparar cada lembrete

# Regras por categoria (ordem importa: primeiro match vence)
RULES: list[tuple[list[str], ReminderRule]] = [
    (
        ["consulta", "médico", "medico", "medica", "médica", "clínica", "clinica",
         "exame", "dentist", "hospital", "ubs", "psicolog", "terapia", "vacina"],
        ReminderRule("🏥 Consulta médica", [60 * 24, 60]),        # 1 dia + 1h
    ),
    (
        ["entrevista", "processo seletivo", "seleção", "selecao", "entrevista de emprego"],
        ReminderRule("💼 Entrevista", [60 * 24, 60]),              # 1 dia + 1h
    ),
    (
        ["voo", "viagem", "embarque", "aeroporto", "check-in", "checkin", "partida"],
        ReminderRule("✈️ Viagem/Voo", [60 * 24, 60 * 3, 60]),     # 1 dia + 3h + 1h
    ),
    (
        ["aniversário", "aniversario", "birthday", "festa", "comemoração", "comemoracao"],
        ReminderRule("🎂 Aniversário", [60 * 24 * 3, 60 * 24]),   # 3 dias + 1 dia
    ),
    (
        ["prazo", "deadline", "entrega", "vencimento", "vence", "data limite"],
        ReminderRule("⏰ Prazo/Deadline", [60 * 24, 60 * 2]),     # 1 dia + 2h
    ),
    (
        ["reunião", "reuniao", "meeting", "call", "sync", "standup", "stand-up",
         "apresentação", "apresentacao", "webinar", "conferência", "conferencia"],
        ReminderRule("📋 Reunião", [30]),                           # 30 min
    ),
    (
        ["academia", "treino", "aula", "yoga", "pilates", "corrida", "natação", "natacao",
         "ginástica", "ginastica", "crossfit", "musculação", "musculacao"],
        ReminderRule("🏋️ Treino/Aula", [60]),                     # 1h antes
    ),
    (
        ["almoço", "almoco", "jantar", "lanche", "café", "cafe", "refeição", "refeicao"],
        ReminderRule("🍽️ Refeição/Encontro", [30]),               # 30 min
    ),
]

DEFAULT_RULE = ReminderRule("📅 Compromisso", [60])  # padrão: 1h antes


def classify_event(title: str, description: str = "") -> ReminderRule:
    text = (title + " " + description).lower()
    for keywords, rule in RULES:
        if any(kw in text for kw in keywords):
            return rule
    return DEFAULT_RULE


def format_minutes(minutes: int) -> str:
    if minutes >= 60 * 24:
        days = minutes // (60 * 24)
        return f"{days} dia{'s' if days > 1 else ''} antes"
    if minutes >= 60:
        hours = minutes // 60
        return f"{hours}h antes"
    return f"{minutes} min antes"


def reminder_summary(rule: ReminderRule) -> str:
    times = " + ".join(format_minutes(m) for m in sorted(rule.minutes_before, reverse=True))
    return f"{rule.label} → {times}"
