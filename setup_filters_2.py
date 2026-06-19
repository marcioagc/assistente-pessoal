"""Filtros complementares: Bruguelo, Apartamento, Documentos."""
from dotenv import load_dotenv
load_dotenv()

from src.google_services import create_filter

ok = []
fail = []

def f(label, **kwargs):
    try:
        fid = create_filter(label, **kwargs)
        ok.append(f"OK  [{fid[:12]}]  {label}")
    except Exception as e:
        fail.append(f"ERR  {label}  =>  {e}")

# ── 1. Bruguelo (filho — assuntos escolares específicos dele) ───────────────────
# Emails que mencionam "Bruguelo" no assunto
f("1. Bruguelo", query="subject:Bruguelo")
# Emails do nome completo caso apareça
f("1. Bruguelo", query="Bruguelo")

# ── 2. Apartamento ──────────────────────────────────────────────────────────────
# Administradora Marvan
f("2. Apartamento", query="from:(@marvan.com.br OR @marvan.com.br) OR subject:(Marvan)")

# Condomínio (boletos, assembleias, avisos do síndico)
f("2. Apartamento", query=(
    'subject:("condomínio" OR "taxa condominial" OR "cota condominial" OR '
    '"boleto condomínio" OR assembleia OR síndico OR "fundo de reserva" OR '
    '"convenção condominial" OR "reunião de condôminos" OR IPTU OR "aviso de encomenda" OR '
    '"encomenda disponível" OR "retirada de encomenda" OR "objeto disponível para retirada")'
))

# Energia elétrica (distribuidoras brasileiras principais)
f("2. Apartamento", query=(
    "from:(@enel.com.br OR @cpfl.com.br OR @cemig.com.br OR @light.com.br "
    "OR @energisa.com.br OR @neoenergia.com OR @elektro.com.br OR @celpe.com.br "
    "OR @coelba.com.br OR @celg.com.br OR @copel.com.br OR @eletropaulo.com.br) "
    'OR subject:("conta de energia" OR "fatura de energia" OR "fornecimento de energia" '
    'OR "leitura do medidor")'
))

# Financiamento imobiliário — emails da Caixa com assunto de imóvel
# (Caixa já vai para Bancos, mas esse filtro é mais específico e entra em Apartamento tb)
f("2. Apartamento", query=(
    'subject:("financiamento imobiliário" OR "prestação do imóvel" OR "habitação" OR '
    '"SFH" OR "SFI" OR "FGTS imóvel" OR "carta de crédito imóvel" OR '
    '"prestação habitacional" OR "minha casa minha vida")'
))

# ── 3. Documentos (cunho pessoal — exclui PJ/empresarial) ──────────────────────
# Comprovantes e recibos pessoais — exclui CNPJ e termos empresariais
f("3. Documentos", query=(
    'subject:("comprovante" OR "recibo" OR "declaração" OR "extrato" OR '
    '"certidão" OR "atestado" OR "contrato" OR "apólice" OR "comprovante de residência" OR '
    '"comprovante de pagamento" OR "comprovante de transferência" OR '
    '"pagamento realizado" OR "transferência realizada") '
    '-subject:(CNPJ OR "razão social" OR "pessoa jurídica" OR "nota fiscal de serviço" OR NFSe)'
))

# ── Resultados ──────────────────────────────────────────────────────────────────
print("\n=== FILTROS CRIADOS ===")
for r in ok:
    print(r)

if fail:
    print("\n=== FALHAS ===")
    for r in fail:
        print(r)

print(f"\nTotal: {len(ok)} criados, {len(fail)} falhas")
