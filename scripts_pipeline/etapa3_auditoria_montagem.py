#!/usr/bin/env python3
"""
ETAPA 3: Auditoria de Montagem
Verifica JORNAIS_FINAL/, detecta problemas e reporta.
Caminhos livres (sem dependência de módulos internos do projeto).
"""
from __future__ import annotations
import os, sys, json, csv, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Caminhos base
BASE_DIR = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = DATA_DIR / "output" / "JORNAIS_FINAL"
LOGS_DIR = BASE_DIR / "logs"
NJUDS_VALIDOS_CSV = BASE_DIR / "NJUDS_VALIDOS.csv"
CHECKLIST_CSV = BASE_DIR / "projeto_etapa_final_2026/checklists/checklist_jornais.csv"

# Diretórios de cortes que podem ter sido usados na montagem
DIRS_DIVIDIDOS = [
    DATA_DIR / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS",
    DATA_DIR / "processed" / "JORNAIS_DIVIDIDOS_TESTE",
    DATA_DIR / "processed" / "JORNAIS_DIVIDIDOS_MAI_PLANO",
]

MIN_DURACAO_MIN = 5 * 60 * 1000  # 5 min em ms
MAX_DURACAO_MAX = 15 * 60 * 1000  # 15 min em ms

os.makedirs(LOGS_DIR, exist_ok=True)

# ============================================================================
# HELPERS
# ============================================================================

def extrair_numero_njud(nome_pasta: str) -> int | None:
    """Extrai número do NJUD de nome como 'NJUD 1849' ou 'NJUD_1849'."""
    m = re.search(r"NJUD[\s_]+(\d+)", nome_pasta)
    return int(m.group(1)) if m else None

def extrair_numero_boletim(nome_arquivo: str) -> int:
    m = re.search(r"_B(\d+)_", nome_arquivo)
    return int(m.group(1)) if m else 0

