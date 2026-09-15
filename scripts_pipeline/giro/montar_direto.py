# -*- coding: utf-8 -*-
"""Montagem direta dos programas GIRO a partir dos cortes BOLETIM_RADIO_TJRN.

Usa src/giro/montagem.py::montar_programa para consolidação,
com persistência de estado para não-regressão.

Receita (conforme especificação do usuário):
    1. VHT_ABERTURA_GIRO (vinheta de abertura ~17s)
    2. Para cada nota (4-6 notas):
       a. Nota (manchete + corpo integrados, ~12-15s cada)
       b. VHT_PASSAGEM_GIRO (só entre notas, ~1.2s)
    3. VHT_ENCERRAMENTO_GIRO (vinheta de encerramento ~12.6s)

Regras:
    - Passagem só entre notas (não antes da primeira nem após a última)
    - Mínimo 4, máximo 6 notas
    - Vinhetas livres de conteúdo de boletim original
    - Estado persistido para evitar regressões
"""
from __future__ import annotations

import json
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pydub import AudioSegment
from pydub.effects import normalize

from giro.config import DIR_OUTPUT, VHT_ABERTURA_GIRO_NOME, VHT_PASSAGEM_GIRO_NOME, VHT_ENCERRAMENTO_GIRO_NOME
from giro.montagem import montar_programa, _carregar_vinheta
from giro.utils import terça_do_programa

# ============================================================================
# CONSTANTS
# ============================================================================
BASE_DIR = Path(__file__).resolve().parents[2]
ESTADO_DIR = BASE_DIR / "data" / "processed" / "PRODUCAO_2026" / "estado_montagem"
MIN_NOTAS = 4
MAX_NOTAS = 6

# Mapeamento programa -> data de exibição (terça-feira semanal)
# Formato: DD-MM-AAAA
# Corrigido: exibição é na TERÇA, não na quarta
PROGRAMAS = {
    "0101": "06-01-2026", "0102": "13-01-2026",
    "0103": "20-01-2026", "0104": "27-01-2026",
    "0201": "03-02-2026", "0202": "10-02-2026",
    "0301": "03-03-2026", "0302": "10-03-2026",
    "0303": "17-03-2026", "0304": "24-03-2026",
    "0401": "07-04-2026", "0402": "14-04-2026",
    "0403": "21-04-2026", "0404": "28-04-2026",
    "0501": "05-05-2026", "0502": "12-05-2026",
    "0503": "19-05-2026", "0504": "26-05-2026",
    "0601": "02-06-2026", "0602": "09-06-2026",
    "0603": "16-06-2026", "0604": "23-06-2026",
    "0701": "07-07-2026", "0702": "14-07-2026",
    "0703": "21-07-2026", "0704": "28-07-2026",
    "0705": "04-08-2026", "0706": "11-08-2026",
    "0801": "04-08-2026", "0802": "11-08-2026",
    "0803": "18-08-2026", "0804": "25-08-2026",
}

# ============================================================================
# PERSISTÊNCIA
# ============================================================================

def carregar_estado_montagem(programa: str) -> dict:
    """Carrega estado de montagem de um programa."""
    caminho = ESTADO_DIR / f"{programa}.json"
    if caminho.exists():
        try:
            with open(caminho) as f:
                return json.load(f)
        except Exception:
            pass
    return {"programa": programa, "montado": False, "notas": [], "data": None}


def salvar_estado_montagem(programa: str, estado: dict) -> None:
    """Persiste estado de montagem de um programa."""
    ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    caminho = ESTADO_DIR / f"{programa}.json"
    with open(caminho, "w") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


def montagem_ja_feita(programa: str) -> bool:
    """Verifica se o programa já foi montado (não-regressão)."""
    estado = carregar_estado_montagem(programa)
    return estado.get("montado", False) and estado.get("notas", [])


# ============================================================================
# MONTAGEM
# ============================================================================

def montar_programa_direto(programa: str) -> bool:
    """Monta um programa GIRO usando os cortes processados.

    Args:
        programa: código do programa (ex: "0101")

    Returns:
        True se montado com sucesso
    """
    # Check persistence (não-regressão)
    if montagem_ja_feita(programa):
        print(f"  {programa}: já montado (persistência), pulando...")
        return True

    data_terça = PROGRAMAS.get(programa)
    if not data_terça:
        print(f"  ERRO: {programa} não tem data mapeada!")
        return False

    mmss = programa
    # data_terça já está no formato DD-MM-AAAA (padrão do dict PROGRAMAS)
    data_terça_obj = data_terça

    # Encontrar notas processadas para este programa
    pasta_notas = BASE_DIR / "data" / "processed" / "PRODUCAO_2026" / "GIRO_COMARCAS" / mmss

    if not pasta_notas.exists():
        print(f"  ERRO: pasta de notas não existe: {pasta_notas}")
        return False

    notas = sorted(pasta_notas.glob("*.mp3"))
    if not notas:
        notas = sorted(pasta_notas.glob("*.wav"))

    if len(notas) < MIN_NOTAS:
        print(f"  ERRO: {programa} tem {len(notas)} notas (mínimo {MIN_NOTAS}) — montagem impedida")
        return False

    if len(notas) > MAX_NOTAS:
        print(f"  AVISO: {programa} tem {len(notas)} notas (máximo {MAX_NOTAS}), usando primeiras {MAX_NOTAS}")
        notas = notas[:MAX_NOTAS]

    if not notas:
        print(f"  ERRO: nenhuma nota encontrada para {programa}")
        return False

    print(f"  {programa}: montando {len(notas)} notas (data: {data_terça})...")

    try:
        # Usar montar_programa do src/giro/montagem.py (agora com fix de passagem)
        caminho = montar_programa(
            mmss=mmss,
            notas=notas,
            data_terça=None,  # será calculado internamente por terça_do_programa
        )

        if caminho and caminho.exists():
            duracao = len(AudioSegment.from_file(str(caminho))) / 1000
            # Persistir estado
            estado = {
                "programa": programa,
                "montado": True,
                "notas": [n.name for n in notas],
                "data": data_terça,
                "duracao": duracao,
                "caminho": str(caminho),
                "status": "concluido",
            }
            salvar_estado_montagem(programa, estado)
            print(f"  {programa}: montado com sucesso ({len(notas)} notas, {duracao:.1f}s)")
            return True
        else:
            print(f"  ERRO: montar_programa retornou None para {programa}")
            return False

    except Exception as e:
        print(f"  ERRO: {e}")
        # Fallback: montagem manual
        return montar_manual(programa, notas, mmss, data_terça_obj)


