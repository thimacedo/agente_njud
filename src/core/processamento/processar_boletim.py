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

# --- Novos imports para fases 3-5 ---
from typing import TYPE_CHECKING

try:
    from core.fila.queue_client import FilaClient
    FILA_DISPONIVEL = True
except ImportError:
    FILA_DISPONIVEL = False

try:
    from core.aprendizado.knowledge_base import KnowledgeBase
    KB_DISPONIVEL = True
except ImportError:
    KB_DISPONIVEL = False

try:
    from core.decisao.analisador import decidir_estrategia, PlanoDeProcessamento
    ANALISADOR_DISPONIVEL = True
except ImportError:
    ANALISADOR_DISPONIVEL = False


@dataclass
class ConfigPrograma:
    """Configuração de um programa (NJUD, GIRO ou BOLETIM)."""
    nome: str  # "njud", "giro" ou "boletim"
    pasta_boletins: Path
    pasta_saida: Path
    pasta_estado: Path
    pasta_log: Path
    modelo_whisper: str = "tiny"
    compute_type: str = "int8"
    roteiro_corte: Optional[str] = None
    minimo_boletins_para_montar: int = 4
    max_boletins_por_programa: int = 6  # Limite superior: máximo 6 boletins por programa
    modo_dual: bool = False  # Fase 3: roda auditoria síncrona E fila em paralelo
    analisador_ativo: bool = False  # Fase 5: usa Analisador em vez de JSON estático
    fila: Optional[FilaClient] = field(default=None)  # instância compartilhada
    usar_separacao_stems: bool = False
    config_stems: ConfigSeparacao = field(default_factory=ConfigSeparacao)
    # Janela de dados do plano (para filtragem por período no Giro)
    data_inicio_coleta: Optional[str] = None  # "YYYY-MM-DD"
    data_fim_coleta: Optional[str] = None  # "YYYY-MM-DD"
    # Fase 1-2: usa staging em vez de pastas fixas
    usar_staging: bool = True  # Se True, monta pasta_boletins a partir de data/staging/PROGRAMA/data
    data_programa: Optional[str] = None  # "YYYY-MM-DD" — data para staging


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
    """Lista arquivos MP3 sem estado OK/ESGOTADO_ACEITO, filtrados pela janela de datas se configurada.
    
    Aplica max_boletins_por_programa para limitar a coleta e evitar supercoleta
    que causa 10-41 notas por programa (Fase 1 do plano de correção).
    """
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

    # Aplicar limite máximo de boletins por programa (Fase 1)
    # Filtra versões duplicadas e limita a N boletins (cada boletim = CABEÇA + CORPO = 2 arquivos)
    if config.max_boletins_por_programa:
        # Filtrar apenas boletins principais (sem _v2, _RESTORED, _1782542963, etc.)
        boletins_principais = []
        for t in tarefas:
            nome = t["stem"]
            if "_v2" in nome or "_RESTORED" in nome or "__" in nome:
                continue
            boletins_principais.append(t)
        
        # Ordenar por número de boletim (B1, B2, ... B10) para priorizar os primeiros
        def num_boletim(t):
            m = re.search(r'B(\d+)', t["stem"])
            return int(m.group(1)) if m else 999
        
        boletins_principais.sort(key=num_boletim)
        
        # Cada boletim tem 2 arquivos (CABEÇA + CORPO), então limite = max_boletins * 2
        limite_arquivos = config.max_boletins_por_programa * 2
        if len(boletins_principais) > limite_arquivos:
            boletins_principais = boletins_principais[:limite_arquivos]
        
        tarefas = boletins_principais

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

    pasta_cortes = config.pasta_saida / "cortes"
    pasta_cortes.mkdir(parents=True, exist_ok=True)

    # Cria subdiretório por boletim para não sobrescrever arquivos
    nome_boletim = Path(arquivo).stem
    pasta_boletim = pasta_cortes / nome_boletim
    pasta_boletim.mkdir(parents=True, exist_ok=True)

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

    # --- Decisão adaptativa de estratégia (NOVO — Fase 5) ---
    decisao_id = uuid.uuid4().hex
    plano = None
    features_decisao = {}
    usou_analisador = False

    if config.analisador_ativo and ANALISADOR_DISPONIVEL:
        try:
            kb = KnowledgeBase() if KB_DISPONIVEL else None
            plano = decidir_estrategia(
                caminho_audio=Path(arquivo),
                programa=config.nome,
                kb=kb,
                tentativas_anteriores=estado.tentativas,
            )
            features_decisao = {
                "duracao_s": plano.features.duracao_s,
                "energia_inicio_db": plano.features.energia_media_inicio_db,
                "energia_fim_db": plano.features.energia_media_fim_db,
                "proporcao_silencio_inicio": plano.features.proporcao_silencio_inicio,
            }
            logger.info(
                "analisador",
                f"Decisão adaptativa para {Path(arquivo).name}: "
                f"stems={plano.usar_stems}, estrategia={plano.estrategia_sugerida}. "
                f"Motivo: {plano.justificativa}",
            )
            usou_analisador = True
        except Exception as exc:
            logger.aviso(
                "analisador",
                f"Erro ao decidir estratégia para {Path(arquivo).name}: {exc}. "
                f"Voltando ao JSON estático.",
            )
            plano = None
            usou_analisador = False

    # Etapa 0 (opcional): separação de stems para remover trilha/vinheta
    arquivo_para_corte = arquivo
    usar_stems = False

    # Se Analisador sugeriu stems, usa-o; senão usa o JSON config
    if plano and plano.usar_stems:
        usar_stems = True
    elif config.usar_separacao_stems:
        usar_stems = True

    if usar_stems:
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

    # --- Escolha de estratégia (MODIFICADO — Fase 5) ---
    estrategias = [
        "calibracao_correlacao",
        "ancora_vad_forcado",
        "janela_silencio_ampliada",
        "grade_fixa_locucao_estendida",
    ]
    max_tentativas = len(estrategias)

    # Se Analisador sugeriu estratégia específica, começa por ela
    if plano:
        if plano.estrategia_sugerida in estrategias:
            idx = estrategias.index(plano.estrategia_sugerida)
            estrategias = estrategias[idx:] + estrategias[:idx]

    # ========== LOOP DE ESTRATÉGIAS (código original mantido, só acrescenta auditoria à fila) ==========

    while len(estado.tentativas) < max_tentativas:
        estrategia = estado.estrategia_atual

        try:
            resultado = processar_arquivo(
                arquivo_para_corte,
                str(pasta_boletim),
                modelo,
                logger,
                apply=True,
                estrategia=estrategia,
            )
            if resultado is None:
                raise RuntimeError("processar_arquivo retornou None")

            cabeca, corpo = resultado.arquivo_cabeca, resultado.arquivo_corpo

            # Auditoria SÍNCRONA (código original) — permanece para não quebrar nada
            audit_status, audit_motivos = analisar_par_consolidado(
                cabeca, corpo,
                caminho_fonte_original=arquivo,
            )

            # --- NOVO (Fase 3): Publicar na fila DE AUDITORIA EM PARALELO ---
            if config.modo_dual and FILA_DISPONIVEL and config.fila:
                try:
                    config.fila.publicar(
                        "pendente_auditoria",
                        {
                            "decisao_id": decisao_id,
                            "programa": config.nome,
                            "arquivo_original": arquivo,
                            "cabeca": str(cabeca),
                            "corpo": str(corpo),
                            "estrategia_usada": estrategia,
                            "usou_stems": usar_stems,
                            "usou_analisador": usou_analisador,
                            "features_audio": features_decisao,
                            "resultado_auditoria_síncrona": audit_status,
                            "motivos_síncronos": audit_motivos,
                        },
                    )
                except Exception as exc:
                    logger.aviso(
                        "fila",
                        f"Erro ao publicar em fila para {Path(arquivo).name}: {exc}",
                    )

            estado.tentativas.append(
                {
                    "estrategia": estrategia,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "resultado": audit_status,
                    "motivo": audit_motivos,
                    "usou_analisador": usou_analisador,
                    "decisao_id": decisao_id,
                }
            )

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
            estado.tentativas.append(
                {
                    "estrategia": estrategia,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "resultado": "ERRO",
                    "motivo": [str(e)],
                    "usou_analisador": usou_analisador,
                    "decisao_id": decisao_id,
                }
            )
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

    # Instanciar fila se modo_dual ativado (Fase 3)
    if config.modo_dual and FILA_DISPONIVEL:
        config.fila = FilaClient()

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
    """Entry point CLI.

    Uso:
        python -m core.processamento.processar_boletim <njud|giro|boletim> [flags]

    Flags:
        --data DATA              : data do programa (YYYY-MM-DD) para staging
        --pasta PASTA            : pasta de boletins (ignora se --data usado)
        --saida PASTA            : pasta de saída (padrão: data/processed/PROGRAMA)
        --stems                  : habilita separação de stems (padrão: False)
        --modo-dual              : roda auditoria síncrona E fila em paralelo (Fase 3)
        --analisador-ativo       : usa Analisador adaptativo em vez de JSON (Fase 5)
        --no-staging             : desabilita staging, usa pasta diretamente
    """
    import sys

    if len(sys.argv) < 2:
        print("Uso: python -m core.processamento.processar_boletim <njud|giro|boletim> [flags]")
        print("\nFlags:")
        print("  --data DATA              : data do programa (YYYY-MM-DD) para staging")
        print("  --pasta PASTA            : pasta de boletins (ignora se --data usado)")
        print("  --saida PASTA            : pasta de saída")
        print("  --stems                  : habilita separação de stems")
        print("  --modo-dual              : roda auditoria síncrona E fila em paralelo")
        print("  --analisador-ativo       : usa Analisador adaptativo")
        print("  --no-staging             : desabilita staging, usa pasta diretamente")
        sys.exit(1)

    programa = sys.argv[1].lower()
    if programa not in ("njud", "giro", "boletim"):
        print("Programa deve ser 'njud', 'giro' ou 'boletim'")
        sys.exit(1)

    # Parse de flags
    usar_stems = "--stems" in sys.argv
    modo_dual = "--modo-dual" in sys.argv
    analisador_ativo = "--analisador-ativo" in sys.argv
    usar_staging = "--no-staging" not in sys.argv

    # Extrair --data
    data_programa = None
    if "--data" in sys.argv:
        idx = sys.argv.index("--data")
        if idx + 1 < len(sys.argv):
            data_programa = sys.argv[idx + 1]

    # Extrair --pasta
    pasta_boletins = None
    if "--pasta" in sys.argv:
        idx = sys.argv.index("--pasta")
        if idx + 1 < len(sys.argv):
            pasta_boletins = Path(sys.argv[idx + 1])

    # Extrair --saida
    pasta_saida = None
    if "--saida" in sys.argv:
        idx = sys.argv.index("--saida")
        if idx + 1 < len(sys.argv):
            pasta_saida = Path(sys.argv[idx + 1])

    # Determinar pasta de boletins
    if usar_staging and data_programa:
        # Fase 1-2: ler de data/staging/PROGRAMA/AAAA-MM-DD/
        staging_dir = {"njud": "NJUD", "giro": "GIRO", "boletim": "BOLETIM"}
        pasta_staging = Path("data/staging") / staging_dir[programa] / data_programa
        pasta_boletins = pasta_staging
        print(f"[config] Usando staging: {pasta_boletins}")
    elif pasta_boletins is None:
        pasta_boletins = Path("JORNAIS")

    # Determinar pasta de saída
    if pasta_saida is None:
        pasta_saida = Path(f"data/processed/PRODUCAO_2026/{programa.upper()}")

    # Roteiro de corte
    roteiro_corte = None
    if programa == "giro":
        roteiro_corte = "GIRO_CABEÇA_CORPO"

    # Mínimo de boletins
    minimo = 4 if programa == "njud" else 3

    config = ConfigPrograma(
        nome=programa,
        pasta_boletins=pasta_boletins,
        pasta_saida=pasta_saida,
        pasta_estado=pasta_saida / "estado_por_arquivo",
        pasta_log=pasta_saida / "_logs",
        roteiro_corte=roteiro_corte,
        minimo_boletins_para_montar=minimo,
        usar_separacao_stems=usar_stems,
        modo_dual=modo_dual,
        analisador_ativo=analisador_ativo,
        usar_staging=usar_staging,
        data_programa=data_programa,
    )

    if modo_dual:
        print("[config] Modo dual ativado — auditoria síncrona + fila em paralelo")
    if analisador_ativo:
        print("[config] Analisador adaptativo ativado")

    return processar_lote(config)


if __name__ == "__main__":
    main()
