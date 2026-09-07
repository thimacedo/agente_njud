#!/usr/bin/env python3
"""Auditoria de NJUDs processados.
Verifica: cortes (_CABECA/_CORPO), duração, contexto (vinhetas).
Retorna: OK (selo) ou NECESSITA REFAZER.
"""
import json, sys, os, subprocess
from pathlib import Path

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")

estado_dir = E / "data" / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"
divididos_dir = E / "data" / "processed" / "PRODUCAO_2026" / "JORNAIS_DIVIDIDOS"
log_file = E / "logs" / "auditoria_v2.log"

NJUDs_ALVO = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]

def auditar_njud(njud_num):
    """Audita um NJUD. Retorna (status, problemas)"""
    problemas = []
    
    # 1. Verificar arquivos de estado com status OK
    cortes_ok = []
    for f in estado_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            if d.get("njud") == f"NJUD {njud_num}" and d.get("status") == "OK":
                cortes_ok.append(d)
        except:
            pass
    
    if len(cortes_ok) < 4:
        problemas.append(f"CORTES: apenas {len(cortes_ok)}/4 OK")
        return "NECESSITA REFAZER", problemas
    
    # 2. Verificar se há CABECA e CORPO
    arquivos = [c.get("arquivo", "") for c in cortes_ok]
    tem_cabeca = any("_CABECA" in Path(a).name or "CABECA" in a for a in arquivos)
    tem_corpo = any("_CORPO" in Path(a).name or "CORPO" in a for a in arquivos)
    
    # 3. Verificar duração via ffprobe nos cortes físicos
    for corte in cortes_ok:
        nome_arquivo = Path(corte.get("arquivo", "")).name
        # Procurar o corte em JORNAIS_DIVIDIDOS
        corte_path = None
        for root, dirs, files in os.walk(str(divididos_dir)):
            for f in files:
                if f.startswith(nome_arquivo.replace(".mp3", "")) and ("CABECA" in f or "CORPO" in f):
                    corte_path = os.path.join(root, f)
                    break
            if corte_path:
                break
        
        if corte_path and Path(corte_path).exists():
            try:
                result = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(corte_path)],
                    capture_output=True, text=True, timeout=10
                )
                info = json.loads(result.stdout)
                duracao = float(info.get("format", {}).get("duration", 0))
                is_corpo = "_CORPO" in Path(corte_path).name
                is_cabeca = "_CABECA" in Path(corte_path).name
                if is_corpo and duracao < 10:
                    problemas.append(f"DURACAO CORPO: {Path(corte_path).name[:40]} = {duracao:.1f}s (< 10s)")
                if is_cabeca and duracao > 30:
                    problemas.append(f"DURACAO CABECA: {Path(corte_path).name[:40]} = {duracao:.1f}s (> 30s)")
                if duracao > 180:
                    problemas.append(f"DURACAO: {Path(corte_path).name[:40]} = {duracao:.1f}s (> 180s, possível sobra)")
            except:
                pass
    
    # 4. Verificar sobras de vinhetas
    for corte in cortes_ok:
        nome = Path(corte.get("arquivo", "")).name.upper()
        if "VINHETA" in nome or "VH_" in nome or "NOTICIAS_DA_HORA" in nome:
            problemas.append(f"CONTEXTO: possível vinheta no corte: {Path(corte.get('arquivo',''))[:50].name}")
    
    if problemas:
        return "NECESSITA REFAZER", problemas
    return "OK", []

# Loop principal
with open(log_file, "w") as log:
    log.write("=== AUDITORIA DE NJUDs v2 ===\n\n")
    log.flush()
    
    fila_refazer = []
    selo_ok = []
    
    for njud in NJUDs_ALVO:
        status, problemas = auditar_njud(njud)
        if status == "OK":
            selo_ok.append(njud)
            log.write(f"NJUD {njud}: SELLO OK\n")
        else:
            fila_refazer.append((njud, problemas))
            log.write(f"NJUD {njud}: NECESSITA REFAZER\n")
            for p in problemas:
                log.write(f"  - {p}\n")
        log.flush()
    
    log.write(f"\n=== RESUMO ===\n")
    log.write(f"Selo OK: {len(selo_ok)}\n")
    log.write(f"Necessita refazer: {len(fila_refazer)}\n")
    if fila_refazer:
        log.write(f"Fila refazer: {', '.join(n for n, _ in fila_refazer)}\n")

print(f"Auditoria: {len(selo_ok)} OK, {len(fila_refazer)} refazer")
