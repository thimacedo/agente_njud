#!/usr/bin/env python3
"""
YOLO: Corrigir 32 JSONs de planejamento do GIRO.
Regra: janela [X, X+7] → [X-6, X-1]
"""

import json
from pathlib import Path
from datetime import date, timedelta

plano_dir = Path('E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/config/planejamento_2026')
corrigidos = 0

for f in sorted(plano_dir.glob('giro_*.json')):
    j = json.loads(f.read_text(encoding='utf-8'))
    exib = date.fromisoformat(j['data_exibicao'])
    
    # Janela correta: [X-6, X-1]
    nova_ini = (exib - timedelta(days=6)).isoformat()
    nova_fim = (exib - timedelta(days=1)).isoformat()
    
    j['janela_coleta']['inicio'] = nova_ini
    j['janela_coleta']['fim'] = nova_fim
    
    f.write_text(json.dumps(j, indent=2, ensure_ascii=False), encoding='utf-8')
    corrigidos += 1
    print(f'✓ {f.name}: {j["janela_coleta"]["inicio"]} a {j["janela_coleta"]["fim"]}')

print(f'\n{corrigidos} JSONs corrigidos')