def montar_manual(programa: str, notas: list[Path], mmss: str, data_terça_obj) -> bool:
    """Montagem manual quando montar_programa falha.

    Receita correta:
        VHT_ABERTURA + NOTA1 + PASSAGEM + NOTA2 + PASSAGEM + ... + VHT_ENCERRAMENTO
    """
    print(f"  {programa}: usando montagem manual...")

    try:
        vht_abertura = _carregar_vinheta(VHT_ABERTURA_GIRO_NOME, "montagem_manual")
        vht_passagem = _carregar_vinheta(VHT_PASSAGEM_GIRO_NOME, "montagem_manual")
        vht_encerramento = _carregar_vinheta(VHT_ENCERRAMENTO_GIRO_NOME, "montagem_manual")
    except Exception as e:
        print(f"  ERRO ao carregar vinhetas: {e}")
        return False

    if not all([vht_abertura, vht_passagem, vht_encerramento]):
        print(f"  ERRO: vinhetas não encontradas")
        return False

    programa_audio = AudioSegment.empty()
    programa_audio += vht_abertura

    for i, nota_path in enumerate(notas):
        if i > 0:  # Passagem só entre notas
            programa_audio += vht_passagem
        nota_audio = AudioSegment.from_file(str(nota_path))
        nota_audio = normalize(nota_audio)
        programa_audio += nota_audio

    programa_audio += vht_encerramento

    # Salvar
    pasta_saida = DIR_OUTPUT
    pasta_saida.mkdir(parents=True, exist_ok=True)

    from giro.utils import nome_programa
    # Nome do arquivo: usar PROGRAMAS[mmss] diretamente (formato DD-MM-AAAA já correto)
    nome_arq = "GNC_{}_{}.mp3".format(mmss, data_terça)  # data_terça = PROGRAMAS[mmss] = "DD-MM-AAAA"
    caminho_saida = pasta_saida / nome_arq
    programa_audio.export(str(caminho_saida), format="mp3")

    duracao = len(programa_audio) / 1000
    estado = {
        "programa": programa,
        "montado": True,
        "notas": [n.name for n in notas],
        "data": str(data_terça_obj),
        "duracao": duracao,
        "caminho": str(caminho_saida),
        "status": "concluido_manual",
    }
    salvar_estado_montagem(programa, estado)
    print(f"  {programa}: montado manualmente -> {nome_arq}")
    return True


# ============================================================================
# EXECUÇÃO
# ============================================================================

def main():
    print("=" * 60)
    print("MONTAGEM DIRETA DOS PROGRAMAS GIRO")
    print("=" * 60)

    ESTADO_DIR.mkdir(parents=True, exist_ok=True)

    n_montados = 0
    n_faltantes = 0

    for programa in sorted(PROGRAMAS.keys()):
        if montagem_ja_feita(programa):
            n_montados += 1
            print(f"  {programa}: [PERSISTENCIA] Já montado")
        else:
            n_faltantes += 1
            sucesso = montar_programa_direto(programa)
            if sucesso:
                n_montados += 1

    print()
    print(f"=== RESUMO ===")
    print(f"  Total de programas: {len(PROGRAMAS)}")
    print(f"  Já montados (persistência): {n_montados}")
    print(f"  Novamente montados: {n_montados - sum(1 for p in PROGRAMAS if montagem_ja_feita(p))}")
    print(f"  Faltantes: {n_faltantes}")

    # Sincronizar com H:
    destino = Path("H:/Meu Drive/RADIO TJRN CONTEÚDO/00_PRODUCAO_2026/03_GIRO_NAS_COMARCAS")
    if destino.exists():
        sincronizados = 0
        for f in DIR_OUTPUT.glob("GNC_*.mp3"):
            destino_f = destino / f.name
            if not destino_f.exists() or f.stat().st_size != destino_f.stat().st_size:
                shutil.copy2(str(f), str(destino_f))
                sincronizados += 1
        print(f"\n  Sincronizados com H: {sincronizados} arquivos")
    else:
        print(f"\n  ATENÇÃO: destino H: não encontrado")

    return n_montados


if __name__ == "__main__":
    resultado = main()
    print(f"\nConcluído: {resultado} programas montados")
