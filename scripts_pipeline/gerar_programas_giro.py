#!/usr/bin/env python3
"""
gerar_programas_giro.py — Integra + monta programas GIRO.
1. Para cada semana: integra vocals_CABECA.wav + vocals_CORPO.wav em notas
2. Monta programas finais GNC_mmss_DD-MM-YY.mp3 com vinhetas
"""
import sys, re, json, logging, shutil
from pathlib import Path, PureWindowsPath
from collections import defaultdict
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydub import AudioSegment
from pydub.effects import normalize
from giro.utils import terça_do_programa
from giro.log import configurar_logger

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "GIRO" / "output"
NOTES_DIR = ROOT / "GIRO" / "notes"
LOGS_DIR = ROOT / "GIRO" / "logs"

# Diretório de saída dos programas montados (padrão settings.py)
from config.giro import settings as giro_settings
PROGRAMAS_DIR = giro_settings.DIR_OUTPUT

def get_data_terça(mmss: str) -> str:
    """Retorna data_terça DD-MM-YY, com fallbacks para cada fonte."""
    # 1. Função da utils
    try:
        t = terça_do_programa(mmss)
        return t.strftime("%d-%m-%y")
    except (ValueError, TypeError):
        pass

    # 2. JSON de planejamento
    for fname in [f"giro_{mmss}.json", f"GIRO_{mmss}.json"]:
        f = ROOT / "config" / "planejamento_2026" / fname
        if f.exists():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                for key in ("data_terça", "data_terça_exibicao", "data"):
                    if key in data:
                        d = date.fromisoformat(data[key][:10])
                        return d.strftime("%d-%m-%y")
            except Exception:
                pass

    # 3. Último fallback: primeira terça do mês
    try:
        mm = int(mmss[:2])
        d = date(2026, mm, 1)
        delta = (1 - d.weekday()) % 7
        return (d + timedelta(days=delta)).strftime("%d-%m-%y")
    except Exception:
        return "01-01-26"

