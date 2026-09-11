#!/usr/bin/env python3
"""
Bootstrap: cria JSONs iniciais PENDENTE para mp3s SEM_JSON em JORNAIS_DIVIDIDOS
e prepara o dispatcher para rodar sobre JORNAIS_DIVIDIDOS como pasta de entrada.
"""
import json, os, glob
from datetime import datetime

estado_dir = 'data/processed/PRODUCAO_2026/estado_por_arquivo'
div_dir = 'data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS'

def bn(p):
    return os.path.basename(p)

criados = 0
ignorados = 0
erros = 0

for p in sorted(glob.glob(os.path.join(div_dir, '*'))):
    if not os.path.isdir(p):
        continue
    for a in glob.glob(os.path.join(p, '*.mp3')):
        bnome = bn(a)
        if '_CABECA' in bnome or '_CORPO' in bnome:
            continue  # já é arquivo de corte
        stem = os.path.splitext(bnome)[0]
        json_path = os.path.join(estado_dir, stem + '.json')
        if os.path.exists(json_path):
            ignorados += 1
            continue
        # Cria JSON PENDENTE
        nj = bn(p)
        entry = {
            "njud": nj,
            "arquivo": a,
            "status": "PENDENTE",
            "timestamp_inicio": datetime.now().isoformat(),
            "tentativas": 0,
            "ultima_tentativa": None,
            "error": None,
            "cortes": {"cabeca": None, "corpo": None},
        }
        try:
            with open(json_path, 'w', encoding='utf-8') as fh:
                json.dump(entry, fh, ensure_ascii=False, indent=2)
            criados += 1
        except Exception as e:
            erros += 1
            print(f'ERRO ao criar {json_path}: {e}')

print(f'Resumo bootstrap:')
print(f'  JSONs criados: {criados}')
print(f'  Ja existentes (ignorados): {ignorados}')
print(f'  Erros: {erros}')
print(f'  Total de mp3s sem JSON em JORNAIS_DIVIDIDOS: {criados + ignorados}')
