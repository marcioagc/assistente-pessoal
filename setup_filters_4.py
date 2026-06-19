from dotenv import load_dotenv
load_dotenv()
from src.google_services import create_filter, get_gmail_service, _get_label_map, get_label_id

service = get_gmail_service()
label_map_inv = {v: k for k, v in _get_label_map().items()}
SYSTEM_LABELS = {"INBOX","SENT","TRASH","SPAM","UNREAD","STARRED","IMPORTANT",
                 "CATEGORY_PERSONAL","CATEGORY_SOCIAL","CATEGORY_PROMOTIONS",
                 "CATEGORY_UPDATES","CATEGORY_FORUMS"}

ok = []
fail = []

def f(label, **kwargs):
    try:
        fid = create_filter(label, **kwargs)
        ok.append((fid, label, kwargs))
    except Exception as e:
        fail.append(f"ERR {label} => {e}")

f("2. Apartamento", query='"Santa Adelia Energia" OR "Santa Adélia Energia" OR from:(santaadelia)')
f("2. Apartamento", query='"Marvan" OR from:(@marvan.com.br) OR from:(@marvanadministradora.com.br)')
f("4. Investimentos", query='"TRX" OR "TRX Investimentos" OR from:(@trxinvestimentos.com.br) OR from:(@trx.com.br)')
f("4. Investimentos", query='"Matheus Nogueira" OR from:(matheusnogueirafinancas) OR from:(matheusnogueiraof)')

print("=== FILTROS CRIADOS ===")
for fid, label, kwargs in ok:
    print(f"OK  [{fid[:12]}]  {label}")
if fail:
    print("\n=== FALHAS ===")
    for r in fail: print(r)
print(f"\nTotal: {len(ok)} criados, {len(fail)} falhas")

# Aplica imediatamente nos emails existentes no INBOX
print("\nAplicando nos emails existentes no INBOX...")
total = 0
for fid, label, kwargs in ok:
    query_parts = []
    if "from_" in kwargs: query_parts.append(f'from:({kwargs["from_"]})')
    if "query" in kwargs: query_parts.append(kwargs["query"])
    q = " ".join(query_parts) + " in:inbox"

    label_id = get_label_id(label)
    if not label_id:
        continue

    page_token = None
    count = 0
    while True:
        res = service.users().messages().list(userId="me", q=q, maxResults=500,
              **({'pageToken': page_token} if page_token else {})).execute()
        msgs = res.get("messages", [])
        for i in range(0, len(msgs), 100):
            chunk = [m["id"] for m in msgs[i:i+100]]
            service.users().messages().batchModify(userId="me", body={
                "ids": chunk,
                "addLabelIds": [label_id],
                "removeLabelIds": ["INBOX"],
            }).execute()
            count += len(chunk)
        page_token = res.get("nextPageToken")
        if not page_token: break

    if count:
        total += count
        print(f"  [{label}]  {count} emails organizados")

print(f"\nConcluido! {total} emails movidos para suas pastas.")
