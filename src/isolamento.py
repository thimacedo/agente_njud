"""
Guard de Isolamento entre Programas — TJRN DIVISOR
===================================================

Valida em tempo de execução que NENHUM script está a escrever fora do
seu diretório de programa. Deve ser importado no início de cada script
de pipeline para garantir isolamento total.

Uso:
    from src.isolamento import guard
    guard.requer_programa("giro")  # Levanta erro se não for GIRO
    
    # Ou validar paths antes de escrever:
    guard.validar_path("data/output/GIRO/0101/cortes/", "giro")
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

# Importar registro canónico
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from registro_programas import (
    TipoPrograma,
    Programa,
    obter_programa,
    STAGING_DIR,
    OUTPUT_DIR,
)

log = logging.getLogger("isolamento")


class IsolamentoError(Exception):
    """Erro de violação de isolamento entre programas."""
    pass


# ===========================================================================
# ESTADO DO GUARD
# ===========================================================================

_programa_ativo: str | None = None


# ===========================================================================
# FUNÇÕES PÚBLICAS
# ===========================================================================

def requer_programa(programa_id: str) -> Programa:
    """
    Define o programa ativo para este contexto.
    
    Deve ser chamado no início de cada script de pipeline.
    Levanta IsolamentoError se já houver outro programa ativo.
    
    Returns:
        Programa config para o id fornecido.
    """
    global _programa_ativo
    
    programa = obter_programa(programa_id)
    
    if _programa_ativo is not None and _programa_ativo != programa_id:
        raise IsolamentoError(
            f"Troca de programa detectada: {_programa_ativo} -> {programa_id}. "
            f"Cada script deve trabalhar com apenas um programa."
        )
    
    _programa_ativo = programa_id
    return programa


@contextmanager
def contexto_programa(programa_id: str):
    """
    Context manager para definir o programa ativo.
    
    Uso:
        with contexto_programa("giro"):
            # código do giro aqui
            pass
    """
    programa = obter_programa(programa_id)
    global _programa_ativo
    anterior = _programa_ativo
    _programa_ativo = programa_id
    try:
        yield programa
    finally:
        _programa_ativo = anterior


def validar_path(caminho: Path | str, programa_id: str | None = None) -> Path:
    """
    Valida que um path está dentro do diretório do programa.
    
    Args:
        caminho: path a validar
        programa_id: programa esperado (usa o ativo se None)
    
    Returns:
        Path absoluto validado
    
    Raises:
        IsolamentoError: se o path não pertencer ao programa
    """
    if programa_id is None:
        programa_id = _programa_ativo
    
    if programa_id is None:
        raise IsolamentoError("Nenhum programa ativo definido. Chame requer_programa() primeiro.")
    
    programa = obter_programa(programa_id)
    caminho_abs = Path(caminho).resolve()
    raiz = Path(__file__).resolve().parent.parent  # DIVISOR/
    
    # Permitidos: pasta do programa em data/output/ ou GIRO/ ou NJUD/ ou BOLETIM/
    caminhos_permitidos = [
        programa.pasta_output,
        programa.pasta_staging,
        programa.pasta_raiz,
        OUTPUT_DIR / programa_id,
        STAGING_DIR / programa_id,
    ]
    
    # Verificar se começa com algum dos caminhos permitidos
    for permitido in caminhos_permitidos:
        permitido_abs = (raiz / permitido).resolve()
        if str(caminho_abs).startswith(str(permitido_abs)):
            return caminho_abs
    
    # Também permitir paths genéricos do projeto (src/, config/, etc.) para leitura
    paths_genericos = [
        raiz / "src",
        raiz / "config",
        raiz / "core",
        raiz / "scripts_pipeline",
    ]
    for generico in paths_genericos:
        if str(caminho_abs).startswith(str(generico)):
            return caminho_abs
    
    raise IsolamentoError(
        f"Path '{caminho}' não pertence ao programa '{programa_id}'. "
        f"Caminhos permitidos: {[str(p) for p in caminhos_permitidos]}"
    )


def validar_janela_datas(
    datas: list[date],
    data_exibicao: date,
    janela_dias: int = 6,
) -> list[str]:
    """
    Valida que todas as datas estão na janela correta ANTERIOR à exibição.
    
    Args:
        datas: datas dos boletins
        data_exibicao: data de exibição do programa
        janela_dias: número de dias na janela (padrão 6)
    
    Returns:
        Lista de erros (vazia = OK)
    """
    erros = []
    
    for d in datas:
        if d >= data_exibicao:
            erros.append(
                f"Boletim {d.strftime('%d-%m-%Y')} é POSTERIOR à exibição "
                f"{data_exibicao.strftime('%d-%m-%Y')}"
            )
        
        diff = (data_exibicao - d).days
        if diff > janela_dias:
            erros.append(
                f"Boletim {d.strftime('%d-%m-%Y')} está fora da janela "
                f"({diff} dias antes, máximo {janela_dias})"
            )
        if diff < 1:
            erros.append(
                f"Boletim {d.strftime('%d-%m-%Y')} é no dia da exibição ou depois"
            )
    
    return erros


def verificar_isolamento_completo() -> dict[str, list[str]]:
    """
    Verifica isolamento completo entre todos os programas.
    
    Returns:
        Dict {programa_id: [erros]}
    """
    erros = {}
    
    for prog_id in ["njud", "giro", "boletim"]:
        prog_erros = []
        try:
            prog = obter_programa(prog_id)
            
            # Verificar que pasta output existe
            if prog.pasta_output.exists():
                # Verificar que não há ficheiros de outros programas
                for ficheiro in prog.pasta_output.rglob("*"):
                    if ficheiro.is_file():
                        nome = ficheiro.name.lower()
                        for outro_id in ["njud", "giro", "boletim"]:
                            if outro_id != prog_id and outro_id in nome:
                                prog_erros.append(
                                    f"Ficheiro de outro programa em output: {ficheiro}"
                                )
        except Exception as e:
            prog_erros.append(f"Erro ao verificar: {e}")
        
        if prog_erros:
            erros[prog_id] = prog_erros
    
    return erros


# ===========================================================================
# DECORADORES
# ===========================================================================

def apenas_para(programa_id: str):
    """
    Decorador que restringe uma função a um programa específico.
    
    Uso:
        @apenas_para("giro")
        def processar_giro():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            requer_programa(programa_id)
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ===========================================================================
# MAIN (verificação rápida)
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("VERIFICAÇÃO DE ISOLAMENTO")
    print("=" * 60)
    
    erros = verificar_isolamento_completo()
    
    if not erros:
        print("✓ Isolamento OK — sem mistura detectada")
    else:
        for prog_id, prog_erros in erros.items():
            print(f"\n[{prog_id}] ERROS:")
            for e in prog_erros:
                print(f"  ✗ {e}")
    
    print("\n" + "=" * 60)
    print("PROGRAMAS REGISTADOS")
    print("=" * 60)
    for prog_id in ["njud", "giro", "boletim"]:
        prog = obter_programa(prog_id)
        print(f"\n[{prog.id}] {prog.nome_completo}")
        print(f"  Output: {prog.pasta_output}")
        print(f"  Staging: {prog.pasta_staging}")
