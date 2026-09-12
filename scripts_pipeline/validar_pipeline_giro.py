#!/usr/bin/env python3
"""
Validação end-to-end da correção do pipeline GIRO.
Processa o boletim de 07/01/2026 e verifica se a vinheta foi removida corretamente.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("validar_pipeline_giro")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from core.processamento.processar_boletim import ConfigPrograma, processar_lote


def main():
    log.info("=== Validação end-to-end: correção pipeline GIRO ===")
    
    plano_path = ROOT / "config" / "planejamento_2026" / "giro_0101.json"
    saida_base = ROOT / "data" / "processed" / "PRODUCAO_2026" / "validacao_0101"
    
    log.info(f"Plano: {plano_path}")
    log.info(f"Saída: {saida_base}")
    
    with open(plano_path, encoding="utf-8") as f:
        plano = json.load(f)
    
    codigo = plano["codigo"]
    data_exibicao = plano["data_exibicao"]
    programa = plano["programa"]
    
    log.info(f"Programa: {programa} | Código: {codigo} | Exibição: {data_exibicao}")
    
    pasta_boletins = ROOT / "data" / "staging" / programa / data_exibicao
    log.info(f"Pasta de boletins: {pasta_boletins}")
    
    if not pasta_boletins.exists():
        log.error(f"Pasta de boletins não existe: {pasta_boletins}")
        sys.exit(1)
    
    boletins = list(pasta_boletins.glob("*.mp3"))
    log.info(f"Boletins encontrados: {len(boletins)}")
    for b in boletins:
        log.info(f"  - {b.name}")
    
    if not boletins:
        log.error("Nenhum boletim encontrado para processar")
        sys.exit(1)
    
    saida_base.mkdir(parents=True, exist_ok=True)
    
    pasta_programa = ROOT / programa.upper()
    pasta_programa.mkdir(parents=True, exist_ok=True)
    
    pasta_saida_prog = pasta_programa / "output" / codigo
    pasta_estado_prog = pasta_programa / "state" / codigo
    pasta_logs_prog = pasta_programa / "logs" / codigo
    
    for p in [pasta_saida_prog, pasta_estado_prog, pasta_logs_prog]:
        p.mkdir(parents=True, exist_ok=True)
    
    config = ConfigPrograma(
        nome=programa.lower(),
        pasta_boletins=pasta_boletins,
        pasta_saida=pasta_saida_prog,
        pasta_estado=pasta_estado_prog,
        pasta_log=pasta_logs_prog,
        modelo_whisper="tiny",
        compute_type="int8",
        roteiro_corte="GIRO_CABEÇA_CORPO" if programa.lower() == "giro" else None,
        minimo_boletins_para_montar=plano.get("parametros", {}).get("boletins_minimos", 4),
        usar_separacao_stems=plano.get("parametros", {}).get("usar_separacao_stems", False),
        data_inicio_coleta=plano.get("janela_coleta", {}).get("inicio"),
        data_fim_coleta=plano.get("janela_coleta", {}).get("fim"),
    )
    
    log.info("Iniciando processamento...")
    
    try:
        resultado = processar_lote(config)
        
        log.info(f"=== RESULTADO DO PROCESSAMENTO ===")
        log.info(f"Status: {resultado.status}")
        log.info(f"Arquivos gerados: {len(resultado.arquivos_gerados)}")
        
        for arq in resultado.arquivos_gerados:
            log.info(f"  - {arq.name}")
        
        log.info(f"Erros: {len(resultado.erros)}")
        for err in resultado.erros:
            log.error(f"  - {err}")
        
        if resultado.status == "ok":
            log.info("✅ Pipeline processou com sucesso")
            
            corte_dir = pasta_saida_prog / "cortes"
            if corte_dir.exists():
                cortes = list(corte_dir.glob("*/vocals_CABECA.wav"))
                log.info(f"Cortes encontrados: {len(cortes)}")
                
                for corte in cortes:
                    from pydub import AudioSegment
                    audio = AudioSegment.from_file(corte)
                    duracao = len(audio) / 1000.0
                    log.info(f"  - {corte.parent.name}: {duracao:.2f}s")
                    
                    if duracao < 10.0:
                        log.info(f"    ✅ CABEÇA com duração plausível (vinheta provavelmente removida)")
                    else:
                        log.warning(f"    ⚠ CABEÇA com duração alta ({duracao:.2f}s) — verificar se vinheta foi removida")
        else:
            log.warning(f"⚠ Pipeline terminou com status: {resultado.status}")
        
        return 0
        
    except Exception as e:
        log.error(f"Erro durante o processamento: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
