"""
core/processamento/processar_boletim.py — versão final revisada

Ponto de entrada ÚNICO para processar um boletim de áudio.
Substitui todos os scripts de processamento individuais.

USO:
    python -m core.processamento.processar_boletim <njud|giro> <pasta_boletins> <pasta_saida>
"""

from __future__ import annotations

import gc
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# --- Dependências do projeto ---
from divisor_boletins.audio import processar_arquivo, carregar_modelo
from divisor_boletins.log import LogPipeline

# --- Auditoria única consolidada (PREFERIDA sobre individual_cuts) ---
from core.auditoria.regras import (
    Auditor,
    Auditavel,
    analisar_par_consolidado,
)

# --- Separação de stems (opcional, etapa anterior ao corte) ---
from core.stems.separacao_stems import (
    separar_stems,
    ConfigSeparacao,
    SeparacaoStemsError,
)

# --- Remoção de vinheta de boletim (Camada A / Fase 2) ---
from core.audio.remocao_vinheta import remover_vinheta_boletim

import uuid


@dataclass
class ConfigPrograma:
    """Configuração de um programa (NJUD ou Giro)."""
    nome: str  # "njud" ou "giro"
    pasta_boletins: Path
    pasta_saida: Path
    pasta_estado: Path
    pasta_log: Path
    modelo_whisper: str = "tiny"
    compute_type: str = "int8"
    roteiro_corte: Optional[str] = None
    minimo_boletins_para_montar: int = 4
    usar_separacao_stems: bool = False
    config_stems: ConfigSeparacao = field(default_factory=ConfigSeparacao)
    # Janela de datas do plano (para filtragem por período no Giro)
    data_inicio_coleta: Optional[str] = None  # "YYYY-MM-DD"
    data_fim_coleta: Optional[str] = None  # "YYYY-MM-DD"


@dataclass
class EstadoArquivo:
    """Estado persisitido de um arquivo no pipeline unificado.

    Compatível com pipeline.single_process.EstadoArquivo para
    reutilização do ciclo_arquivo quando disponível.
    """
    arquivo: str
    programa: str
    njud: str = ""  # vazio para Giro (que não usa NJUD)
    status: str = "PENDENTE"
    estrategia_atual: str = "calibracao_correlacao"
    tentativas: list = field(default_factory=list)
    erro: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "EstadoArquivo":
        known = {"arquivo", "programa", "njud", "status", "estrategia_atual", "tentativas", "erro"}
        filtered = {k: v for k, v in dados.items() if k in known}
        if "tentativas" in filtered and filtered["tentativas"]:
            filtered["tentativas"] = [
                {**t} for t in filtered["tentativas"]
            ]
        return cls(**filtered)


def carregar_estado(arquivo: str, programa: str, njud: str, pasta_estado: Path) -> EstadoArquivo:
    """Carrega ou cria estado persistido por arquivo."""
    caminho = pasta_estado / f"{Path(arquivo).stem}.json"
    if caminho.exists():
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            return EstadoArquivo.from_dict(dados)
        except Exception:
            pass
    return EstadoArquivo(arquivo=arquivo, programa=programa, njud=njud)


