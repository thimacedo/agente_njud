import os
import logging
from pathlib import Path

LOG_DIR = r'F:\Projetos\DIVISOR\logs'
os.makedirs(LOG_DIR, exist_ok=True)
ERROR_LOG_PATH = os.path.join(LOG_DIR, 'error.log')

logging.basicConfig(
    filename=ERROR_LOG_PATH,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

LOGS_OUT = Path(r'F:\Projetos\DIVISOR\data\output\_logs')
FALTANTES_JSON = LOGS_OUT / 'faltantes_jan_ago_2026.json'
FALTANTES_CSV = LOGS_OUT / 'faltantes_jan_ago_2026.csv'
RESUMO_TXT = LOGS_OUT / 'resumo_faltantes_jan_ago_2026.txt'

def gerar_plano_faltantes() -> None:
    """Gera a estrutura de rastreamento para os dias faltantes identificados no diagnóstico.

    Returns:
        None

    Raises:
        Exception: Captura falhas na geração ou escrita de arquivos de controle.
    """
    try:
        print("Mapeando matriz de demanda para os dias faltantes (Março a Agosto).")
        if not FALTANTES_JSON.exists() or not FALTANTES_CSV.exists():
            raise RuntimeError('Arquivos de faltantes não encontrados; execute a geração primeiro.')

        linhas = []
        linhas.append('RESUMO DE FALTANTES - JANEIRO A AGOSTO DE 2026')
        linhas.append('=' * 60)
        import json
        dados = json.loads(FALTANTES_JSON.read_text(encoding='utf-8'))
        for item in dados.get('resumo', []):
            mes = item.get('mes', '')
            falt = item.get('faltantes', 0)
            linhas.append(f"{mes}: {falt} dia(s) faltante(s)")
        linhas.append('-' * 60)
        linhas.append(f"CSV: {FALTANTES_CSV}")
        linhas.append(f"JSON: {FALTANTES_JSON}")
        RESUMO_TXT.write_text('\n'.join(linhas), encoding='utf-8')
        print('\n'.join(linhas))
    except Exception as e:
        logging.error(f"Erro ao gerar plano de faltantes: {str(e)}")
        raise

if __name__ == '__main__':
    gerar_plano_faltantes()
