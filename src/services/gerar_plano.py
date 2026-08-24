import os, shutil, csv, re
from collections import defaultdict

MONTH_MAP = {
    "01 - JAN - 26": "JANEIRO",
    "02 - FEV - 26": "FEVEREIRO",
    "03 - MAR - 26": "MARÇO",
    "04 - ABR - 26": "ABRIL",
    "05 - MAI - 26": "MAIO",
    "06 - JUN - 26": "JUNHO",
    "07 - JUL - 26": "JULHO",
    "08 - AGO - 26": "AGOSTO",
}
SOURCE_ROOT = r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\01_BOLETINS_DIARIOS\03_AUDIOS_RADIO"
DEST_ROOT = r"F:\Projetos\DIVISOR\JORNAIS"
NJUDS_CSV = r"F:\Projetos\DIVISOR\data\jornal_njuds.csv"
PLAN_CSV = r"F:\Projetos\DIVISOR\data\plano_alocacao.csv"
REPORT_CSV = r"F:\Projetos\DIVISOR\data\alocacao_boletins.csv"
MISSING_CSV = r"F:\Projetos\DIVISOR\data\njuds_faltantes.csv"

BLOCKED_ENTITIES = {
    "OAB", "OABRN", "TRE", "TSE", "STF", "CNJ", "MPRN", "TRTRN", "DPERN",
    "TCERN", "TCE", "TJDFT", "TJMG", "TJSP", "STJ", "MPF", "PF", "PRF"
}
pat = re.compile(r"^BOLETIM_RADIO_TJRN_(\d{2}_(\d{2})_(\d{4}))_B(\d+)_(.+?)\.mp3$", re.IGNORECASE)
month_num_to_name = {
    "01": "JANEIRO", "02": "FEVEREIRO", "03": "MARÇO", "04": "ABRIL",
    "05": "MAIO", "06": "JUNHO", "07": "JULHO", "08": "AGOSTO"
}

njuds_by_month = {}
with open(NJUDS_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        njuds_by_month[row["mes"]] = [x.strip() for x in row["njuds"].split(";") if x.strip()]

# Build pool per month-of-date (strict date-month -> pool)
pool_by_month = defaultdict(list)
seen = set()
for src_month_dir in sorted(os.listdir(SOURCE_ROOT)):
    src = os.path.join(SOURCE_ROOT, src_month_dir)
    if not os.path.isdir(src):
        continue
    for dirpath, dirnames, filenames in os.walk(src):
        for f in filenames:
            m = pat.match(f)
            if not m:
                continue
            data_full, mes_num, ano, bnum, retranca = m.groups()
            key = (data_full, bnum)
            if key in seen:
                continue
            seen.add(key)
            ent = retranca.upper().split("_")[0]
            blocked = ent in BLOCKED_ENTITIES
            dest = month_num_to_name.get(mes_num)
            if not dest or dest not in njuds_by_month:
                continue
            pool_by_month[dest].append((data_full, int(bnum), retranca, f, dirpath, ent, blocked))

# Sort each pool: data crescente, não-bloqueados primeiro, TJRN primeiro, bloqueados por último
for m in pool_by_month:
    pool_by_month[m].sort(key=lambda x: (
        tuple(int(n) for n in x[0].split("_")),
        1 if x[6] else 0,
        0 if x[5] == "TJRN" else 1,
        x[1]
    ))

plan_rows = []
missing = []
used_global = set()

for month_name in sorted(njuds_by_month):
    njuds = njuds_by_month[month_name]
    own_pool = pool_by_month.get(month_name, [])
    for njud in njuds:
        # pick up to 4 from own month (prefer non-blocked)
        picked = []
        for item in own_pool:
            if len(picked) >= 4:
                break
            data_full, bnum, retranca, fname, src, ent, blocked = item
            key = (data_full, bnum)
            if key in used_global:
                continue
            used_global.add(key)
            picked.append({
                "mes_destino": month_name,
                "njud": njud,
                "arquivo": fname,
                "data": data_full,
                "boletim": f"B{bnum}",
                "retranca": retranca,
                "entidade": ent,
                "bloqueado": "SIM" if blocked else "NAO",
                "src": src,
            })
        # fallback: complete with ONE other month, using blocked if necessary
        if len(picked) < 4:
            fallback_month = None
            for om in sorted(pool_by_month):
                if om == month_name:
                    continue
                available = [x for x in pool_by_month[om] if (x[0], x[1]) not in used_global]
                if len(available) >= (4 - len(picked)):
                    fallback_month = om
                    break
            if fallback_month:
                for item in pool_by_month[fallback_month]:
                    if len(picked) >= 4:
                        break
                    data_full, bnum, retranca, fname, src, ent, blocked = item
                    key = (data_full, bnum)
                    if key in used_global:
                        continue
                    used_global.add(key)
                    picked.append({
                        "mes_destino": month_name,
                        "njud": njud,
                        "arquivo": fname,
                        "data": data_full,
                        "boletim": f"B{bnum}",
                        "retranca": retranca,
                        "entidade": ent,
                        "bloqueado": "SIM" if blocked else "NAO",
                        "src": src,
                    })
        if len(picked) < 4:
            missing.append((month_name, njud, 4 - len(picked)))
        plan_rows.extend(picked)

with open(PLAN_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["mes_destino","njud","arquivo","data","boletim","retranca","entidade","bloqueado","src"])
    writer.writeheader()
    writer.writerows(plan_rows)

with open(MISSING_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["mes", "njud", "faltam"])
    writer.writerows(missing)

print(f"Plano: {PLAN_CSV}")
print(f"Faltantes: {MISSING_CSV}")
print(f"Total alocado: {len(plan_rows)}")
from collections import Counter
c = Counter(r["mes_destino"] for r in plan_rows)
print("Resumo:")
for m in sorted(c):
    print(f"  {m}: {c[m]}")
print("Faltantes:")
for r in missing:
    print(r)
