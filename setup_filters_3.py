"""Filtros específicos por domínio: TownSq (Apartamento) e AgendaTellme (Bruguelo)."""
from dotenv import load_dotenv
load_dotenv()
from src.google_services import create_filter

ok = []
fail = []

def f(label, **kwargs):
    try:
        fid = create_filter(label, **kwargs)
        ok.append(f"OK  [{fid[:12]}]  {label}  |  {kwargs}")
    except Exception as e:
        fail.append(f"ERR  {label}  =>  {e}")

# Encomendas do condomínio via TownSq → Apartamento
f("2. Apartamento", from_="noreply@townsq.com.br")

# Escola do Bruguelo via AgendaTellme → Bruguelo
f("1. Bruguelo", from_="naoresponda@agendatellme.com.br")

print("\n=== FILTROS CRIADOS ===")
for r in ok:
    print(r)
if fail:
    print("\n=== FALHAS ===")
    for r in fail:
        print(r)
print(f"\nTotal: {len(ok)} criados, {len(fail)} falhas")
