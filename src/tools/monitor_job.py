#!/usr/bin/env python3
"""
Monitor de segurança para jobs longos de auditoria.
- Verifica se o processo ainda está vivo
- Alerta se morrer antes de gerar o CSV final
- Reporta progresso baseado no arquivo de saída parcial (se houver)
"""
import psutil
import time
import sys
from pathlib import Path
import csv

def monitorar(pid: int, csv_path: str, intervalo: int = 30, timeout_total: int = 7200):
    """Monitora um PID até terminar ou timeout."""
    csv_file = Path(csv_path)
    inicio = time.time()
    ultimo_progresso = 0
    
    print(f"[MONITOR] Iniciado para PID {pid}, CSV: {csv_path}")
    print(f"[MONITOR] Intervalo: {intervalo}s, Timeout total: {timeout_total}s")
    
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        print(f"[MONITOR] ERRO: PID {pid} não existe no início")
        return 1
    
    while True:
        time.sleep(intervalo)
        
        # Verifica timeout total
        if time.time() - inicio > timeout_total:
            print(f"[MONITOR] TIMEOUT TOTAL ({timeout_total}s) — matando PID {pid}")
            try:
                proc.kill()
            except psutil.NoSuchProcess:
                pass
            return 2
        
        # Verifica se processo ainda vive
        try:
            if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                print(f"[MONITOR] Processo MORTO (status: {proc.status()})")
                break
        except psutil.NoSuchProcess:
            print(f"[MONITOR] Processo NÃO EXISTE MAIS")
            break
        
        # Verifica progresso no CSV (se já começou a escrever)
        progresso_atual = 0
        if csv_file.exists():
            try:
                with open(csv_file, encoding='utf-8') as f:
                    # Conta linhas (menos header)
                    progresso_atual = sum(1 for _ in f) - 1
            except Exception:
                pass
        
        if progresso_atual != ultimo_progresso:
            elapsed = time.time() - inicio
            rate = progresso_atual / elapsed if elapsed > 0 else 0
            eta = (1104 - progresso_atual) / rate if rate > 0 else 0
            print(f"[MONITOR] Progresso: {progresso_atual}/1104 ({progresso_atual/1104*100:.1f}%) | "
                  f"Taxa: {rate:.1f} arq/s | ETA: {eta/60:.0f}min | "
                  f"CPU: {proc.cpu_percent():.1f}% | Mem: {proc.memory_info().rss/1024/1024:.0f}MB")
            ultimo_progresso = progresso_atual
        
        # Verifica se CSV finalizado (todas as linhas)
        if progresso_atual >= 1104:
            print(f"[MONITOR] CSV COMPLETO: {progresso_atual} linhas")
            # Aguarda processo terminar graciosamente
            try:
                proc.wait(timeout=30)
                print(f"[MONITOR] Processo finalizado com exit_code: {proc.wait()}")
            except psutil.TimeoutExpired:
                print(f"[MONITOR] Processo não encerrou após CSV completo — forçando")
                proc.kill()
            return 0
    
    # Processo morreu — verifica se CSV foi salvo
    if csv_file.exists():
        with open(csv_file, encoding='utf-8') as f:
            linhas = sum(1 for _ in f) - 1
        print(f"[MONITOR] ALERTA: Processo morreu com {linhas}/1104 linhas no CSV")
        if linhas < 1104:
            print(f"[MONITOR] CSV INCOMPLETO — será necessário reiniciar")
            return 3
        else:
            print(f"[MONITOR] CSV completo apesar da morte do processo")
            return 0
    else:
        print(f"[MONITOR] ALERTA CRÍTICO: Processo morreu e NENHUM CSV foi gerado")
        return 4

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python monitor_job.py <PID> <caminho_csv> [intervalo_s] [timeout_total_s]")
        sys.exit(1)
    
    pid = int(sys.argv[1])
    csv_path = sys.argv[2]
    intervalo = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 7200
    
    sys.exit(monitorar(pid, csv_path, intervalo, timeout))