def main():
    logger = configurar_logger(stdout=True)
    logger.info("=" * 60)
    logger.info("GERAR PROGRAMAS GIRO — Integra + Monta")
    logger.info(f"Cortes:  {OUTPUT_DIR}")
    logger.info(f"Notas:   {NOTES_DIR}")
    logger.info(f"Programas: {PROGRAMAS_DIR}")
    logger.info("=" * 60)

    # --- Counter stats ---
    stats = {"notas_integradas": 0, "boletims_pulados": 0, "erros_integracao": 0,
             "programas_ok": 0, "programas_erro": 0}

    # --- Limpar e recriar dirs ---
    if NOTES_DIR.exists():
        shutil.rmtree(NOTES_DIR)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    PROGRAMAS_DIR.mkdir(parents=True, exist_ok=True)

    # ================================================================
    # ETAPA 1: Integrar CABEÇA+CORPO em notas
    # ================================================================
    logger.info("\n[1/2] Integrando notas (vocals_CABECA + vocals_CORPO → GNC_mmss_N{n}.mp3)")
    notes_by_mmss = defaultdict(list)

    semana_dirs = sorted(
        d for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and re.match(r"^\d{4}$", d.name)
    )
    logger.info(f"{len(semana_dirs)} semanas: {', '.join(d.name for d in semana_dirs)}")

    for semana_dir in semana_dirs:
        mmss = semana_dir.name
        cortes_dir = semana_dir / "cortes"
        if not cortes_dir.is_dir():
            logger.warning(f"{mmss}: sem pasta 'cortes', pulando")
            stats["boletims_pulados"] += 1
            continue

        data_terça = get_data_terça(mmss)
        logger.info(f"\n  Semana {mmss} (terça={data_terça}):")

        boletim_dirs = sorted(cortes_dir.iterdir())
        n_ok = 0
        n_pulado = 0

        for bl_dir in boletim_dirs:
            if not bl_dir.is_dir():
                continue

            # Buscar vocals_CABECA e vocals_CORPO no diretório
            cab_files = list(bl_dir.glob("vocals_CABECA.wav"))
            cor_files = list(bl_dir.glob("vocals_CORPO.wav"))

            if not cab_files or not cor_files:
                logger.warning(f"    {bl_dir.name}: faltam CABEÇA/CORPO")
                n_pulado += 1
                stats["boletims_pulados"] += 1
                continue

            cab_path = cab_files[0]
            cor_path = cor_files[0]

            # Extrair índice B{n} do nome do diretório
            m = re.search(r"_B(\d+)_", bl_dir.name)
            if not m:
                logger.warning(f"    {bl_dir.name}: índice B{n} não encontrado")
                n_pulado += 1
                stats["boletims_pulados"] += 1
                continue

            idx = int(m.group(1))
            nota_name = f"GNC_{mmss}_N{idx:02d}_{data_terça}.mp3"
            nota_path = NOTES_DIR / mmss / nota_name
            nota_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                cab = AudioSegment.from_wav(str(cab_path))
                cor = AudioSegment.from_wav(str(cor_path))
                nota = normalize(cab + cor)
                nota.export(str(nota_path), format="mp3", bitrate="192k")
                notes_by_mmss[mmss].append(nota_path)
                n_ok += 1
                stats["notas_integradas"] += 1
                logger.info(f"    ✓ {nota_name} ({len(nota)/1000:.1f}s)")
            except Exception as e:
                logger.error(f"    ✗ {bl_dir.name}: {e}")
                stats["erros_integracao"] += 1
                n_pulado += 1

        logger.info(f"    → {n_ok} notas, {n_pulado} pulados")

    total_notas = sum(len(v) for v in notes_by_mmss.values())
    logger.info(f"\nNotas integradas: {stats['notas_integradas']} (boletims pulados: {stats['boletims_pulados']}, erros: {stats['erros_integracao']})")

    # ================================================================
    # ETAPA 2: Montar programas a partir das notas
    # ================================================================
    logger.info("\n[2/2] Montando programas...")
    from giro.montagem import montar_programa

    programas_gerados = []
    semanas_sem_programa = []

    for mmss in sorted(notes_by_mmss.keys()):
        notas = sorted(notes_by_mmss[mmss])
        if not notas:
            semanas_sem_programa.append(mmss)
            continue

        data_terça = get_data_terça(mmss)
        logger.info(f"\n  Programa GNC_{mmss} ({len(notas)} notas):")
        try:
            caminho = montar_programa(mmss, notas, data_terça=data_terça, logger=logger)
            if caminho:
                duracao = caminho.stat().st_size / (1024 * 1024)
                logger.info(f"    ✓ {caminho.name} ({duracao:.1f} MB)")
                programas_gerados.append(caminho)
                stats["프로그램_ok"] += 1
            else:
                logger.error(f"    ✗ falha montagem")
                stats["프로그램_erro"] += 1
        except Exception as e:
            logger.error(f"    ✗ erro: {e}")
            stats["프로그램_erro"] += 1

    # ================================================================
    # RESUMO FINAL
    # ================================================================
    logger.info(f"\n{'='*60}")
    logger.info("RESUMO FINAL")
    logger.info(f"{'='*60}")
    logger.info(f"Total de semanas: {len(semana_dirs)}")
    logger.info(f"Notas integradas: {stats['notas_integradas']}")
    logger.info(f"Boletim pulados:  {stats['boletims_pulados']}")
    logger.info(f"Erros integração: {stats['erros_integracao']}")
    logger.info(f"Programas montados: {len(programas_gerados)}")
    logger.info(f"Programas com erro: {stats['프로그램_erro']}")
    logger.info(f"Semanas sem programa: {len(semanas_sem_programa)}")

    if programas_gerados:
        logger.info(f"\nProgramas gerados:")
        for p in sorted(programas_gerados):
            st = p.stat()
            logger.info(f"  {p.relative_to(ROOT)}  ({st.st_size/(1024*1024):.1f} MB)")

    # Semanas que ficaram sem programa
    if semanas_sem_programa:
        logger.info(f"\n⚠ Semanas sem programa (nenhuma nota ou erro):")
        for s in semanas_sem_programa:
            logger.info(f"  - {s}")

    # Salvar relatório
    report = {
        "status": "concluido" if stats["프로그램_erro"] == 0 else "com_erro",
        "total_programas": len(programas_gerados),
        "total_notas": stats["notas_integradas"],
        "bem_sucedido": [p.name for p in programas_gerados],
        "sem_programa": semanas_sem_programa,
        "estatisticas": stats,
    }
    report_path = LOGS_DIR / "gerar_programas_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"\nRelatório: {report_path}")

    return 0 if stats["프로그램_erro"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
