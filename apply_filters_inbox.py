"""
Aplica todos os filtros existentes aos emails que estão na caixa de entrada.
Emails identificados pelos filtros saem do INBOX e ganham o label correspondente.
Emails não identificados permanecem na caixa de entrada.
"""
from dotenv import load_dotenv
load_dotenv()

from src.google_services import get_gmail_service, _get_label_map

service = get_gmail_service()
label_map = _get_label_map()           # nome → id
label_map_inv = {v: k for k, v in label_map.items()}  # id → nome

# ── 1. Carrega todos os filtros ─────────────────────────────────────────────────
print("Carregando filtros...")
filters_raw = service.users().settings().filters().list(userId="me").execute().get("filter", [])
print(f"  {len(filters_raw)} filtros encontrados.")

# Monta lista: (query_para_busca, label_id)
tasks = []
for f in filters_raw:
    criteria = f.get("criteria", {})
    action   = f.get("action", {})
    add_ids  = action.get("addLabelIds", [])
    if not add_ids:
        continue

    # Constrói query de busca a partir dos critérios do filtro
    parts = []
    if criteria.get("from"):
        parts.append(f'from:({criteria["from"]})')
    if criteria.get("to"):
        parts.append(f'to:({criteria["to"]})')
    if criteria.get("subject"):
        parts.append(f'subject:({criteria["subject"]})')
    if criteria.get("query"):
        parts.append(criteria["query"])

    if not parts:
        continue

    query = " ".join(parts) + " in:inbox"
    tasks.append((query, add_ids[0]))

print(f"  {len(tasks)} tarefas de busca montadas.\n")

# ── 2. Para cada filtro, busca e processa emails ────────────────────────────────
total_moved = 0

for query, label_id in tasks:
    label_name = label_map_inv.get(label_id, label_id)
    page_token = None
    batch_count = 0

    while True:
        params = dict(userId="me", q=query, maxResults=500)
        if page_token:
            params["pageToken"] = page_token

        result = service.users().messages().list(**params).execute()
        messages = result.get("messages", [])

        if not messages:
            break

        # Processa em lotes de 100 (limite da API batchModify)
        for i in range(0, len(messages), 100):
            chunk = messages[i:i+100]
            ids = [m["id"] for m in chunk]
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": ids,
                    "addLabelIds": [label_id],
                    "removeLabelIds": ["INBOX"],
                }
            ).execute()
            batch_count += len(ids)

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    if batch_count:
        total_moved += batch_count
        print(f"  [{label_name}]  {batch_count} emails organizados")

print(f"\nConcluido! {total_moved} emails movidos para seus labels.")
print("Emails nao identificados permanecem na caixa de entrada.")