def salvar_estado(estado: EstadoArquivo, pasta_estado: Path) -> None:
    """Persiste estado no disco."""
    caminho = pasta_estado / f"{Path(estado.arquivo).stem}.json"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(
        json.dumps(estado.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def listar_tarefas_pendentes(config: ConfigPrograma) -> list[dict]:
    """Lista arquivos MP3 sem estado OK/ESGOTADO_ACEITO, filtrados pela janela de datas se configurada."""
    import re
    from datetime import date
    tarefas = []
    data_inicio = None
    data_fim = None
    if config.data_inicio_coleta and config.data_fim_coleta:
        data_inicio = date.fromisoformat(config.data_inicio_coleta)
        data_fim = date.fromisoformat(config.data_fim_coleta)

    for arq in sorted(config.pasta_boletins.rglob("*.mp3")):
        # Sem janela de datas configurada → lista tudo sem estado
        if data_inicio is None or data_fim is None:
            caminho_estado = config.pasta_estado / f"{arq.stem}.json"
            if caminho_estado.exists():
                try:
                    status = json.loads(caminho_estado.read_text(encoding="utf-8")).get("status")
                    if status in ("OK", "ESGOTADO_ACEITO"):
                        continue
                except Exception:
                    pass
            tarefas.append({"arquivo": str(arq), "stem": arq.stem})
            continue

        # Filtro de janela de datas (Giro): extrai data via regex
        m = re.search(r'BOLETIM_RADIO_TJRN_(\d{2})_(\d{2})_(\d{4})_', arq.name)
        if not m:
            continue
        try:
            dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dt_arq = date(ano, mes, dia)
            if not (data_inicio <= dt_arq <= data_fim):
                continue
        except ValueError:
            continue

        caminho_estado = config.pasta_estado / f"{arq.stem}.json"
        if caminho_estado.exists():
            try:
                status = json.loads(caminho_estado.read_text(encoding="utf-8")).get("status")
                if status in ("OK", "ESGOTADO_ACEITO"):
                    continue
            except Exception:
                pass
        tarefas.append({"arquivo": str(arq), "stem": arq.stem})
    return tarefas


def classificar_motivo(motivos: list[str]) -> str:
    """Traduz motivos textuais da auditoria em categoria estruturada."""
    texto = " ".join(motivos).lower()
    if "proporção de corte" in texto or "fallback" in texto:
        return "fallback_audio_completo"
    if "borda colada" in texto or "0.00s do início" in texto:
        return "borda_colada"
    if "conectivo isolado" in texto or "pontuação" in texto:
        return "conectivo_isolado"
    if "alucinacao" in texto or "alucinação" in texto:
        return "alucinacao_whisper"
    if "duracao muito curto" in texto or "muito curto" in texto:
        return "duracao_curta"
    if "duracao muito longo" in texto or "muito longo" in texto:
        return "duracao_longa"
    return "desconhecido"


def processar_um_arquivo(
    arquivo: str,
    config: ConfigPrograma,
    modelo,
    logger: LogPipeline,
) -> EstadoArquivo:
    """
    Processa UM arquivo: corte + auditoria com a regra SemFallback obrigatória.

    Esta é a versão do ciclo de corte+auditoria que usa a auditoria
    consolidada (core/auditoria/regras.py) em vez de analisar_par
    legado. Se pipeline.single_process.ciclo_arquivo estiver disponível,
    ele será usado como orquestrador — caso contrário, roda o ciclo
    manualmente aqui.
    """
    estado = carregar_estado(arquivo, config.nome, "", config.pasta_estado)
    if estado.status in ("OK", "ESGOTADO_ACEITO"):
        return estado

    pasta_cortes = config.pasta_saida / "JORNAIS_DIVIDIDOS"
    pasta_cortes.mkdir(parents=True, exist_ok=True)

    # Etapa 0 (opcional): separação de stems para remover trilha/vinheta
    arquivo_para_corte = arquivo
    if config.usar_separacao_stems:
        try:
            resultado_stems = separar_stems(arquivo, config.config_stems)
            if resultado_stems.sucesso:
                arquivo_para_corte = resultado_stems.caminho_vocal
                logger.info(
                    "stems",
                    f"Stems separados: {Path(arquivo).name} "
                    f"(cache={'hit' if resultado_stems.veio_do_cache else 'miss'}, "
                    f"{resultado_stems.tempo_processamento_s:.1f}s)",
                )
            else:
                logger.aviso(
                    "stems",
                    f"Falha na separação para {Path(arquivo).name}: {resultado_stems.erro}. "
                    f"Prosseguindo com áudio original.",
                )
        except SeparacaoStemsError as exc:
            logger.aviso(
                "stems",
                f"Falha na separação para {Path(arquivo).name}: {exc}. "
                f"Prosseguindo com áudio original.",
            )
    else:
        # Camada A: tenta remover apenas a vinheta de boletim via
        # detecção por transcrição. Rede de segurança leve quando
        # Demucs está desabilitado (caso atual de todos os giro_*.json).
        try:
            _project_root = Path(__file__).resolve().parents[3]
            vinheta_ref = _project_root / "assets" / "vinhetas" / "boletim" / "VHT_ABERTURA_BOLETIM.mp3"
            audio_limpo = remover_vinheta_boletim(Path(arquivo), vinheta_ref)
            if audio_limpo is not None:
                tmp_dir = Path("data/tmp")
                tmp_dir.mkdir(parents=True, exist_ok=True)
                arquivo_para_corte = tmp_dir / f"sem_vinheta_{uuid.uuid4().hex}.wav"
                audio_limpo.export(str(arquivo_para_corte), format="wav")
                logger.info(
                    "Vinheta de boletim removida antes do corte: %s",
                    Path(arquivo).name,
                )
            else:
                # Não detectada (ou erro) — segue com o áudio original.
                # RegraVinhetaBoletimAusente (Camada C) pega o caso residual.
                arquivo_para_corte = arquivo
        except Exception as exc:
            logger.aviso(
                "vinheta",
                f"Falha ao tentar remover vinheta para {Path(arquivo).name}: {exc}. "
                f"Prosseguindo com áudio original.",
            )
            arquivo_para_corte = arquivo

    estrategias = [
        "calibracao_correlacao",
        "ancora_vad_forcado",
        "janela_silencio_ampliada",
        "grade_fixa_locucao_estendida",
    ]
    max_tentativas = len(estrategias)

    while len(estado.tentativas) < max_tentativas:
        estrategia = estado.estrategia_atual

        try:
            resultado = processar_arquivo(
                arquivo_para_corte,
                str(pasta_cortes),
                modelo,
                logger,
                apply=True,
                estrategia=estrategia,
            )
            if resultado is None:
                raise RuntimeError("processar_arquivo retornou None")

            cabeca, corpo = resultado.arquivo_cabeca, resultado.arquivo_corpo

            # Auditoria com fonte original para RegraSemFallback obrigatória
            audit_status, audit_motivos = analisar_par_consolidado(
                cabeca, corpo,
                caminho_fonte_original=arquivo,
            )

            estado.tentativas.append({
                "estrategia": estrategia,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "resultado": audit_status,
                "motivo": audit_motivos,
            })

            if audit_status == "OK":
                estado.status = "OK"
                salvar_estado(estado, config.pasta_estado)
                return estado

            # Classifica motivo e decide próxima estratégia
            motivo_classificado = classificar_motivo(audit_motivos)
            proxima = _proxima_estrategia(estado, motivo_classificado, estrategias)
            if proxima is None:
                estado.status = "ESGOTADO"
                salvar_estado(estado, config.pasta_estado)
                return estado

            estado.estrategia_atual = proxima
            salvar_estado(estado, config.pasta_estado)

        except Exception as e:
            estado.status = "ERRO"
            estado.erro = str(e)
            estado.tentativas.append({
                "estrategia": estrategia,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "resultado": "ERRO",
                "motivo": [str(e)],
            })
            salvar_estado(estado, config.pasta_estado)
            return estado

    estado.status = "ESGOTADO"
    salvar_estado(estado, config.pasta_estado)
    return estado


def _proxima_estrategia(estado: EstadoArquivo, motivo: str, estrategias: list[str]) -> Optional[str]:
    """Decide próxima estratégia baseado no motivo e histórico."""
    ja_tentadas = {t.get("estrategia") for t in estado.tentativas}

    mapeamento = {
        "fallback_audio_completo": "ancora_vad_forcado",
        "borda_colada": "janela_silencio_ampliada",
        "conectivo_isolado": "grade_fixa_locucao_estendida",
        "alucinacao_whisper": "janela_silencio_ampliada",
        "duracao_curta": "ancora_vad_forcado",
        "duracao_longa": "grade_fixa_locucao_estendida",
        "desconhecido": None,
    }

    sugerida = mapeamento.get(motivo)
    if sugerida and sugerida not in ja_tentadas:
        return sugerida

    for e in estrategias:
        if e not in ja_tentadas:
            return e

    return None


def processar_lote(config: ConfigPrograma, gc_a_cada_n: int = 10) -> dict:
    """Processa todas as tarefas pendentes."""
    config.pasta_estado.mkdir(parents=True, exist_ok=True)
    config.pasta_log.parent.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

    logger = LogPipeline(config.pasta_log)

    print(f"[processamento] Carregando modelo Whisper ({config.modelo_whisper}, {config.compute_type})...")
    modelo = carregar_modelo()
    print("[processamento] Modelo carregado.")

    tarefas = listar_tarefas_pendentes(config)
    print(f"[processamento] {len(tarefas)} tarefa(s) pendente(s) de {config.nome}.")

    if not tarefas:
        print("[processamento] Nada a fazer — todos os boletins já processados.")
        return {"total": 0, "ok": 0, "esgotado": 0, "erro": 0}

    resultados: dict[str, int] = {"total": len(tarefas), "ok": 0, "esgotado": 0, "erro": 0}

    for idx, tarefa in enumerate(tarefas):
        arquivo = tarefa["arquivo"]
        print(f"[{idx+1}/{len(tarefas)}] {Path(arquivo).name}")

        try:
            estado = processar_um_arquivo(arquivo, config, modelo, logger)
            print(f"  -> {estado.status}")
            if estado.status == "OK":
                resultados["ok"] += 1
            elif estado.status == "ESGOTADO":
                resultados["esgotado"] += 1
            else:
                resultados["erro"] += 1
        except Exception as exc:
            print(f"  -> ERRO: {exc}")
            resultados["erro"] += 1

        if (idx + 1) % gc_a_cada_n == 0:
            gc.collect()
            print(f"  [memoria] GC. {resultados}")

    print(f"\n=== CONCLUÍDO ({config.nome}) ===\n{json.dumps(resultados, indent=2)}")
    return resultados


def main():
    """Entry point CLI."""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m core.processamento.processar_boletim <njud|giro> <pasta_boletins> <pasta_saida>")
        sys.exit(1)

    programa = sys.argv[1].lower()
    if programa not in ("njud", "giro"):
        print("Programa deve ser 'njud' ou 'giro'")
        sys.exit(1)

    pasta_boletins = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("JORNAIS")
    pasta_saida = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data/processed/PRODUCAO_2026")

    # Flags opcionais
    usar_stems = "--stems" in sys.argv
    roteiro_corte = None
    minimo = 4 if programa == "njud" else 3

    if programa == "giro":
        roteiro_corte = "GIRO_CABEÇA_CORPO"

    config = ConfigPrograma(
        nome=programa,
        pasta_boletins=pasta_boletins,
        pasta_saida=pasta_saida,
        pasta_estado=pasta_saida / "estado_por_arquivo",
        pasta_log=pasta_saida / "_logs",
        roteiro_corte=roteiro_corte,
        minimo_boletins_para_montar=minimo,
        usar_separacao_stems=usar_stems,
    )

    return processar_lote(config)


if __name__ == "__main__":
    main()
