#!/usr/bin/env python3
"""
Processamento serial de boletins - modelo tiny para estabilidade de memoria.
Processa um arquivo por vez, liberando memoria entre cada um.
"""
import json
import os
import sys
import time
import gc
from pathlib import Path

# Configurar variaveis de ambiente para reduzir uso de memoria
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["MKL_DISABLE_FAST_MM"] = "1"
os.environ["KMP_AFFINITY"] = "disabled"

sys.path.insert(0, str(Path(__file__).parent / "src"))

import torch
torch.set_num_threads(1)
torch.set_num_interop_threads(1)

from config.njud import settings as _settings

from faster_whisper import WhisperModel
from divisor_boletins.audio import processar_arquivo
from divisor_boletins.log import LogPipeline
from audit.individual_cuts import analisar_par
from pipeline.single_process import ciclo_arquivo, EstadoArquivo


class EstadoArquivoUnico:
    """Adapta EstadoProcesso para persistir em UM arquivo por boletim."""
    def __init__(self, caminho, arquivo, njud):
        self.caminho = caminho
        if caminho.exists():
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            from pipeline.single_process import TentativaLog
            tentativas = [TentativaLog(**t) for t in dados.pop("tentativas", [])]
            import dataclasses
            validas = {f.name for f in dataclasses.fields(EstadoArquivo)}
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


def listar_tarefas_pendentes(pasta_boletins, pasta_estado):
    """Lista arquivos MP3 que ainda nao foram processados com sucesso."""
    tarefas = []
    for arq in sorted(pasta_boletins.rglob("*.mp3")):
        njud = arq.parent.name
        caminho_estado = pasta_estado / f"{arq.stem}.json"
        if caminho_estado.exists():
            try:
                status = json.loads(caminho_estado.read_text(encoding="utf-8")).get("status")
                if status in ("OK", "ESGOTADO_ACEITO"):
                    continue
            except:
                pass
        tarefas.append({"arquivo": str(arq), "njud": njud})
    return tarefas


def main():
    pasta_boletins = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/JORNAIS")
    pasta_saida = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/data/processed/PRODUCAO_2026")

    pasta_estado = pasta_saida / "estado_por_arquivo"
    pasta_estado.mkdir(parents=True, exist_ok=True)
    pasta_cortes = pasta_saida / "JORNAIS_DIVIDIDOS"
    pasta_cortes.mkdir(parents=True, exist_ok=True)

    logger = LogPipeline(pasta_saida / "_logs")

    # Carregar modelo Whisper tiny (mais leve, nao trava com pouca RAM)
    print("[processamento] Carregando modelo Whisper (tiny, int8)...")
    modelo = WhisperModel(_settings.MODELO_WHISPER, device="cpu", compute_type=_settings.COMPUTE_TYPE, cpu_threads=1)
    print("[processamento] Modelo carregado.")

    tarefas = listar_tarefas_pendentes(pasta_boletins, pasta_estado)
    print(f"[processamento] {len(tarefas)} tarefa(s) pendente(s).")

    if not tarefas:
        print("[processamento] Nada a fazer.")
        return

    ok_count = 0
    erro_count = 0
    esgotado_count = 0

    for idx, tarefa in enumerate(tarefas):
        arquivo = tarefa["arquivo"]
        njud = tarefa["njud"]
        caminho_estado = pasta_estado / f"{Path(arquivo).stem}.json"
        pasta_destino_njud = pasta_cortes / njud

        print(f"[{idx+1}/{len(tarefas)}] Processando: {Path(arquivo).name}")

        def cortar_fn(arq, estrategia, _modelo=modelo, _logger=logger, _destino=pasta_destino_njud):
            resultado = processar_arquivo(
                arq, _destino, _modelo, _logger, apply=True, estrategia=estrategia,
            )
            if resultado is None:
                raise RuntimeError(f"processar_arquivo falhou para {arq}")
            return resultado.arquivo_cabeca, resultado.arquivo_corpo

        def auditar_fn(cabeca, corpo, _modelo=modelo):
            return analisar_par(cabeca, corpo, _modelo)

        try:
            estado_local = EstadoArquivoUnico(caminho_estado, arquivo, njud)
            resultado = ciclo_arquivo(estado_local, arquivo, njud, cortar_fn, auditar_fn)
            print(f"  -> {resultado.status}")

            if resultado.status == "OK":
                ok_count += 1
            elif resultado.status and "ESGOTADO" in resultado.status:
                esgotado_count += 1

        except Exception as e:
            print(f"  -> ERRO: {e}")
            erro_count += 1
            try:
                caminho_estado.write_text(
                    json.dumps({"arquivo": arquivo, "njud": njud, "status": "ERRO",
                                "erro": str(e)}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except:
                pass

        # Liberar memoria a cada 10 arquivos
        if (idx + 1) % 10 == 0:
            gc.collect()
            import psutil
            mem = psutil.virtual_memory()
            print(f"  [memoria] GC coletado. Livre: {mem.available/1024**3:.1f}GB | Progresso: {ok_count} OK, {esgotado_count} ESGOTADO, {erro_count} ERRO")

    print(f"\n=== CONCLUIDO ===")
    print(f"Total processado: {len(tarefas)}")
    print(f"OK: {ok_count}")
    print(f"ESGOTADO: {esgotado_count}")
    print(f"ERRO: {erro_count}")


if __name__ == "__main__":
    main()
