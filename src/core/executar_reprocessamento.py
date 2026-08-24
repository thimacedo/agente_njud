import os
import sys
import json
import time
import shutil
import psutil
from pathlib import Path
from pydub import AudioSegment
from faster_whisper import WhisperModel

# yolo yagni autopilot: Limitar o Whisper e pydub a usar no máximo 2 threads/CPUs
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"
os.environ["VECLIB_MAXIMUM_THREADS"] = "2"
os.environ["NUMEXPR_NUM_THREADS"] = "2"

# Importa o pipeline do src estruturado
sys.path.insert(0, 'F:/Projetos/DIVISOR/src')
from divisor_boletins.audio import processar_recursivo
from divisor_boletins.montagem import montar_todos_jornais
from divisor_boletins.log import LogPipeline

logger = LogPipeline("F:/Projetos/DIVISOR/data/output/_logs")

PASTA_DESTINO_DRIVE_PAI = Path(r"H:\Meu Drive\RADIO TJRN CONTEÚDO\00_PRODUCAO_2026\02_JORNAIS_NJUD\03_AUDIOS_RADIO")

MAPEAMENTO_MESES = {
    "JAN": "01 - JAN - 26",
    "FEV": "02 - FEV - 26",
    "MAR": "03 - MAR - 26",
    "ABR": "04 - ABR - 26",
    "MAI": "05 - MAI - 26",
    "JUN": "06 - JUN - 26",
    "JUL": "07 - JUL - 26",
    "AGO": "08 - AGO - 26",
    "SET": "09 - SET - 26",
    "OUT": "10 - OUT - 26",
    "NOV": "11 - NOV - 26",
    "DEZ": "12 - DEZ - 26",
}

ORIGEM = Path(r"F:/Projetos/DIVISOR/JORNAIS")
DESTINO_CORTES = Path(r"F:/Projetos/DIVISOR/data/processed/JORNAIS_DIVIDIDOS")
DESTINO_SAIDA = Path(r"F:/Projetos/DIVISOR/data/output")

def obter_pasta_mes_destino(nome_arquivo):
    parts = nome_arquivo.replace(".mp3", "").split("_")
    if len(parts) >= 3:
        data_str = parts[2]
        data_parts = data_str.split("-")
        if len(data_parts) == 3:
            mes_num = data_parts[1]
            mes_nomes = {
                "01": "JAN", "02": "FEV", "03": "MAR", "04": "ABR",
                "05": "MAI", "06": "JUN", "07": "JUL", "08": "AGO",
                "09": "SET", "10": "OUT", "11": "NOV", "12": "DEZ"
            }
            mes_sigla = mes_nomes.get(mes_num)
            if mes_sigla and mes_sigla in MAPEAMENTO_MESES:
                return PASTA_DESTINO_DRIVE_PAI / MAPEAMENTO_MESES[mes_sigla]
    return None

def mover_jornal_para_drive(caminho_arquivo):
    pasta_destino = obter_pasta_mes_destino(caminho_arquivo.name)
    if not pasta_destino:
        print(f" ⚠ Não foi possível determinar o mês destino para: {caminho_arquivo.name}")
        return False
        
    pasta_destino.mkdir(parents=True, exist_ok=True)
    caminho_destino = pasta_destino / caminho_arquivo.name
    
    if caminho_destino.exists():
        # REGRA DE OPERAÇÃO: sobrescreve silenciosamente, sem criar cópias
        # _old no Drive (decisão do operador, 2026-08-24 — nenhuma cópia
        # extra deve ocupar espaço no H:).
        print(f" ↺ Arquivo existente será sobrescrito: {caminho_destino.name}")
        caminho_destino.unlink()
        
    print(f" ➜ Copiando para o Drive: {caminho_destino}")
    shutil.copy2(str(caminho_arquivo), str(caminho_destino))
    return True

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

