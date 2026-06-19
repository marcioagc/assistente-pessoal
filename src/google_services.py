import os
import json
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