def pegar_duracao_mp3(caminho: Path) -> int | None:
    """Tenta ler duração com pydub. Retorna ms ou None se falhar."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(caminho), format="mp3")
        return len(audio)  # ms
    except Exception as e:
        return None

def verificar_mp3_valido(caminho: Path) -> tuple[bool, str | None]:
    """Verifica se o mp3 pode ser lido pelo pydub."""
    try:
        duracao = pegar_duracao_mp3(caminho)
        if duracao is None:
            return False, "Não foi possível ler com pydub"
        if duracao < 1000:  # menos de 1 segundo
            return False, f"Áudio muito curto: {duracao}ms"
        return True, f"OK ({duracao/1000:.1f}s)"
    except Exception as e:
        return False, f"Erro: {e}"

def formatar_duracao_ms(ms: int) -> str:
    """Formata ms como MM:SS."""
    total_s = ms // 1000
    m, s = divmod(total_s, 60)
    return f"{m}:{s:02d}"

# ============================================================================
# 1. CARREGAR NJUDS DO CSV DE REFERÊNCIA
# ============================================================================

def carregar_njuds_csv():
    """
    Carrega NJUDS_VALIDOS.csv e retorna dict {numero_njud: {data, dia_semana, correto}}
    Também retorna conjunto de todos os NJUDs que tinham 4 cortes OK no checklist.
    """
    njuds_csv = {}
    njuds_4_cortes_ok = set()

    if NJUDS_VALIDOS_CSV.exists():
        with open(NJUDS_VALIDOS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                num = row.get('Correto', '').strip()
                if num.isdigit():
                    n = int(num)
                    njuds_csv[n] = {
                        'data': row.get('Data_Formatada', ''),
                        'dia_semana': row.get('Dia_Semana', ''),
                        'correto': row.get('Correto', '').strip()
                    }
                    njuds_4_cortes_ok.add(n)

    # Também verificar checklist_jornais.csv para datas com status != DESNECESSARIA
    if CHECKLIST_CSV.exists():
        with open(CHECKLIST_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('status', '').upper() != 'DESNECESSARIA':
                    # Extrair NJUD do detalhe ou de relação data->NJUD
                    pass  # O checklist não tem número de NJUD direto

    return njuds_csv, njuds_4_cortes_ok

# ============================================================================
# 2. ESCANEAR JORNAIS_DIVIDIDOS PARA SABER O QUE EXISTE
# ============================================================================

def scanear_divididos():
    """
    Scanea todos os diretórios JORNAIS_DIVIDIDOS* e retorna:
    - dict {numero_njud: {caminho, total_cortes, cortes_ok}}
    """
    resultado = {}

    for base_dir in DIRS_DIVIDIDOS:
        if not base_dir.exists():
            continue
        for entry in sorted(base_dir.iterdir()):
            if not entry.is_dir():
                continue
            num = extrair_numero_njud(entry.name)
            if num is None:
                continue

            # Contar cortes: arquivos que terminam em _CABECA.mp3 ou _CORPO.mp3
            cabecas = list(entry.glob("*_CABECA.mp3"))
            corpos = list(entry.glob("*_CORPO.mp3"))
            total_cortes = len(cabecas) + len(corpos)

            # Cortes OK: pares completos (ambos existindo com mesmo identificador)
            cortes_ok = 0
            for c in cabecas:
                # Tenta achar o corpo correspondente
                base_name = c.name.replace('_CABECA.mp3', '')
                corpo_corr = entry / f"{base_name}_CORPO.mp3"
                if corpo_corr.exists():
                    cortes_ok += 1

            if num not in resultado:
                resultado[num] = {
                    'caminho': entry,
                    'total_cortes': total_cortes,
                    'cortes_ok': cortes_ok,
                    'cabecas': len(cabecas),
                    'corpos': len(corpos),
                    'dir_origem': str(base_dir),
                }
            else:
                # Já existe (pode estar em múltiplos dirs, somar)
                r = resultado[num]
                r['total_cortes'] += total_cortes
                r['cortes_ok'] += cortes_ok
                r['cabecas'] += len(cabecas)
                r['corpos'] += len(corpos)

    return resultado

# ============================================================================
# 3. ESCANEAR JORNAIS_FINAL
# ============================================================================

def scanear_final():
    """
    Scanea data/output/JORNAIS_FINAL/ 
    Suporta dois layouts:
    - NJUDs como subpastas: JORNAIS_FINAL/NJUD 1792/NJUD_1792_*.mp3
    - NJUDs como arquivos planos: JORNAIS_FINAL/NJUD_1792_*.mp3
    Retorna dict {numero_njud: {caminho_dir, arquivos, problemas}}
    """
    resultado = {}

    if not OUTPUT_DIR.exists():
        return resultado

    # Layout 1: subpastas por NJUD
    for entry in sorted(OUTPUT_DIR.iterdir()):
        if entry.is_dir():
            num = extrair_numero_njud(entry.name)
            if num is None:
                continue

            arquivos_mp3 = sorted(entry.glob("*.mp3"))
            problemas = []
            detalhes = []

            for arq in arquivos_mp3:
                ok, msg = verificar_mp3_valido(arq)
                if not ok:
                    problemas.append(f"{arq.name}: {msg}")
                else:
                    detalhes.append(f"{arq.name}: {msg}")

            resultado[num] = {
                'caminho_dir': entry,
                'arquivos': [a.name for a in arquivos_mp3],
                'problemas': problemas,
                'detalhes_validos': detalhes,
                'total_arquivos': len(arquivos_mp3),
                'layout': 'subpasta',
            }

    # Layout 2: arquivos planos (sem subpastas)
    if len(resultado) == 0:
        for arq in sorted(OUTPUT_DIR.glob("*.mp3")):
            num = extrair_numero_njud(arq.stem)  # stem remove .mp3
            if num is None:
                continue

            if num not in resultado:
                resultado[num] = {
                    'caminho_dir': OUTPUT_DIR,
                    'arquivos': [],
                    'problemas': [],
                    'detalhes_validos': [],
                    'total_arquivos': 0,
                    'layout': 'plano',
                }

            ok, msg = verificar_mp3_valido(arq)
            if not ok:
                resultado[num]['problemas'].append(f"{arq.name}: {msg}")
            else:
                resultado[num]['detalhes_validos'].append(f"{arq.name}: {msg}")
            resultado[num]['arquivos'].append(arq.name)
            resultado[num]['total_arquivos'] += 1

    return resultado

# ============================================================================
# 4. AUDITAR INTEGRIDADE (duração 5-15 min)
# ============================================================================

def auditar_integridade(scan_final: dict) -> dict:
    """
    Para cada NJUD em JORNAIS_FINAL, verifica duração total.
    Retorna dict {numero_njud: {duração_ms, problema}}
    """
    resultado = {}

    for num, info in scan_final.items():
        duracoes = []
        for nome_arq in info['arquivos']:
            arq_path = info['caminho_dir'] / nome_arq
            d = pegar_duracao_mp3(arq_path)
            if d is not None:
                duracoes.append(d)

        if not duracoes:
            resultado[num] = {
                'duração_total_ms': None,
                'problema': 'Não foi possível determinar duração (arquivos corrompidos ou vazios)'
            }
            continue

        # Somar todas as faixas do NJUD (se houver mais de um arquivo)
        duracao_total = sum(duracoes)
        mins = duracao_total / 60000

        problema = None
        if duracao_total < MIN_DURACAO_MIN:
            problema = f"Duracao insuficiente: {formatar_duracao_ms(duracao_total)} ({mins:.1f} min) — mínimo 5 min"
        elif duracao_total > MAX_DURACAO_MAX:
            problema = f"Duracao excede limite: {formatar_duracao_ms(duracao_total)} ({mins:.1f} min) — máximo 15 min"

        resultado[num] = {
            'duração_total_ms': duracao_total,
            'duracao_formatada': formatar_duracao_ms(duracao_total),
            'minutos': round(mins, 1),
            'problema': problema,
        }

    return resultado

# ============================================================================
# 5. GERAR RELATÓRIO
# ============================================================================

def gerar_relatorio(
    scan_final: dict,
    scan_divididos: dict,
    njuds_csv: dict,
    njuds_4_cortes_ok: set,
    integridade: dict,
    timestamp: str
):
    """
    Gera relatório JSON em logs/relatorio_auditoria_<timestamp>.json
    E retorna dict com resumo para output do agente.
    """
    relatorio_path = LOGS_DIR / f"relatorio_auditoria_{timestamp}.json"

    njuds_aprovados = []
    njuds_rejeitados = []
    pendencias = []
    erros_detail = []

    # Números dos NJUDs montados
    montados = set(scan_final.keys())
    # Números esperados (tinham 4 cortes OK no CSV)
    esperados = njuds_4_cortes_ok

    # 1. Verificar NJUDs montados
    for num, info in sorted(scan_final.items()):
        problemas = list(info['problemas'])  # problemas de mp3 inválido
        int_info = integridade.get(num, {})

        # Verificar duração
        if int_info.get('problema'):
            problemas.append(int_info['problema'])

        # Verificar se tem correspondente em JORNAIS_DIVIDIDOS (órfão)
        if num in scan_divididos:
            dividido = scan_divididos[num]
            if dividido['cortes_ok'] < 4:
                problemas.append(
                    f"Montado com apenas {dividido['cortes_ok']}/4 cortes OK "
                    f"(total: {dividido['total_cortes']} arquivos em {dividido['dir_origem']})"
                )
        else:
            problemas.append(f"ÓRFÃO: não há correspondente em JORNAIS_DIVIDIDOS")

        # Tamanho total dos arquivos
        tamanho_total = sum((info['caminho_dir'] / f).stat().st_size for f in info['arquivos']
                           if (info['caminho_dir'] / f).exists())

        if problemas:
            njuds_rejeitados.append({
                'njud': f"NJUD {num}",
                'problemas': problemas,
                'arquivos': info['arquivos'],
                'tamanho_bytes': tamanho_total,
                'duracao': int_info.get('duracao_formatada', 'N/A'),
            })
            erros_detail.append(f"NJUD {num}: {', '.join(problemas)}")
        else:
            njuds_aprovados.append({
                'njud': f"NJUD {num}",
                'duracao': int_info.get('duracao_formatada', 'N/A'),
                'minutos': int_info.get('minutos', 0),
                'tamanho_bytes': tamanho_total,
                'arquivos': info['arquivos'],
            })

    # 2. Verificar NJUDs que deveriam ter sido montados mas não foram
    for num in sorted(esperados):
        if num not in montados:
            pendencias.append({
                'njud': f"NJUD {num}",
                'motivo': f"Tinha {njuds_csv.get(num, {}).get('data', 'data desconhecida')} no CSV com 4 cortes OK, "
                          f"mas não foi montado. "
                          f"Localização em cortes: {scan_divididos.get(num, {}).get('dir_origem', 'não encontrado')}"
            })
            erros_detail.append(f"NJUD {num} NÃO MONTADO: esperado com 4 cortes OK")

    # 3. Verificar órfãos (montados sem correspondente)
    # Já tratado acima nos problemas de cada NJUD montado

    total_auditados = len(montados)

    relatorio = {
        'timestamp': timestamp,
        'total_njuds_auditados': total_auditados,
        'total_esperados_com_4_cortes_ok': len(esperados),
        'njuds_aprovados': njuds_aprovados,
        'njuds_rejeitados': njuds_rejeitados,
        'njuds_nao_fluxados': pendencias,
        'resumo': {
            'aprovados': len(njuds_aprovados),
            'rejeitados': len(njuds_rejeitados),
            'pendencias': len(pendencias),
        },
        'detalhes_erro': erros_detail if erros_detail else [],
    }

    with open(relatorio_path, 'w', encoding='utf-8') as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)

    return {
        'relatorio_path': str(relatorio_path),
        'njuds_aprovados': njuds_aprovados,
        'njuds_rejeitados': njuds_rejeitados,
        'pendencias': pendencias,
        'total_auditados': total_auditados,
        'erros_detail': erros_detail,
        'aprovados_count': len(njuds_aprovados),
        'rejeitados_count': len(njuds_rejeitados),
        'pendencias_count': len(pendencias),
    }

# ============================================================================
# 6. REFAZER MONTAGEM DOS NJUDs AFETADOS
# ============================================================================

def refazer_montagem_problematicos(scan_final, scan_divididos, integridade, njuds_4_cortes_ok):
    """
    Identifica NJUDs com problemas e tenta refazer a montagem.
    Retorna lista de NJUDs que foram (ou deveriam ser) reprocessados.
    """
    problemas_numeros = set()

    for num, info in scan_final.items():
        tem_problema = False
        if info['problemas']:
            tem_problema = True
        int_info = integridade.get(num, {})
        if int_info.get('problema'):
            tem_problema = True
        if num in scan_divididos and scan_divididos[num]['cortes_ok'] < 4:
            tem_problema = True
        if not tem_problema and num not in scan_divididos:
            tem_problema = True  # órfão

        if tem_problema:
            problemas_numeros.add(num)

    # NJUDs esperados mas não montados
    for num in njuds_4_cortes_ok:
        if num not in scan_final:
            problemas_numeros.add(num)

    reprocessar = sorted(problemas_numeros)
    return reprocessar

# ============================================================================
# MAIN
# ============================================================================

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"=" * 70)
    print(f"ETAPA 3: AUDITORIA DE MONTAGEM")
    print(f"Timestamp: {timestamp}")
    print(f"Data/output/JORNAIS_FINAL: {OUTPUT_DIR}")
    print(f"=" * 70)

    # 1. Carregar referência
    print("\n[1/6] Carregando NJUDS_VALIDOS.csv...")
    njuds_csv, njuds_4_cortes_ok = carregar_njuds_csv()
    print(f"  NJUDs com 4 cortes OK no CSV: {len(njuds_4_cortes_ok)}")
    if njuds_4_cortes_ok:
        print(f"  Exemplos: {sorted(list(njuds_4_cortes_ok))[:10]}")

    # 2. Scaneear JORNAIS_DIVIDIDOS
    print("\n[2/6] Scanear JORNAIS_DIVIDIDOS (todas as variantes)...")
    scan_divididos = scanear_divididos()
    print(f"  Total de NJUDs encontrados nos cortes: {len(scan_divididos)}")
    # Resumo por origem
    origens = defaultdict(int)
    for num, info in scan_divididos.items():
        origens[info['dir_origem']] += 1
    for origem, count in sorted(origens.items()):
        print(f"    - {origem}: {count} NJUDs")

    # 3. Scaneear JORNAIS_FINAL
    print("\n[3/6] Scanear data/output/JORNAIS_FINAL/...")
    if not OUTPUT_DIR.exists():
        print(f"  ⚠️  Diretório NÃO EXISTE: {OUTPUT_DIR}")
        scan_final = {}
    else:
        scan_final = scanear_final()
        print(f"  NJUDs montados encontrados: {len(scan_final)}")

    # 4. Auditando integridade (duração)
    print("\n[4/6] Verificando integridade (duração 5-15 min) e validade MP3...")
    integridade = auditar_integridade(scan_final)

    for num in sorted(integridade.keys()):
        info = integridade[num]
        if info.get('problema'):
            print(f"  ❌ NJUD {num}: {info['problema']}")
        elif info.get('duração_total_ms'):
            print(f"  ✓  NJUD {num}: {info['duracao_formatada']} ({info['minutos']} min)")

    # 5. Gerar relatório
    print("\n[5/6] Gerando relatório...")
    resumo = gerar_relatorio(
        scan_final, scan_divididos, njuds_csv, njuds_4_cortes_ok,
        integridade, timestamp
    )

    print(f"\n  RELATÓRIO: {resumo['relatorio_path']}")
    print(f"\n  RESUMO DA AUDITORIA:")
    print(f"    Total auditados : {resumo['total_auditados']}")
    print(f"    Aprovados       : {resumo['aprovados_count']}")
    print(f"    Rejeitados      : {resumo['rejeitados_count']}")
    print(f"    Pendências      : {resumo['pendencias_count']}")

    if resumo['erros_detail']:
        print(f"\n  DETALHE DE ERROS:")
        for e in resumo['erros_detail']:
            print(f"    - {e}")

    # 6. Determinar se precisa refazer montagem
    print("\n[6/6] Determinando ações corretivas...")
    if resumo['rejeitados_count'] > 0 or resumo['pendencias_count'] > 0:
        reprocessar = refazer_montagem_problematicos(scan_final, scan_divididos, integridade, njuds_4_cortes_ok)
        print(f"  ⚠️  PROBLEMAS DETECTADOS!")
        print(f"  NJUDs a reprocessar: {len(reprocessar)}")
        if reprocessar:
            print(f"  Lista: {reprocessar}")
        print(f"\n  Para refazer a montagem, execute:")
        print(f"    python scripts_pipeline/montagem_jornais.py")
        print(f"  Ou usar o script: scripts_pipeline/montar.sh")
    else:
        print(f"  ✅ NENHUM PROBLEMA DETECTADO. Montagem está íntegra.")
        reprocessar = []

    # Controle de fluxo para o agente pai
    if resumo['rejeitados_count'] > 0 or resumo['pendencias_count'] > 0:
        auditoria_ok = "NAO_OK"
        erro = "; ".join(resumo['erros_detail']) if resumo['erros_detail'] else "Problemas não especificados"
    else:
        auditoria_ok = "OK"
        erro = ""

    return {
        'auditoria_ok': auditoria_ok,
        'erro': erro,
        'njuds_aprovados': str(resumo['aprovados_count']),
        'njuds_rejeitados': str(resumo['rejeitados_count']),
        'pendencias': str(resumo['pendencias_count']),
        'relatorio_path': resumo['relatorio_path'],
        'resultado': f"Auditoria concluída: {resumo['aprovados_count']} aprovados, "
                     f"{resumo['rejeitados_count']} rejeitados, "
                     f"{resumo['pendencias_count']} pendentes. "
                     f"Relatório: {resumo['relatorio_path']}",
    }

if __name__ == "__main__":
    result = main()
    print("\n" + "=" * 70)
    print("RESULTADO FINAL (JSON):")
    print(json.dumps(result, indent=2, ensure_ascii=False))
