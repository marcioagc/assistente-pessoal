import os
import json
import urllib.parse
import urllib.request
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from datetime import datetime, timedelta
import pytz

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly",
]

TOKEN_FILE = Path(__file__).parent.parent / "token.json"
CREDENTIALS_FILE = Path(__file__).parent.parent / "credentials.json"


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())


def get_calendar_service():
    return build("calendar", "v3", credentials=get_credentials())


# ── Gmail ──────────────────────────────────────────────────────────────────────

def list_unread_emails(max_results=10):
    service = get_gmail_service()
    result = service.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
    ).execute()
    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        snippet = detail.get("snippet", "")
        emails.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": snippet,
        })
    return emails


def get_email_body(message_id):
    service = get_gmail_service()
    detail = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
    body = _extract_body(detail["payload"])
    return {
        "from": headers.get("From", ""),
        "subject": headers.get("Subject", ""),
        "date": headers.get("Date", ""),
        "body": body,
    }


def _extract_body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload["parts"]:
            result = _extract_body(part)
            if result:
                return result
    else:
        data = payload["body"].get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def create_draft(to: str, subject: str, body: str):
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return draft["id"]


def send_email(to: str, subject: str, body: str):
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()


def mark_as_read(message_id: str):
    service = get_gmail_service()
    service.users().messages().modify(
        userId="me", id=message_id,
        body={"removeLabelIds": ["UNREAD"]}
    ).execute()


def search_emails(query: str, max_results=5):
    service = get_gmail_service()
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        emails.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": detail.get("snippet", ""),
        })
    return emails


# ── Calendar ───────────────────────────────────────────────────────────────────

def list_events(days_ahead=7, max_results=20):
    service = get_calendar_service()
    tz = pytz.timezone(os.getenv("TIMEZONE", "America/Sao_Paulo"))
    now = datetime.now(tz)
    time_max = now + timedelta(days=days_ahead)
    result = service.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=time_max.isoformat(),
        maxResults=max_results,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = []
    for e in result.get("items", []):
        start = e["start"].get("dateTime", e["start"].get("date", ""))
        end = e["end"].get("dateTime", e["end"].get("date", ""))
        events.append({
            "id": e["id"],
            "summary": e.get("summary", "Sem título"),
            "start": start,
            "end": end,
            "location": e.get("location", ""),
            "description": e.get("description", ""),
        })
    return events


def create_event(summary: str, start_dt: str, end_dt: str, description: str = "", location: str = "",
                 reminder_minutes: list[int] | None = None):
    service = get_calendar_service()
    tz = os.getenv("TIMEZONE", "America/Sao_Paulo")

    # Lembretes via notificação popup (substitui o padrão do Google Calendar)
    if reminder_minutes:
        reminders = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": m} for m in reminder_minutes],
        }
    else:
        reminders = {"useDefault": True}

    # Adiciona bloco de Maps na descrição quando há local
    if location:
        maps_block = build_location_description(location)
        description = f"{description}\n\n{maps_block}".strip() if description else maps_block

    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {"dateTime": start_dt, "timeZone": tz},
        "end": {"dateTime": end_dt, "timeZone": tz},
        "reminders": reminders,
    }
    created = service.events().insert(calendarId="primary", body=event).execute()
    return created.get("htmlLink", ""), created.get("id", "")


def delete_event(event_id: str):
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()


# ── Labels & Filtros ───────────────────────────────────────────────────────────

LABEL_MAP: dict[str, str] = {}  # cache nome→id


def _get_label_map() -> dict[str, str]:
    global LABEL_MAP
    if not LABEL_MAP:
        service = get_gmail_service()
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        LABEL_MAP = {l["name"]: l["id"] for l in labels}
    return LABEL_MAP


def list_labels() -> list[dict]:
    service = get_gmail_service()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    return [{"id": l["id"], "name": l["name"], "type": l["type"]} for l in labels]


def create_label(name: str) -> str:
    service = get_gmail_service()
    label = service.users().labels().create(userId="me", body={"name": name}).execute()
    LABEL_MAP[name] = label["id"]
    return label["id"]


def get_label_id(name: str) -> str | None:
    lmap = _get_label_map()
    # Busca exata primeiro, depois case-insensitive
    if name in lmap:
        return lmap[name]
    name_lower = name.lower()
    for k, v in lmap.items():
        if k.lower() == name_lower:
            return v
    return None


def list_filters() -> list[dict]:
    service = get_gmail_service()
    result = service.users().settings().filters().list(userId="me").execute()
    filters = result.get("filter", [])
    lmap = {v: k for k, v in _get_label_map().items()}  # id→nome
    out = []
    for f in filters:
        criteria = f.get("criteria", {})
        action = f.get("action", {})
        add_labels = [lmap.get(lid, lid) for lid in action.get("addLabelIds", [])]
        remove_inbox = "INBOX" in action.get("removeLabelIds", [])
        out.append({
            "id": f["id"],
            "de": criteria.get("from", ""),
            "para": criteria.get("to", ""),
            "assunto": criteria.get("subject", ""),
            "query": criteria.get("query", ""),
            "labels": add_labels,
            "remove_inbox": remove_inbox,
        })
    return out


