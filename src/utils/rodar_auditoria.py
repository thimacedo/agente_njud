import os
import sys
import json
from pathlib import Path
from faster_whisper import WhisperModel

def analisar_integridade_arquivo(caminho, modelo_whisper):
    try:
        segs, info = modelo_whisper.transcribe(str(caminho), beam_size=3, language='pt')
        textos = [s.text.strip() for s in segs]
        full_text = " ".join(textos)
        
        palavras = full_text.split()
        if not palavras:
            return False, "Áudio vazio ou sem fala detectada"
            
        primeira = palavras[0]
        ultima = palavras[-1]
        
        incompleta_inicio = primeira.islower() and len(primeira) > 1 and primeira not in ['a', 'o', 'e', 'de', 'do', 'da', 'em', 'um', 'uma', 'para', 'com', 'no', 'na']
        incompleta_fim = not (full_text.endswith('.') or full_text.endswith('!') or full_text.endswith('?'))
        
        if incompleta_inicio:
            return False, f"Início truncado (palavra: '{primeira}')"
        if incompleta_fim:
            return False, f"Fim sem pontuação/truncado (palavra: '{ultima}')"
            
        return True, "OK"
    except Exception as e:
        return False, f"Erro na análise: {str(e)}"

def executar_auditoria():
    print("=== [AGENTE] Iniciando Auditoria de Integridade de forma isolada ===")
    modelo = WhisperModel("small", device="cpu", compute_type="int8")
    
    pasta_montados = Path('F:/Projetos/DIVISOR/data/output/JORNAIS_DIVIDIDOS_montados')
    jornais = sorted([pasta_montados / f for f in os.listdir(pasta_montados) if f.endswith('.mp3')])
    
    relatorio = []
    erros_detectados = 0
    
    for i, j in enumerate(jornais):
        print(f"[{i+1}/{len(jornais)}] Analisando: {j.name} ...")
        status_ok, motivo = analisar_integridade_arquivo(j, modelo)
        relatorio.append({
            "arquivo": j.name,
            "integridade": "OK" if status_ok else "ALERTA",
            "detalhe": motivo
        })
        if not status_ok:
            erros_detectados += 1
            print(f"  ⚠ ALERTA em {j.name}: {motivo}")
        else:
            print(f"  ✓ {j.name}: OK")
            
    with open("F:/Projetos/DIVISOR/logs/relatorio_integridade_autonomo.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
        
    print(f"\n=== [AGENTE] Auditoria finalizada. {len(jornais)} jornais avaliados, {erros_detectados} com alertas.")

if __name__ == "__main__":
    executar_auditoria()
