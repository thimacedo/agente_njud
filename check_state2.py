import json, os, glob

div = 'data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS'
pastas = sorted([d for d in glob.glob(os.path.join(div, '*')) if os.path.isdir(d)])
print(f"Total de pastas NJUD em JORNAIS_DIVIDIDOS: {len(pastas)}")

com_cortes = 0
sem_cortes = 0
for p in pastas:
    arquivos = glob.glob(os.path.join(p, '*_CABECA.mp3'))
    if arquivos:
        com_cortes += 1
    else:
        sem_cortes += 1

print(f"Com cortes (_CABECA): {com_cortes}")
print(f"Sem cortes: {sem_cortes}")
print()

print("=== NJUDs SEM cortes ===")
for p in pastas:
    arquivos = glob.glob(os.path.join(p, '*_CABECA.mp3'))
    if not arquivos:
        print(f"  {os.path.basename(p)}")

print()
print("=== Amostra de NJUDs com cortes (primeiros 5) ===")
for p in pastas[:5]:
    ce = glob.glob(os.path.join(p, '*_CABECA.mp3'))
    co = glob.glob(os.path.join(p, '*_CORPO.mp3'))
    orig = glob.glob(os.path.join(p, '*.mp3'))
    orig_sem_corte = [a for a in orig if '_CABECA' not in os.path.basename(a) and '_CORPO' not in os.path.basename(a)]
    print(f"  {os.path.basename(p)}: orig={len(orig_sem_corte)} cabe={len(ce)} corpo={len(co)}")

print()
print("=== Resumo estado_por_arquivo ===")
estado = 'data/processed/PRODUCAO_2026/estado_por_arquivo'
counts = {}
nj_nao_ok = set()
for f in glob.glob(os.path.join(estado, '*.json')):
    with open(f, 'r') as fh:
        d = json.load(fh)
    s = d.get('status','?')
    counts[s] = counts.get(s,0)+1
    if s not in ('OK','ESGOTADO_ACEITO'):
        nj_nao_ok.add(d.get('njud','?'))

for k,v in sorted(counts.items()):
    print(f"  {k}: {v}")
print(f"Total: {sum(counts.values())}")
print(f"NJUDs com pelo menos 1 arquivo nao-OK: {len(nj_nao_ok)}")
print(f"  NJUDs: {sorted(nj_nao_ok)}")