def matar_processos_orfaos():
    """
    Mata processos Python que estejam rodando o mesmo script ou divisor_boletins,
    garantindo não tocar em nenhum outro processo (como Chrome, etc.).
    """
    print("=== [AGENTE] HIGIENIZANDO PROCESSOS ÓRFÃOS DO PIPELINE ===")
    my_pid = os.getpid()
    for p in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if p.info['pid'] == my_pid:
                continue
            cmd = ' '.join(p.info['cmdline'] or [])
            # Target específico: apenas processos Python rodando executar_reprocessamento ou divisor_boletins
            if 'python' in p.info['name'].lower() and ('executar_reprocessamento.py' in cmd or 'divisor_boletins' in cmd):
                print(f" Matando processo órfão {p.info['pid']}: {cmd}")
                p.kill()
        except Exception:
            pass

def executar_pipeline_autonomo():
    # Remover matar_processos_orfaos() daqui para evitar auto-kill no reinício do subprocesso/processo pai
    
    # yolo yagni autopilot: Definir prioridade BAIXA de CPU para o processo atual no Windows
    try:
        p = psutil.Process(os.getpid())
        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        print("=== [AGENTE] PRIORIDADE DO PIPELINE DEFINIDA COMO BAIXA (BELOW_NORMAL) ===")
    except Exception as e:
        print(f" ⚠ Não foi possível alterar prioridade do processo: {e}")
        
    os.makedirs(DESTINO_CORTES, exist_ok=True)
    os.makedirs(DESTINO_SAIDA, exist_ok=True)
    
    print("=== [AGENTE] 1. INICIANDO DIVISÃO DOS BOLETINS ===")
    processar_recursivo(ORIGEM, DESTINO_CORTES, apply=True)
    
    print("\n=== [AGENTE] 2. INICIANDO MONTAGEM DOS JORNAIS ===")
    montar_todos_jornais(DESTINO_CORTES, DESTINO_SAIDA, logger)
    
    print("\n=== [AGENTE] 3. AUDITORIA DE INTEGRIDADE TOTAL ===")
    # Whisper configurado para usar apenas 2 threads na CPU
    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)
    
    jornais = sorted([p for p in DESTINO_SAIDA.glob("*.mp3")])
    
    relatorio = []
    erros_detectados = 0
    
    for j in jornais:
        status_ok, motivo = analisar_integridade_arquivo(j, modelo)
        relatorio.append({
            "arquivo": j.name,
            "integridade": "OK" if status_ok else "ALERTA",
            "detalhe": motivo
        })
        if not status_ok:
            erros_detectados += 1
            print(f" ⚠ Alerta de integridade em {j.name}: {motivo}")
        else:
            print(f" ✓ {j.name}: Integridade validada.")
            
    with open("F:/Projetos/DIVISOR/data/output/relatorio_integridade_autonomo.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=2, ensure_ascii=False)
        
    print("\n=== [AGENTE] 4. COPIANDO JORNAIS VALIDADOS PARA O DRIVE ===")
    copias_sucesso = 0
    copias_falha = []
    drive_disponivel = os.path.exists(str(PASTA_DESTINO_DRIVE_PAI.parent.parent))
    
    if not drive_disponivel:
        print(f" ⚠ Google Drive não montado. Jornais permanecem em data/output/ para cópia posterior.")
        copias_falha = [j.name for j in jornais]
    else:
        for j in jornais:
            try:
                if mover_jornal_para_drive(j):
                    copias_sucesso += 1
            except Exception as e:
                print(f" ⚠ Falha ao copiar {j.name}: {e}")
                copias_falha.append(j.name)
    
    if copias_falha:
        pendentes_path = "F:/Projetos/DIVISOR/data/output/pendentes_drive.json"
        with open(pendentes_path, "w", encoding="utf-8") as f:
            json.dump(copias_falha, f, ensure_ascii=False, indent=2)
        print(f" 📋 {len(copias_falha)} arquivos pendentes registrados em {pendentes_path}")
            
    print(f"\n=== [AGENTE] Processo concluído. {copias_sucesso}/{len(jornais)} arquivos copiados para o Drive.")
    print(f"=== [AGENTE] Auditoria finalizada. {len(jornais)} jornais avaliados, {erros_detectados} com alertas.")

if __name__ == "__main__":
    executar_pipeline_autonomo()
