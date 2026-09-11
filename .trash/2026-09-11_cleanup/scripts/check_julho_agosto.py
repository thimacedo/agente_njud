import json, os, glob

estado = 'data/processed/PRODUCAO_2026/estado_por_arquivo'
div = 'data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS'

# NJUDs de JULHO/AGOSTO (1900+)
print('=== NJUDs de JULHO/AGOSTO (1900+) sem cortes em JORNAIS_DIVIDIDOS ===')
pastas = sorted([d for d in glob.glob(os.path.join(div, '*')) if os.path.isdir(d)])
for p in pastas:
    nj = os.path.basename(p)
    try:
        num = int(nj.split()[-1])
    except:
        continue
    if num < 1900:
        continue
    ce = glob.glob(os.path.join(p, '*_CABECA.mp3'))
    if not ce:
        # Conta mp3s originais
        orig = glob.glob(os.path.join(p, '*.mp3'))
        orig = [a for a in orig if '_CABECA' not in os.path.basename(a) and '_CORPO' not in os.path.basename(a)]
        # Verifica estado
        estados_nj = []
        for a in orig:
            stem = os.path.splitext(os.path.basename(a))[0]
            json_path = os.path.join(estado, stem + '.json')
            if os.path.exists(json_path):
                with open(json_path) as fh:
                    d = json.load(fh)
                estados_nj.append((os.path.basename(a), d.get('status','?')))
            else:
                estados_nj.append((os.path.basename(a), 'SEM_JSON'))
        print(f'{nj}: {len(orig)} mp3(s) -> {estados_nj}')

print()
print('=== NJUDs JULHO/AGOSTO com arquivos nao-OK ===')
for f in glob.glob(os.path.join(estado, '*.json')):
    with open(f) as fh:
        d = json.load(fh)
    s = d.get('status','?')
    if s not in ('OK','ESGOTADO_ACEITO'):
        nj = d.get('njud','?')
        try:
            num = int(nj.split()[-1])
        except:
            continue
        if num >= 1900:
            print(f'{os.path.basename(f)}: status={s} njud={nj} arquivo={d.get("arquivo","?")}')
