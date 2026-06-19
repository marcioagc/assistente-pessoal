"""
Cria filtros Gmail para todos os labels existentes.
Remove emails da caixa de entrada automaticamente.
"""
from dotenv import load_dotenv
load_dotenv()

from src.google_services import create_filter, list_filters, get_label_id

ok = []
fail = []

def f(label, **kwargs):
    try:
        fid = create_filter(label, **kwargs)
        ok.append(f"OK  [{fid[:12]}]  {label}  |  {kwargs}")
    except Exception as e:
        fail.append(f"ERR  {label}  |  {kwargs}  =>  {e}")

# ── Trabalho ────────────────────────────────────────────────────────────────────
f("6. Trabalho/1. Accenture",   query="from:(@accenture.com) OR from:(@accenture.com.br)")
f("6. Trabalho/2. Sysmap",      query="from:(@sysmap.com.br) OR from:(@sysmap.com)")
f("6. Trabalho/3. Capgemini",   query="from:(@capgemini.com) OR from:(@capgemini.com.br)")
f("6. Trabalho/4. Backlgrs",    query="from:(@backloggers.com.br) OR from:(@backlgrs.com) OR Backlgrs")

# ── Financeiro / Bancos ─────────────────────────────────────────────────────────
f("7. Financeiro/Bancos", query=(
    "from:(@nubank.com.br OR @itau.com.br OR @bradesco.com.br OR @santander.com.br "
    "OR @bb.com.br OR @cef.gov.br OR @bancointer.com.br OR @c6bank.com.br "
    "OR @next.me OR @btgpactual.com OR @xpi.com.br OR @rico.com.vc "
    "OR @clear.com.br OR @picpay.com OR @mercadopago.com OR @pagbank.com.br)"
))

# ── Financeiro / Impostos e NFs ─────────────────────────────────────────────────
f("7. Financeiro/Impostos e NFs", query=(
    "from:(@sefaz.gov.br OR @receita.fazenda.gov.br OR @nfe.fazenda.gov.br) "
    "OR subject:(\"nota fiscal\" OR \"NF-e\" OR DANFE OR DARF OR \"imposto de renda\" "
    "OR \"declaração IR\" OR \"comprovante fiscal\")"
))

# ── Investimentos ───────────────────────────────────────────────────────────────
f("4. Investimentos", query=(
    "from:(@b3.com.br OR @xpi.com.br OR @rico.com.vc OR @clear.com.br "
    "OR @btgpactual.com OR @modalmais.com.br OR @ativainvestimentos.com.br) "
    "OR subject:(dividendo OR dividendos OR \"renda fixa\" OR \"tesouro direto\" "
    "OR \"fundo imobiliário\" OR FII OR \"informe de rendimentos\" OR \"posição carteira\")"
))

# ── Newsletters / Salesforce ────────────────────────────────────────────────────
f("8. Newsletters/Salesforce", query=(
    "from:(@salesforce.com OR @trailhead.com OR @pardot.com OR @exact.target.com "
    "OR @marketing.salesforce.com) "
    "OR subject:(Salesforce OR Trailhead OR AppExchange OR Dreamforce)"
))

# ── Newsletters / Recrutamento ──────────────────────────────────────────────────
f("8. Newsletters/Recrutamento", query=(
    "from:(@linkedin.com OR @gupy.io OR @catho.com.br OR @infojobs.com.br "
    "OR @indeed.com OR @glassdoor.com OR @vagas.com.br OR @123empregos.com.br "
    "OR @recrutei.com.br OR @kenoby.com) "
    "OR subject:(\"vaga\" OR \"oportunidade\" OR \"proposta\" OR recrutamento OR \"processo seletivo\")"
))

# ── Newsletters / Geral ─────────────────────────────────────────────────────────
# Emails com link de descadastro que não encaixaram nas outras pastas
f("8. Newsletters/Geral", query=(
    "list:* unsubscribe "
    "-from:(@salesforce.com @trailhead.com @linkedin.com @gupy.io @catho.com.br "
    "@infojobs.com.br @indeed.com @glassdoor.com)"
))

# ── Segurança ───────────────────────────────────────────────────────────────────
f("8. Segurança", query=(  # label com encoding issue, tenta pelo ID
    "subject:(\"código de verificação\" OR \"código de segurança\" OR \"autenticação\" "
    "OR \"verificação em duas etapas\" OR \"acesso suspeito\" OR \"alerta de segurança\" "
    "OR \"login\" OR \"senha\" OR \"redefinir senha\" OR \"confirme seu email\" "
    "OR \"verify\" OR \"verification code\" OR \"security alert\" OR \"sign-in\")"
))

# ── Compras ─────────────────────────────────────────────────────────────────────
f("5. Compras", query=(
    "from:(@amazon.com.br OR @mercadolivre.com OR @shopee.com.br "
    "OR @magazineluiza.com.br OR @americanas.com.br OR @submarino.com.br "
    "OR @casasbahia.com.br OR @pontofrio.com.br OR @extra.com.br "
    "OR @netshoes.com.br OR @zattini.com.br OR @dafiti.com.br) "
    "OR subject:(\"seu pedido\" OR \"rastreio\" OR \"código de rastreamento\" "
    "OR \"entrega\" OR \"nota fiscal\" OR \"compra aprovada\" OR \"pedido confirmado\")"
))

# ── Escola ──────────────────────────────────────────────────────────────────────
f("9. Escola", query=(
    "subject:(\"boletim\" OR \"nota\" OR \"matrícula\" OR \"mensalidade\" "
    "OR \"atividade\" OR \"prova\" OR \"aula\" OR \"turma\" OR \"escola\" "
    "OR \"colégio\" OR \"universidade\" OR \"faculdade\")"
))

print("\n=== FILTROS CRIADOS ===")
for r in ok:
    print(r)

if fail:
    print("\n=== FALHAS ===")
    for r in fail:
        print(r)

print(f"\nTotal: {len(ok)} criados, {len(fail)} falhas")
print("\nFiltros que precisam de mais informacao:")
print("  - 1. Bruguelo       -> qual email/dominio?")
print("  - 2. Apartamento    -> qual email/dominio? (administradora, sindico?)")
print("  - 3. Documentos     -> criterio? (RG, CPF, contratos?)")
print("  - 1. Assuntos pend. -> criterio manual, sem filtro automatico")
