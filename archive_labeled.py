"""
Remove do INBOX todos os emails que já têm pelo menos um label de usuário.
Emails sem nenhum label de usuário permanecem na caixa de entrada.
"""
from dotenv import load_dotenv
load_dotenv()

from src.google_services import get_gmail_service, _get_label_map

service = get_gmail_service()

# IDs de labels de sistema que não contam como "classificado"
SYSTEM_LABELS = {
    "INBOX", "SENT", "TRASH", "SPAM", "UNREAD", "STARRED",
    "IMPORTANT", "CATEGORY_PERSONAL", "CATEGORY_SOCIAL",
    "CATEGORY_PROMOTIONS", "CATEGORY_UPDATES", "CATEGORY_FORUMS",
}

print("Buscando emails na caixa de entrada...")
to_archive = []
page_token = None

while True:
    params = dict(userId="me", labelIds=["INBOX"], maxResults=500)
    if page_token:
        params["pageToken"] = page_token

    result = service.users().messages().list(**params).execute()
    messages = result.get("messages", [])

    for msg in messages:
        detail = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=[]
        ).execute()
        label_ids = set(detail.get("labelIds", []))
        # Tem algum label de usuário (não-sistema)?
        user_labels = label_ids - SYSTEM_LABELS
        if user_labels:
            to_archive.append(msg["id"])

    page_token = result.get("nextPageToken")
    if not page_token:
        break

print(f"  {len(to_archive)} emails com label mas ainda no INBOX.")

if not to_archive:
    print("Nada a fazer.")
else:
    print("Arquivando em lotes...")
    for i in range(0, len(to_archive), 100):
        chunk = to_archive[i:i+100]
        service.users().messages().batchModify(
            userId="me",
            body={"ids": chunk, "removeLabelIds": ["INBOX"]}
        ).execute()
        print(f"  {min(i+100, len(to_archive))}/{len(to_archive)} processados...")

    print(f"\nConcluido! {len(to_archive)} emails arquivados.")
    print("Os que ficaram no INBOX nao possuem nenhum label — sao os nao identificados.")