def create_filter(label_name: str, from_: str = "", to_: str = "",
                  subject: str = "", query: str = "") -> str:
    """Cria filtro Gmail que aplica label e remove da caixa de entrada."""
    service = get_gmail_service()

    # Resolve ou cria o label
    label_id = get_label_id(label_name)
    if not label_id:
        label_id = create_label(label_name)

    criteria: dict = {}
    if from_:
        criteria["from"] = from_
    if to_:
        criteria["to"] = to_
    if subject:
        criteria["subject"] = subject
    if query:
        criteria["query"] = query

    if not criteria:
        raise ValueError("Pelo menos um critério de filtro é obrigatório (de, para, assunto ou query).")

    body = {
        "criteria": criteria,
        "action": {
            "addLabelIds": [label_id],
            "removeLabelIds": ["INBOX"],
        },
    }
    result = service.users().settings().filters().create(userId="me", body=body).execute()
    return result["id"]


def delete_filter(filter_id: str):
    service = get_gmail_service()
    service.users().settings().filters().delete(userId="me", id=filter_id).execute()


def apply_label_to_message(message_id: str, label_name: str, remove_inbox: bool = True):
    """Aplica label manualmente a um email existente."""
    service = get_gmail_service()
    label_id = get_label_id(label_name)
    if not label_id:
        label_id = create_label(label_name)
    body: dict = {"addLabelIds": [label_id]}
    if remove_inbox:
        body["removeLabelIds"] = ["INBOX"]
    service.users().messages().modify(userId="me", id=message_id, body=body).execute()


# ── Contatos ───────────────────────────────────────────────────────────────────

def get_people_service():
    return build("people", "v1", credentials=get_credentials())


def search_contacts(name: str, max_results=5) -> list[dict]:
    service = get_people_service()
    result = service.people().searchContacts(
        query=name,
        readMask="names,emailAddresses,phoneNumbers",
        pageSize=max_results,
    ).execute()
    contacts = []
    for r in result.get("results", []):
        person = r.get("person", {})
        names = person.get("names", [{}])
        emails = person.get("emailAddresses", [])
        phones = person.get("phoneNumbers", [])
        contacts.append({
            "nome": names[0].get("displayName", "") if names else "",
            "emails": [e["value"] for e in emails],
            "telefones": [p["value"] for p in phones],
        })
    return contacts


# ── Maps / Directions ──────────────────────────────────────────────────────────

def maps_link(location: str) -> str:
    """Retorna link do Google Maps para o endereço."""
    encoded = urllib.parse.quote(location)
    return f"https://www.google.com/maps/search/?api=1&query={encoded}"


def directions_link(destination: str, origin: str = "") -> str:
    """Retorna link de rota no Google Maps."""
    dest_enc = urllib.parse.quote(destination)
    if origin:
        orig_enc = urllib.parse.quote(origin)
        return f"https://www.google.com/maps/dir/?api=1&origin={orig_enc}&destination={dest_enc}"
    return f"https://www.google.com/maps/dir/?api=1&destination={dest_enc}"


def get_travel_time(destination: str, origin: str = "") -> str | None:
    """Usa Directions API para estimar tempo de deslocamento."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key or not origin:
        return None
    try:
        params = urllib.parse.urlencode({
            "origin": origin,
            "destination": destination,
            "key": api_key,
            "language": "pt-BR",
            "mode": "driving",
        })
        url = f"https://maps.googleapis.com/maps/api/directions/json?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "OK":
            leg = data["routes"][0]["legs"][0]
            return leg["duration"]["text"]
    except Exception:
        pass
    return None


def build_location_description(location: str) -> str:
    """Monta bloco de localização para incluir na descrição do evento.
    Não usa origem fixa — o Maps usa a localização atual do dispositivo ao abrir."""
    if not location:
        return ""
    # Sem origin → Google Maps usa GPS do celular automaticamente
    route = directions_link(location)
    maps = maps_link(location)
    lines = [
        f"📍 Local: {location}",
        f"🗺️ Ver no Maps: {maps}",
        f"🧭 Como chegar (usa sua localização atual): {route}",
    ]
    return "\n".join(lines)


def get_travel_time_from_coords(destination: str, lat: float, lng: float) -> str | None:
    """Calcula tempo de deslocamento a partir de coordenadas GPS do usuário."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return None
    try:
        origin = f"{lat},{lng}"
        params = urllib.parse.urlencode({
            "origin": origin,
            "destination": destination,
            "key": api_key,
            "language": "pt-BR",
            "mode": "driving",
        })
        url = f"https://maps.googleapis.com/maps/api/directions/json?{params}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
        if data.get("status") == "OK":
            leg = data["routes"][0]["legs"][0]
            duration = leg["duration"]["text"]
            distance = leg["distance"]["text"]
            return f"{duration} ({distance})"
    except Exception:
        pass
    return None


def directions_link_from_coords(destination: str, lat: float, lng: float) -> str:
    dest_enc = urllib.parse.quote(destination)
    return f"https://www.google.com/maps/dir/?api=1&origin={lat},{lng}&destination={dest_enc}"
