"""
core/governanca/regras_regressao.py

Versão EXECUTÁVEL das decisões documentadas em DECISOES.md. Cada função
`checar_item_N` corresponde a um item do arquivo e retorna
(ok: bool, detalhe: str). Isto é o "portão de regressão" citado na
arquitetura: roda antes de qualquer promoção de heurística nova do
Analisador, e pode ser plugado no auditor_service como mais uma
categoria de regra (regra de CÓDIGO, não de áudio).

Não substitui DECISOES.md — o "porquê" continua lá, legível por humano.
Este arquivo é o "sim/não, a máquina confirma" complementar.

Uso:
    python -m core.governanca.regras_regressao --raiz /caminho/do/DIVISOR

Saída: lista de OK/FALHOU por item, exit code != 0 se algo falhar
(pode ser plugado num hook de pre-commit ou no CI local).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable

Resultado = tuple[bool, str]


def checar_item_2_convencao_data(raiz: Path) -> Resultado:
    """
    DECISOES.md item 2: nome de arquivo de boletim é DD_MM_AAAA, nunca
    MM_DD_AAAA. Aqui não conseguimos provar semântica sem o dado real,
    mas podemos garantir que nenhum script "vivo" (fora de área de
    quarentena/arquivo morto) usa o padrão de parsing invertido
    conhecido do incidente de 2026-09-09 (grupos capturados como MM,DD).
    """
    padrao_suspeito = re.compile(r"BOLETIM_RADIO_TJRN_\(MM\)_\(DD\)|mes.*=.*group\(1\).*dia.*=.*group\(2\)")
    ofensores = []
    for py in raiz.rglob("*.py"):
        if _em_area_ignorada(py):
            continue
        try:
            texto = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if padrao_suspeito.search(texto):
            ofensores.append(str(py))
    if ofensores:
        return False, f"Padrão de data invertido (MM_DD) encontrado em: {ofensores}"
    return True, "Nenhum script vivo com parsing de data invertido encontrado."


def checar_item_3_dry_run_padrao(raiz: Path) -> Resultado:
    """
    DECISOES.md item 3: scripts que tocam em disco em lote devem ter
    --dry-run como padrão e exigir --apply explícito para executar.
    Heurística: procura scripts que chamam shutil.rmtree/os.remove em
    lote sem checar um argparse com --apply nas proximidades.
    """
    ofensores = []
    for py in raiz.rglob("*.py"):
        if _em_area_ignorada(py):
            continue
        try:
            texto = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        usa_delete_em_lote = ("shutil.rmtree" in texto or "Remove-Item" in texto)
        tem_flag_apply = ("--apply" in texto or "apply" in texto.lower())
        if usa_delete_em_lote and not tem_flag_apply:
            ofensores.append(str(py))
    if ofensores:
        return False, f"Scripts com deleção em lote sem flag --apply visível: {ofensores}"
    return True, "Scripts com deleção em lote possuem indício de flag --apply."


def checar_item_h_leitura(raiz: Path) -> Resultado:
    """
    Regra inegociável do README/PROCEDIMENTO_PADRAO: H: é somente leitura
    exceto core/sync (ou src/sync/drive.py). Verifica que nenhum arquivo
    fora de sync/ contém operações de escrita (Move-Item, Remove-Item,
    shutil.move/rmtree) apontando literalmente para "H:" ou "H:\\".
    """
    padrao_escrita_h = re.compile(r"(Move-Item|Remove-Item|shutil\.move|shutil\.rmtree)[^\n]{0,80}H:\\\\?")
    ofensores = []
    for arq in list(raiz.rglob("*.py")) + list(raiz.rglob("*.ps1")) + list(raiz.rglob("*.sh")):
        if "sync" in arq.parts or _em_area_ignorada(arq):
            continue
        try:
            texto = arq.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if padrao_escrita_h.search(texto):
            ofensores.append(str(arq))
    if ofensores:
        return False, f"Escrita direta em H: fora de sync/: {ofensores}"
    return True, "Nenhuma escrita direta em H: fora da área de sync."


def checar_item_regra_sem_fallback_obrigatoria(raiz: Path) -> Resultado:
    """
    core/auditoria/regras.py deve sempre incluir RegraSemFallbackParaAudioCompleto
    na lista padrão do Auditor — ela é textualmente marcada como
    "não pode ser desativada". Falha se o Auditor for encontrado sem ela.
    """
    candidatos = list(raiz.rglob("regras.py"))
    for arq in candidatos:
        if "auditoria" not in str(arq):
            continue
        texto = arq.read_text(encoding="utf-8", errors="ignore")
        if "class Auditor" in texto and "RegraSemFallbackParaAudioCompleto" not in texto:
            return False, f"Auditor em {arq} não referencia RegraSemFallbackParaAudioCompleto."
    return True, "RegraSemFallbackParaAudioCompleto presente onde o Auditor é definido."


def _em_area_ignorada(caminho: Path) -> bool:
    partes = set(caminho.parts)
    return bool(partes & {".git", "node_modules", "__pycache__", "_arquivo_morto_logs", "quarentena"})


REGRAS: dict[str, Callable[[Path], Resultado]] = {
    "item_2_convencao_data": checar_item_2_convencao_data,
    "item_3_dry_run_padrao": checar_item_3_dry_run_padrao,
    "item_h_somente_leitura": checar_item_h_leitura,
    "regra_sem_fallback_obrigatoria": checar_item_regra_sem_fallback_obrigatoria,
}


def rodar_portao(raiz: Path) -> bool:
    """Roda todas as regras de regressão. Retorna True só se todas passarem."""
    tudo_ok = True
    for nome, fn in REGRAS.items():
        ok, detalhe = fn(raiz)
        status = "OK" if ok else "FALHOU"
        print(f"[{status}] {nome}: {detalhe}")
        tudo_ok = tudo_ok and ok
    return tudo_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Portão de regressão executável (DECISOES.md).")
    parser.add_argument("--raiz", type=Path, default=Path("."))
    args = parser.parse_args()

    ok = rodar_portao(args.raiz)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
