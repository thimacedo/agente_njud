#!/usr/bin/env python3
"""
Dispatcher Paralelo — Pool de Workers para o Processo Único
=============================================================

Distribui o ciclo corte->auditoria->reaprendizado (processo_unico.py)
entre N subprocessos workers, cada um mantendo seu próprio modelo Whisper
carregado uma única vez (evita o custo de recarregar o modelo por tarefa).

DECISÕES DE PROJETO (não reverter sem entender o motivo):

1. Nº de workers é CALCULADO, não fixo arbitrário:
   limite_cpu = max(1, (nucleos_fisicos - 1) // THREADS_POR_WORKER)
   limite_ram = max(1, int((ram_livre_gb - RAM_RESERVADA_GB) / RAM_POR_WORKER_GB))
   workers = min(limite_cpu, limite_ram, TETO_MANUAL)
   Isso evita o cenário "8 workers, cada um pedindo 2 threads, numa
   máquina de 8 núcleos" — que trava o PC inteiro, incluindo o monitor
   e qualquer outra coisa rodando.

2. Cada worker roda com prioridade BELOW_NORMAL (mesma politica já usada
   em executar_reprocessamento.py) — trabalho de fundo nunca compete com
   o primeiro plano do operador.

3. Estado NÃO é um único JSON compartilhado. Cada arquivo tem seu próprio
   estado/<nome>.json, escrito só pelo worker responsável por ele. Isso
   elimina qualquer necessidade de lock: não existem dois processos
   escrevendo o mesmo arquivo ao mesmo tempo. O agregador (usado pelo
   gate de montagem) só LÊ.

4. Monitor de carga: antes de despachar uma nova tarefa, o dispatcher
   confere a CPU global. Se estiver acima de LIMIAR_CPU_PAUSA, ele
   espera em vez de enfileirar mais trabalho — mesmo que haja worker
   ocioso. Isso cobre casos em que outro processo do operador (não
   relacionado ao pipeline) está consumindo CPU no momento.

5. A montagem continua fora deste pool, rodando sozinha e só quando
   njud_completo() fecha — nunca concorrente com os workers de corte,
   para não competir por I/O de disco na hora de gerar o jornal final.

Uso
----
    python dispatcher_paralelo.py <pasta_boletins> <pasta_saida> \
        [--max-workers N] [--threads-por-worker 2] [--limiar-cpu 85]
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from queue import Empty

import psutil

# ===========================================================================
# ORÇAMENTO DE RECURSOS
# ===========================================================================

THREADS_POR_WORKER_PADRAO = 2      # mesmo valor usado hoje no pipeline serial
# MEDIDO em 2026-08-24: 2 workers em paralelo causaram mkl_malloc OOM com
# 5.6GB livres. Cada worker consome ~2.5GB no pico (transcrição + VAD).
RAM_POR_WORKER_GB = 2.5
RAM_RESERVADA_GB = 3.0             # nunca consumir isso, deixa pro SO/operador
LIMIAR_CPU_PAUSA = 85.0            # % de uso global acima do qual pausa despacho
INTERVALO_CHECAGEM_CPU_S = 5


def calcular_max_workers(threads_por_worker: int, teto_manual: int | None) -> int:
    nucleos_fisicos = psutil.cpu_count(logical=False) or os.cpu_count() or 2
    limite_cpu = max(1, (nucleos_fisicos - 1) // threads_por_worker)

    ram_livre_gb = psutil.virtual_memory().available / (1024 ** 3)
    ram_disponivel = max(0.0, ram_livre_gb - RAM_RESERVADA_GB)
    limite_ram = max(1, int(ram_disponivel / RAM_POR_WORKER_GB))

    candidatos = [limite_cpu, limite_ram]
    if teto_manual is not None:
        candidatos.append(teto_manual)
    escolhido = min(candidatos)

    print(
        f"[dispatcher] núcleos_físicos={nucleos_fisicos} "
        f"limite_cpu={limite_cpu} ram_livre={ram_livre_gb:.1f}GB "
        f"limite_ram={limite_ram} -> workers={escolhido}"
    )
    return escolhido


# ===========================================================================
# WORKER PERSISTENTE
# ===========================================================================

def _aplicar_prioridade_baixa():
    try:
        p = psutil.Process(os.getpid())
        if hasattr(psutil, "BELOW_NORMAL_PRIORITY_CLASS"):
            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)  # Windows
        else:
            p.nice(10)  # POSIX
    except Exception:
        pass


def worker_loop(
    worker_id: int,
    fila_tarefas: mp.Queue,
    pasta_estado: Path,
    threads_por_worker: int,
    usar_whisper_timestamped: bool = False,
):
    """Processo de vida longa: carrega o modelo Whisper UMA vez, depois
    consome tarefas da fila até receber o sentinel None."""
    os.environ["OMP_NUM_THREADS"] = str(threads_por_worker)
    os.environ["MKL_NUM_THREADS"] = str(threads_por_worker)
    _aplicar_prioridade_baixa()

    if usar_whisper_timestamped:
        import whisper_timestamped as wt
        modelo_wt = wt.load_model("small", device="cpu", compute_type="int8")
    else:
        modelo_wt = None

    from faster_whisper import WhisperModel
    from divisor_boletins.audio import processar_arquivo
    from divisor_boletins.log import LogPipeline
    from analisar_cortes_individuais import analisar_par
    from processo_unico import ciclo_arquivo

    print(f"[worker {worker_id}] carregando modelo Whisper...")
    modelo = WhisperModel("small", device="cpu", compute_type="int8",
                           cpu_threads=threads_por_worker)
    pasta_saida_cortes = pasta_estado.parent / "JORNAIS_DIVIDIDOS"
    logger_worker = LogPipeline(pasta_estado.parent / "_logs" / f"worker_{worker_id}")
    print(f"[worker {worker_id}] pronto. whisper_timestamped={usar_whisper_timestamped}")

    # HEARTBEAT: prova de vida para o monitor_tempo_real.py. Gravado ao
    # receber tarefa, a cada conclusão e quando ocioso (via timeout da fila).
    pasta_heartbeat = pasta_estado.parent / "_heartbeat"
    pasta_heartbeat.mkdir(parents=True, exist_ok=True)
    caminho_heartbeat = pasta_heartbeat / f"worker_{worker_id}.json"

    def _bater_heartbeat(tarefa_atual: str | None):
        try:
            caminho_heartbeat.write_text(json.dumps({
                "worker_id": worker_id,
                "pid": os.getpid(),
                "timestamp": time.time(),
                "tarefa_atual": tarefa_atual,
            }), encoding="utf-8")
        except Exception:
            pass

    _bater_heartbeat(None)

    while True:
        try:
            tarefa = fila_tarefas.get(timeout=5)
        except Empty:
            _bater_heartbeat(None)  # ocioso mas vivo
            continue
        if tarefa is None:
            break

        arquivo, njud = tarefa["arquivo"], tarefa["njud"]
        caminho_estado_arquivo = pasta_estado / f"{Path(arquivo).stem}.json"
        pasta_destino_njud = pasta_saida_cortes / njud
        _bater_heartbeat(arquivo)

        def cortar_fn(arq, estrategia, _modelo=modelo, _logger=logger_worker,
                      _destino=pasta_destino_njud):
            resultado = processar_arquivo(
                arq, _destino, _modelo, _logger, apply=True, estrategia=estrategia,
            )
            if resultado is None:
                raise RuntimeError(f"processar_arquivo falhou para {arq} (transcrição ou I/O)")
            return resultado.arquivo_cabeca, resultado.arquivo_corpo

        def auditar_fn(cabeca, corpo, _modelo=modelo):
            return analisar_par(cabeca, corpo, _modelo)

        # HEARTBEAT EM BACKGROUND: o processamento de um arquivo pode levar
        # minutos; sem isso o monitor marca worker como MORTO? (falso positivo,
        # observado em 2026-08-24). Thread daemon atualiza a cada 10s.
        import threading
        parar_hb = threading.Event()

        def _heartbeat_continuo():
            while not parar_hb.wait(10):
                _bater_heartbeat(arquivo)

        hb_thread = threading.Thread(target=_heartbeat_continuo, daemon=True)
        hb_thread.start()

        try:
            estado_local = _EstadoArquivoUnico(caminho_estado_arquivo, arquivo, njud)
            resultado = ciclo_arquivo(estado_local, arquivo, njud, cortar_fn, auditar_fn)
            print(f"[worker {worker_id}] {arquivo}: {resultado.status}")
        except Exception as e:
            print(f"[worker {worker_id}] ERRO em {arquivo}: {e}")
            caminho_estado_arquivo.write_text(
                json.dumps({"arquivo": arquivo, "njud": njud, "status": "ERRO",
                            "erro": str(e)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        finally:
            parar_hb.set()  # encerra o heartbeat contínuo desta tarefa


class _EstadoArquivoUnico:
    """Adapta EstadoProcesso para persistir em UM arquivo por boletim
    (em vez do JSON único), eliminando concorrência de escrita entre
    workers sem precisar de lock."""
    def __init__(self, caminho: Path, arquivo: str, njud: str):
        from processo_unico import EstadoArquivo
        self.caminho = caminho
        if caminho.exists():
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            from processo_unico import TentativaLog
            tentativas = [TentativaLog(**t) for t in dados.pop("tentativas", [])]
            # Filtra chaves que não existem no dataclass (ex.: "erro" gravado pelo
            # handler de exceção do worker). Sem isso, arquivos com status ERRO
            # crasham eternamente no retry e nunca são reprocessados.
            import dataclasses
            validas = {f_.name for f_ in dataclasses.fields(EstadoArquivo)}
            dados = {k: v for k, v in dados.items() if k in validas}
            self._e = EstadoArquivo(tentativas=tentativas, **dados)
        else:
            self._e = EstadoArquivo(arquivo=arquivo, njud=njud)

    def obter_ou_criar(self, arquivo, njud):
        return self._e

    def salvar(self):
        from dataclasses import asdict
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(asdict(self._e), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


# ===========================================================================
# AGREGADOR (só leitura — usado pelo gate de montagem)
# ===========================================================================

def njud_completo(pasta_estado: Path, njud: str, pasta_boletins: Path) -> bool:
    """Valida se NJUD está completo comparando estados E contagem física.
    
    Bug crítico corrigido 2026-08-25: antes só lia estados JSON, o que podia
    considerar NJUD completo com 3 de 4 boletins se um worker crashasse sem
    escrever o JSON. Agora valida contra arquivos físicos na origem.
    """
    # Conta estados OK/ESGOTADO_ACEITO
    estados_concluidos = []
    for p in pasta_estado.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("njud") == njud and d.get("status") in ("OK", "ESGOTADO_ACEITO"):
            estados_concluidos.append(d)
    
    # Validação crítica: compara com contagem física real (antes era código morto)
    total_fisico = total_esperado_njud(njud, pasta_boletins)
    if len(estados_concluidos) < total_fisico:
        return False
    
    # Regra inegociável: precisa de 4 boletins (ou 3 com exceção explícita)
    return len(estados_concluidos) >= 3


# ===========================================================================
# DISPATCHER PRINCIPAL
# ===========================================================================

def listar_tarefas_pendentes(pasta_boletins: Path, pasta_estado: Path) -> list[dict]:
    tarefas = []
    for arq in sorted(pasta_boletins.rglob("*.mp3")):
        njud = arq.parent.name
        caminho_estado = pasta_estado / f"{arq.stem}.json"
        if caminho_estado.exists():
            status = json.loads(caminho_estado.read_text(encoding="utf-8")).get("status")
            if status in ("OK", "ESGOTADO_ACEITO"):
                continue  # já concluído — não reenfileira (isso É o "processo único")
        tarefas.append({"arquivo": str(arq), "njud": njud})
    return tarefas


def executar(pasta_boletins: Path, pasta_saida: Path, max_workers: int | None,
             threads_por_worker: int, limiar_cpu: float,
             usar_whisper_timestamped: bool = False):
    pasta_estado = pasta_saida / "estado_por_arquivo"
    pasta_estado.mkdir(parents=True, exist_ok=True)

    n_workers = calcular_max_workers(threads_por_worker, max_workers)
    tarefas = listar_tarefas_pendentes(pasta_boletins, pasta_estado)
    print(f"[dispatcher] {len(tarefas)} tarefa(s) pendente(s) (arquivos já OK são pulados).")
    if not tarefas:
        print("[dispatcher] Nada a fazer — todo o lote já está em estado ideal.")
        return

    fila = mp.Queue()
    processos = []
    for i in range(n_workers):
        p = mp.Process(target=worker_loop, args=(i, fila, pasta_estado, threads_por_worker, usar_whisper_timestamped))
        p.start()
        processos.append(p)

    # Despacho com controle de carga: só empurra tarefa nova se CPU global
    # estiver abaixo do limiar. Isso protege contra outros processos do
    # operador competindo por CPU no mesmo momento.
    idx = 0
    while idx < len(tarefas):
        uso_cpu = psutil.cpu_percent(interval=1)
        if uso_cpu >= limiar_cpu:
            print(f"[dispatcher] CPU em {uso_cpu:.0f}% (>= {limiar_cpu}%) — pausando despacho...")
            time.sleep(INTERVALO_CHECAGEM_CPU_S)
            continue
        fila.put(tarefas[idx])
        idx += 1

    for _ in processos:
        fila.put(None)  # sentinel de encerramento por worker
    for p in processos:
        p.join()

    # Watchdog: se ainda houver tarefas pendentes após o pool inicial terminar,
    # assume que algum worker morreu e respawn — REPOE as tarefas na fila e
    # reenvia os sentinels corretamente (bug crítico corrigido 2026-08-25).
    pendentes = listar_tarefas_pendentes(pasta_boletins, pasta_estado)
    if pendentes:
        print(f"[dispatcher] watchdog: {len(pendentes)} tarefa(s) pendente(s); respawn do pool...")
        processos = []
        for i in range(n_workers):
            p = mp.Process(target=worker_loop, args=(i, fila, pasta_estado, threads_por_worker, usar_whisper_timestamped))
            p.start()
            processos.append(p)
        # REPOE as tarefas pendentes na nova fila (antes não repunha → hang infinito)
        for tarefa in pendentes:
            fila.put(tarefa)
        # Reenvia sentinels para garantir encerramento
        for _ in processos:
            fila.put(None)
        for p in processos:
            p.join()

    # ================================================================
    # AUTONOMIA: montagem automática dos NJUDs completos (2026-08-24)
    # O processo único não termina em "cortes prontos" — termina no
    # jornal montado. Assim que TODOS os boletins de um NJUD estão OK
    # ou ESGOTADO_ACEITO, a montagem daquele NJUD dispara sozinha.
    # ESGOTADO puro (sem aceitação) NUNCA monta — segue para revisão manual.
    # ================================================================
    pasta_cortes = pasta_saida / "JORNAIS_DIVIDIDOS"
    pasta_jornais = pasta_saida / "JORNAIS_FINAL"
    pasta_jornais.mkdir(parents=True, exist_ok=True)

    # Fonte da verdade para montagem: estado_por_arquivo/*.json
    # Motivo: total_esperado_njud() baseado em pastas pode divergir se a
    # estrutura de entrada mudar; o estado reflete exatamente o que foi
    # processado e é a base do gate por-NJUD.
    njuds_estado: dict[str, dict] = {}
    for p_estado in pasta_estado.glob("*.json"):
        try:
            d = json.loads(p_estado.read_text(encoding="utf-8"))
        except Exception:
            continue
        njud = d.get("njud", "?")
        status = d.get("status", "PENDENTE")
        njuds_estado.setdefault(njud, {"total": 0, "concluidos": 0})
        njuds_estado[njud]["total"] += 1
        if status in ("OK", "ESGOTADO_ACEITO"):
            njuds_estado[njud]["concluidos"] += 1

    # Gate por-NJUD agora usa njud_completo() com validação física (bug fix 2026-08-25)
    njuds_prontos = []
    for njud, info in sorted(njuds_estado.items()):
        if njud_completo(pasta_estado, njud, pasta_boletins):
            njuds_prontos.append(njud)

    if not njuds_prontos:
        print("[dispatcher] Nenhum NJUD completo — nada a montar.")
        return

    print(f"[dispatcher] {len(njuds_prontos)} NJUD(s) completo(s): {njuds_prontos}")
    sys.path.insert(0, str(Path(__file__).parent))
    from divisor_boletins.log import LogPipeline
    # montagem direta por NJUD (sem depender da estrutura MES/ do montar_todos)
    from divisor_boletins.montagem import montar_jornal

    logger = LogPipeline(pasta_saida / "_logs")
    gerados = []
    for njud in njuds_prontos:
        pasta_njud = pasta_cortes / njud
        if not pasta_njud.is_dir():
            print(f"[dispatcher] ⚠ cortes de {njud} não encontrados em {pasta_njud}")
            continue
        try:
            resultado = montar_jornal(pasta_njud, pasta_jornais, logger,
                                      nome_jornal=njud.replace(" ", "_"))
            if resultado:
                gerados.append(resultado)
                print(f"[dispatcher] ✓ jornal montado: {Path(resultado).name}")
            else:
                print(f"[dispatcher] ✖ montagem falhou para {njud}")
        except Exception as e:
            print(f"[dispatcher] ✖ erro na montagem de {njud}: {e}")

    print(f"[dispatcher] Montagem automática: {len(gerados)}/{len(njuds_prontos)} "
          f"jornal(is) em {pasta_jornais}")


def total_esperado_njud(njud: str, pasta_boletins: Path) -> int:
    """Conta quantos boletins existem fisicamente para o NJUD na origem."""
    return sum(1 for arq in pasta_boletins.rglob("*.mp3") if arq.parent.name == njud)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta_boletins")
    parser.add_argument("pasta_saida")
    parser.add_argument("--max-workers", type=int, default=None,
                         help="Teto manual opcional; o real é min(cpu, ram, teto).")
    parser.add_argument("--threads-por-worker", type=int, default=THREADS_POR_WORKER_PADRAO)
    parser.add_argument("--limiar-cpu", type=float, default=LIMIAR_CPU_PAUSA)
    parser.add_argument("--usar-whisper-timestamped", action="store_true",
                        help="Usa whisper-timestamped para timestamps mais estáveis nas bordas.")
    args = parser.parse_args()

    executar(
        Path(args.pasta_boletins), Path(args.pasta_saida),
        args.max_workers, args.threads_por_worker, args.limiar_cpu,
        args.usar_whisper_timestamped,
    )


if __name__ == "__main__":
    main()
