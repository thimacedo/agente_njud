#!/usr/bin/env python3
"""Orquestrador do pipeline DIVISOR.
Ciclo continuo: percebe -> planeja -> age -> adapta.
"""
import json, time, subprocess, os, sys
from pathlib import Path
from datetime import datetime

E = Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
estado_dir = E / "data" / "processed" / "PRODUCAO_2026" / "estado_por_arquivo"
log_orq = E / "logs" / "orquestrador.log"

NJUDs_ALVO = [str(n) for n in list(range(1909, 1927)) + list(range(1936, 1945))]

def contar_estado():
    """Conta arquivos de estado por status para NJUDs alvo."""
    status = {n: {"OK": 0, "ERRO": 0, "ESGOTADO": 0, "PENDENTE": 0} for n in NJUDs_ALVO}
    for f in estado_dir.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            njud = d.get("njud", "").replace("NJUD ", "")
            if njud in NJUDs_ALVO:
                s = d.get("status", "?")
                if s in status[njud]:
                    status[njud][s] += 1
        except:
            pass
    return status

def verificar_serial():
    """Verifica se o serial processor esta rodando."""
    for proc in os.popen('tasklist /FI "IMAGENAME eq python.exe" /FO CSV').readlines():
        if "serial" in proc.lower():
            return True
    return False

def rodar_auditoria():
    """Roda a auditoria v2."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(E / "src")
    result = subprocess.run(
        [sys.executable, str(E / "scripts_pipeline" / "auditoria_v2.py")],
        cwd=str(E), env=env, capture_output=True, text=True, timeout=300
    )
    return result.returncode == 0

def obter_resultado_auditoria():
    """Le o resultado da auditoria."""
    log_aud = E / "logs" / "auditoria_v2.log"
    if not log_aud.exists():
        return None, None
    content = log_aud.read_text()
    linhas = content.splitlines()
    
    selo_ok = []
    fila_refazer = []
    for l in linhas:
        if "SELLO OK" in l:
            njud = l.split(":")[0].strip().replace("NJUD ", "")
            selo_ok.append(njud)
        elif "NECESSITA REFAZER" in l:
            njud = l.split(":")[0].strip().replace("NJUD ", "")
            fila_refazer.append(njud)
    
    return selo_ok, fila_refazer

# Loop principal do orquestrador
with open(log_orq, "w") as log:
    log.write("=== ORQUESTRADOR INICIADO ===\n")
    log.flush()
    
    ciclo = 0
    while True:
        ciclo += 1
        agora = datetime.now().strftime("%H:%M:%S")
        
        # 1. PERCEBER
        status = contar_estado()
        serial_rodando = verificar_serial()
        
        total_ok = sum(1 for n in NJUDs_ALVO if status[n]["OK"] >= 4)
        total_erro = sum(1 for n in NJUDs_ALVO if status[n]["OK"] == 0 and (status[n]["ERRO"] > 0 or status[n]["ESGOTADO"] > 0))
        total_parcial = sum(1 for n in NJUDs_ALVO if 0 < status[n]["OK"] < 4)
        
        log.write(f"\n[{agora}] CICLO {ciclo}\n")
        log.write(f"  Serial: {'RODANDO' if serial_rodando else 'MORTO'}\n")
        log.write(f"  Progresso: {total_ok} completos, {total_parcial} parciais, {total_erro} so erro\n")
        log.flush()
        
        # 2. PLANEJAR
        # Se ha NJUDs com 4+ OK que ainda nao foram auditados, rodar auditoria
        # Se o serial morreu e ainda ha pendentes, reportar
        
        # 3. AGIR
        if total_ok > 0:
            # Rodar auditoria
            log.write(f"  -> Rodando auditoria...\n")
            log.flush()
            
            if rodar_auditoria():
                selo_ok, fila_refazer = obter_resultado_auditoria()
                if selo_ok is not None:
                    log.write(f"  -> Auditoria: {len(selo_ok)} OK, {len(fila_refazer)} refazer\n")
                    log.write(f"  -> Selo OK: {', '.join(selo_ok[:10])}{'...' if len(selo_ok) > 10 else ''}\n")
                    log.write(f"  -> Fila refazer: {', '.join(fila_refazer[:10])}{'...' if len(fila_refazer) > 10 else ''}\n")
                    log.flush()
        
        # Verificar se tudo terminou
        total_njuds_com_estado = sum(1 for n in NJUDs_ALVO if sum(status[n].values()) > 0)
        if total_njuds_com_estado == len(NJUDs_ALVO) and not serial_rodando:
            log.write(f"\n=== TUDO CONCLUIDO ===\n")
            log.write(f"Completos: {total_ok}/{len(NJUDs_ALVO)}\n")
            log.flush()
            break
        
        # 4. ADAPTAR - aguardar proximo ciclo
        time.sleep(300)  # 5 minutos

print("Orquestrador concluido")
