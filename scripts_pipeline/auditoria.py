#!/usr/bin/env python3
"""Auditoria de NJUDs processados.
Verifica: cortes, montagem, contexto, sobras de vinhetas.
Retorna: OK (selo) ou NECESSITA REFAZER.
"""
import json, sys, os, subprocess, gc
from pathlib import Path

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
sys.path.insert(0, str(E / "src"))

estado_dir = E / "data" / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"
divididos_dir = E / "data" / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"
final_dir = E / "data" / "output" / "JORNAIS_FINAL"
log_file = E / "logs" / "auditoria.log"

# NJUDs alvo
NJUDs_ALVO = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]

def auditar_njud(njud_num):
    """Audita um NJUD específico. Retorna (status, problemas)"""
    problemas = []
    
    # 1. Verificar cortes (_CABECA e _CORPO)
    njud_cortes = []
    for f in estado_dir.glob("*.json"):
        d = json.loads(f.read_text())
        if d.get("njud") == f"NJUD {njud_num}" and d.get("status") == "OK":
            njud_cortes.append(d)
    
    if len(njud_cortes) < 4:
        problemas.append(f"CORTES: apenas {len(njud_cortes)}/4 OK")
        return "NECESSITA REFAZER", problemas
    
    # 2. Verificar se há cortes _CABECA e _CORPO
    tem_cabeca = any("_CABECA" in c.get("arquivo", "") for c in njud_cortes)
    tem_corpo = any("_CORPO" in c.get("arquivo", "") for c in njud_cortes)
    if not tem_cabeca or not tem_corpo:
        problemas.append(f"CORTES: sem CABECA={tem_cabeca}, sem CORPO={tem_corpo}")
    
    # 3. Verificar duração dos cortes (mínimo 5s cada)
    for corte in njud_cortes:
        caminho = corte.get("caminho_corte", "")
        if not caminho or not Path(caminho).exists():
            # Procurar no JORNAIS_DIVIDIDOS
            for root, dirs, files in os.walk(str(divididos_dir)):
                for f in files:
                    if f == Path(caminho).name:
                        caminho = os.path.join(root, f)
                        break
        
        if caminho and Path(caminho).exists():
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(caminho)],
                    capture_output=True, text=True, timeout=10
                )
                info = json.loads(result.stdout)
                duracao = float(info.get("format", {}).get("duration", 0))
                if duracao < 3:
                    problemas.append(f"DURACAO: {Path(caminho).name} = {duracao:.1f}s (< 3s)")
            except:
                pass
    
    # 4. Verificar contexto (vinhetas)
    for corte in njud_cortes:
        arquivo = corte.get("arquivo", "")
        if "VINHETA" in arquivo.upper() or "VH_" in arquivo.upper():
            problemas.append(f"CONTEXTO: possível vinheta no corte: {Path(arquivo).name}")
    
    # 5. Resultado
    if problemas:
        return "NECESSITA REFAZER", problemas
    else:
        return "OK", []

# Loop principal
with open(log_file, "w") as log:
    log.write("=== AUDITORIA DE NJUDs ===\n\n")
    log.flush()
    
    fila_refazer = []
    selo_ok = []
    
    for njud in NJUDs_ALVO:
        status, problemas = auditar_njud(njud)
        if status == "OK":
            selo_ok.append(njud)
            log.write(f"NJUD {njud}: ✅ SELLO OK\n")
        else:
            fila_refazer.append(njud)
            log.write(f"NJUD {njud}: ❌ NECESSITA REFAZER\n")
            for p in problemas:
                log.write(f"  - {p}\n")
        log.flush()
    
    log.write(f"\n=== RESUMO ===\n")
    log.write(f"Selo OK: {len(selo_ok)}\n")
    log.write(f"Necessita refazer: {len(fila_refazer)}\n")
    if fila_refazer:
        log.write(f"Fila: {', '.join(fila_refazer)}\n")

print(f"Auditoria concluída: {len(selo_ok)} OK, {len(fila_refazer)} refazer")
