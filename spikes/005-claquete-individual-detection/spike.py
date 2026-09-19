#!/usr/bin/env python3
"""Spike 005: detectar claquetes individuais no início de cada boletim."""
import sys, os, re, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'scripts_pipeline', 'boletim'))
from processar_boletim_canonico import carregar_modelo, transcrever
from pydub import AudioSegment
from pathlib import Path

SAIDA_DIR = r"E:\02_Projetos_Trabalho\Projetos_Ativos\DIVISOR\boletins\17 SET B1-B5-2_saida"

# Padrões de claquete individual
PADROES_CLAQUETE = [
    re.compile(r'^(?:[BMV]\d{1,2})[\s.,:\-–—]', re.I),  # B3. M2, V5, B10,
    re.compile(r'^boletins?\s+\d+', re.I),               # "Boletins 17..."
    re.compile(r'^(?:no\s+ar|not[ií]cias?\s+da\s+hora|boletim\s+informativo)', re.I),  # vinheta abertura
]

def eh_claquete(texto, duracao_seg):
    """Verifica se um segmento é claquete individual."""
    texto_limpo = texto.strip()
    
    # Vinheta de abertura sempre é mantida (NÃO é claquete a remover)
    if re.match(r'^(?:no\s+ar|not[ií]cias?\s+da\s+hora|boletim\s+informativo)', texto_limpo, re.I):
        return False, "vinheta_abertura"
    
    # Padrão B{N}. / M{N}. / V{N}.
    if PADROES_CLAQUETE[0].match(texto_limpo):
        # Se duração curta (<4s), é claquete
        if duracao_seg < 4.0:
            return True, "claquete_B{MNV}"
        else:
            return False, "conteudo_longo"
    
    # Claquete geral "Boletins X de Y..."
    if PADROES_CLAQUETE[1].match(texto_limpo):
        return True, "claquete_geral"
    
    return False, "nao_match"

def main():
    print("=" * 70)
    print("SPIKE 005: claquete-individual-detection")
    print("=" * 70)
    
    modelo = carregar_modelo()
    
    resultados = []
    
    for boletim_path in sorted(Path(SAIDA_DIR).glob("*.mp3")):
        print(f"\n--- {boletim_path.name} ---")
        
        audio = AudioSegment.from_mp3(str(boletim_path))
        tmp = tempfile.mktemp(suffix=".wav", dir=r"C:\Users\THIAGO\AppData\Local\Temp")
        segmentos = transcrever(audio, tmp, modelo)
        
        if not segmentos:
            print("  Sem segmentos")
            continue
        
        # Analisar primeiros 5 segmentos (janela de busca por claquete)
        print(f"  Total segmentos: {len(segmentos)}")
        print(f"  Analisando primeiros 5 segmentos:")
        
        for i, seg in enumerate(segmentos[:5]):
            texto = seg["text"].strip()
            duracao = seg["end"] - seg["start"]
            is_claq, motivo = eh_claquete(texto, duracao)
            
            marcador = "❌ CLAQUETE" if is_claq else "✅ manter"
            print(f"    [{seg['start']:.1f}s-{seg['end']:.1f}s] ({duracao:.1f}s) {marcador} ({motivo})")
            print(f"      \"{texto[:80]}\"")
            
            resultados.append({
                "boletim": boletim_path.stem,
                "segmento_idx": i,
                "inicio": seg["start"],
                "fim": seg["end"],
                "duracao": duracao,
                "texto": texto[:100],
                "eh_claquete": is_claq,
                "motivo": motivo
            })
    
    # Resumo
    print(f"\n{'='*70}")
    print("RESUMO")
    print("=" * 70)
    
    claquetes = [r for r in resultados if r["eh_claquete"]]
    mantidos = [r for r in resultados if not r["eh_claquete"]]
    
    print(f"  Total segmentos analisados: {len(resultados)}")
    print(f"  Claquetes detectadas: {len(claquetes)}")
    print(f"  Segmentos mantidos: {len(mantidos)}")
    
    if claquetes:
        print(f"\n  Claquetes a remover:")
        for c in claquetes:
            print(f"    {c['boletim']}: [{c['inicio']:.1f}s-{c['fim']:.1f}s] \"{c['texto'][:50]}\"")
    
    # Salvar
    out_path = Path(__file__).parent / "resultados.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    print(f"\n  Resultados salvos: {out_path}")

if __name__ == "__main__":
    main()
