#!/usr/bin/env python3
"""
Relatório pós-download:
- Compara cobertura antes/depois em uma pasta de saída.
- Gera CSV de faltantes restantes por data.
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from src.utils.logger import get_logger

logger = get_logger(__name__)

MESES = {
    '01': 'JANEIRO', '02': 'FEVEREIiro', '03': 'MARÇO', '04': 'ABRIL',
    '05': 'MAIO', '06': 'JUNHO', '07': 'JULHO', '08': 'AGOSTO',
    '09': 'SETEMBRO', '10': 'OUTUBRO', '11': 'NOVEMBRO', '12': 'DEZEMBRO',
}


def _listar_baixados(pasta: Path) -> Dict[str, List[Path]]:
    mapa: Dict[str, List[Path]] = {}
    for p in pasta.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.mp3', '.wav', '.m4a', '.aac', '.ogg'}:
            base = p.stem
            data = None
            for parte in base.split('_'):
                try:
                    data = datetime.strptime(parte, '%Y-%m-%d').strftime('%Y-%m-%d')
                    break
                except ValueError:
                    pass
                try:
                    data = datetime.strptime(parte, '%d-%m-%Y').strftime('%Y-%m-%d')
                    break
                except ValueError:
                    pass
            if data:
                mapa.setdefault(data, []).append(p)
    return mapa


def gerar_relatorio(pasta: Path, saida: Path, alvos: List[str]) -> Path:
    baixados = _listar_baixados(pasta)
    faltantes = [{'data': d, 'status': 'faltante'} for d in sorted(alvos) if d not in baixados]
    ordenados = sorted(alvos)
    encontrados = [{'data': d, 'status': 'ok', 'arquivos': len(baixados.get(d, []))} for d in ordenados if d in baixados]
    with saida.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['data','status','arquivos'])
        writer.writeheader()
        writer.writerows(encontrados + faltantes)
    logger.info(f"Relatório gerado: {saida}")
    return saida


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Relatório pós-download')
    parser.add_argument('--saida', required=True, help='Arquivo CSV de saída')
    parser.add_argument('--pasta', default='./boletins_brutos_rss', help='Pasta de download')
    parser.add_argument('--alvo', default='data/_pipeline_logs/alvos_recuperacao.csv', help='CSV de alvos')
    args = parser.parse_args()

    alvos_path = Path(args.alvo)
    if not alvos_path.exists():
        logger.error(f"Arquivo de alvos não encontrado: {alvos_path}")
        return 1

    with alvos_path.open('r', encoding='utf-8') as f:
        linhas = list(csv.DictReader(f))
    alvos = sorted({r['data'] for r in linhas if r.get('data')})
    gerar_relatorio(Path(args.pasta), Path(args.saida), alvos)
    print(f"Relatório salvo em: {args.saida}")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
