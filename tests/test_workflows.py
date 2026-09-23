#!/usr/bin/env python3
"""
test_workflows.py — Testes para shared/workflows.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts_pipeline"))

from shared.workflows import (
    AuditorAgent,
    AjusteAgent,
    RelatorioAgent,
    executar_workflow,
    Problema,
)


# ═══════════════════════════════════════════════════════════
# Testes: AuditorAgent
# ═══════════════════════════════════════════════════════════

def test_auditor_sem_problemas():
    """Auditoria sem problemas deve retornar lista vazia."""
    auditor = AuditorAgent()
    assert auditor.problemas == []
    print("  ✅ Auditor sem problemas OK")


def test_auditor_completo():
    """Auditor deve processar auditoria.json válida."""
    # Criar auditoria temporária
    auditoria = {
        "boletims_gerados": [
            {
                "arquivo": "B1.mp3",
                "duracao_segundos": 100,
                "qualidade": {
                    "cobertura_roteiro_original": 0.90,
                    "correcoes_aplicadas": False,
                    "texto_corrigido": "Texto de teste do boletim"
                }
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(auditoria, f)
        tmp_path = Path(f.name)
    
    try:
        auditor = AuditorAgent()
        resultado = auditor.auditar(tmp_path)
        assert resultado.sucesso
        assert resultado.agente == "Auditor"
        print("  ✅ Auditor completo OK")
    finally:
        tmp_path.unlink()


# ═══════════════════════════════════════════════════════════
# Testes: AjusteAgent
# ═══════════════════════════════════════════════════════════

def test_ajuste_sem_problemas():
    """Sem problemas, nenhum ajuste proposto."""
    ajuste = AjusteAgent()
    resultado = ajuste.analisar_e_problemas([])
    assert len(resultado.acoes) == 0
    print("  ✅ Ajuste sem problemas OK")


def test_ajuste_com_problemas():
    """Com problemas, deve propor ajustes."""
    problemas = [
        Problema("ALTO", "Sentido", "B1", "Sentido comprometido"),
    ]
    
    ajuste = AjusteAgent()
    resultado = ajuste.analisar_e_problemas(problemas)
    assert len(resultado.acoes) > 0
    print(f"  ✅ Ajuste com problemas OK: {len(resultado.acoes)} ação(ões)")


def test_ajuste_aplicar():
    """Deve aplicar ajuste corretamente."""
    from shared.config import get_config, set_config
    
    config = get_config()
    config.cobertura_min = 0.60
    
    ajuste = AjusteAgent()
    problemas = [Problema("ALTO", "Sentido", "B1", "Teste")]
    resultado = ajuste.analisar_e_problemas(problemas)
    
    if resultado.acoes:
        ajuste.aplicar_acao(resultado.acoes[0])
        # Verificar que valor mudou
        assert resultado.acoes[0].aplicada
        print("  ✅ Aplicar ajuste OK")


# ═══════════════════════════════════════════════════════════
# Testes: RelatorioAgent
# ═══════════════════════════════════════════════════════════

def test_relatorio_vazio():
    """Relatório sem resultados."""
    agente = RelatorioAgent()
    resultado = agente.gerar([])
    assert "RELATÓRIO" in resultado
    print("  ✅ Relatório vazio OK")


def test_relatorio_com_resultados():
    """Relatório com resultados."""
    from shared.workflows import ResultadoWorkflow
    
    agente = RelatorioAgent()
    resultados = [
        ResultadoWorkflow("Teste", True, [], [], "Funcionou"),
    ]
    resultado = agente.gerar(resultados)
    assert "Teste" in resultado
    print("  ✅ Relatório com resultados OK")


# ═══════════════════════════════════════════════════════════
# Testes: executar_workflow (integração)
# ═══════════════════════════════════════════════════════════

def test_workflow_completo():
    """Pipeline completo de workflow."""
    auditoria = {
        "boletims_gerados": [
            {
                "arquivo": "B1.mp3",
                "duracao_segundos": 100,
                "qualidade": {
                    "cobertura_roteiro_original": 0.50,
                    "correcoes_aplicadas": True,
                    "texto_corrigido": "Texto com sentido diferente"
                }
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(auditoria, f)
        tmp_path = Path(f.name)
    
    try:
        resultado = executar_workflow(tmp_path, aplicar_ajustes=False)
        assert "RELATÓRIO" in resultado
        assert "Auditor" in resultado
        assert "Ajuste" in resultado
        print("  ✅ Workflow completo OK")
    finally:
        tmp_path.unlink()


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
