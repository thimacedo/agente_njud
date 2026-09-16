#!/usr/bin/env python3
"""
gerar_programas_giro_v2.py — Retoma da onde parou (após crash).
- Só integra boletins que ainda NÃO têm nota correspondente
- Só monta programas cujas notas já estão completas
"""
import sys, re, json, logging, shutil
from pathlib import Path
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

from config.giro import settings as giro_settings
PROGRAMAS_DIR = giro_settings.DIR_OUTPUT

def get_data_terça(mmss: str) -> str:
    try:
        t = terça_do_programa(mmss)
        return t.strftime("%d-%m-%y")
    except (ValueError, TypeError):
        pass
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
    logger.info("GERAR PROGRAMAS GIRO — RETOMADA (pós-crash)")
    logger.info(f"Cortes:  {OUTPUT_DIR}")
    logger.info(f"Notas:   {NOTES_DIR}")
    logger.info(f"Programas: {PROGRAMAS_DIR}")
    logger.info("=" * 60)

    stats = {"notas_geradas": 0, "boletims_pulados": 0, "erros_integracao": 0,
             "programas_ok": 0, "programas_erro": 0, "semanas_total": 0,
             "semanas_com_notas": 0, "semanas_sem_notas": 0}

    # --- Dirs ---
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    PROGRAMAS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Detectar semanas já com notas ---
    semanas_com_notas = {}
    for semana_dir in NOTES_DIR.iterdir():
        if not semana_dir.is_dir():
            continue
        mmss = semana_dir.name
        notas_ja = list(semana_dir.glob("*.mp3"))
        semanas_com_notas[mmss] = {p.stem for p in notas_ja}
        logger.info(f"  Semana {mmss}: {len(notas_ja)} notas já existentes")

    # --- Listar todas as semanas nos cortes ---
    semana_dirs = sorted(
        d for d in OUTPUT_DIR.iterdir()
        if d.is_dir() and re.match(r"^\d{4}$", d.name)
    )
    stats["semanas_total"] = len(semana_dirs)
    logger.info(f"\n{len(semana_dirs)} semanas no output")

    notes_by_mmss = defaultdict(list)

    # Pre-popular com notas já existentes
    for mmss, stems in semanas_com_notas.items():
        for stem in stems:
            nota_path = NOTES_DIR / mmss / f"{stem}.mp3"
            if nota_path.exists():
                notes_by_mmss[mmss].append(nota_path)

    # ================================================================
    # ETAPA 1: Integrar NOTAS FALTANTES
    # ================================================================
    logger.info("\n[1/2] Integrando notas FALTANTES (pular as que já existem)...")
    for semana_dir in semana_dirs:
        mmss = semana_dir.name
        cortes_dir = semana_dir / "cortes"
        if not cortes_dir.is_dir():
            logger.warning(f"{mmss}: sem pasta 'cortes'")
            stats["boletims_pulados"] += 1
            continue

        data_terça = get_data_terça(mmss)
        notas_existentes = {p.stem for p in (NOTES_DIR / mmss).glob("*.mp3")} if (NOTES_DIR / mmss).exists() else set()

        cortes_boletim = sorted(cortes_dir.iterdir())
        n_total = 0
        n_ok = 0
        n_pulado = 0
        n_faltam = 0

        for bl_dir in cortes_boletim:
            if not bl_dir.is_dir():
                continue
            m = re.search(r"_B(\d+)_", bl_dir.name)
            if not m:
                n_pulado += 1
                continue
            idx = int(m.group(1))
            esperado = f"GNC_{mmss}_N{idx:02d}_{data_terça}"
            if esperado in notas_existentes:
                n_total += 1
                continue  # Já existe

            n_faltam += 1
            cab_files = list(bl_dir.glob("vocals_CABECA.wav"))
            cor_files = list(bl_dir.glob("vocals_CORPO.wav"))

            if not cab_files or not cor_files:
                logger.warning(f"  {mmss}/{bl_dir.name}: faltam CABEÇA/CORPO")
                n_pulado += 1
                stats["boletims_pulados"] += 1
                continue

            cab_path = cab_files[0]
            cor_path = cor_files[0]
            nota_name = f"{esperado}.mp3"
            nota_path = NOTES_DIR / mmss / nota_name
            nota_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                cab = AudioSegment.from_wav(str(cab_path))
                cor = AudioSegment.from_wav(str(cor_path))
                nota = normalize(cab + cor)
                nota.export(str(nota_path), format="mp3", bitrate="192k")
                notes_by_mmss[mmss].append(nota_path)
                notas_existentes.add(esperado)
                n_ok += 1
                stats["notas_geradas"] += 1
                logger.info(f"  ✓ {mmss}/{nota_name} ({len(nota)/1000:.1f}s)")
            except Exception as e:
                logger.error(f"  ✗ {mmss}/{nota_name}: {e}")
                n_pulado += 1
                stats["erros_integracao"] += 1

        total_esperado = n_ok + n_faltam + n_pulado
        logger.info(f"  {mmss}: {n_ok} geradas, {n_faltam} faltantes → {n_total}/{total_esperado} notas")

    # Contar semanas completas
    for mmss in notes_by_mmss:
        if notes_by_mmss[mmss]:
            stats["semanas_com_notas"] += 1
        else:
            stats["semanas_sem_notas"] += 1

    logger.info(f"\nNotas geradas nesta rodada: {stats['notas_geradas']}")
    logger.info(f"Total notas: {sum(len(v) for v in notes_by_mmss.values())}")
    logger.info(f"Semanas com notas: {stats['semanas_com_notas']}/{stats['semanas_total']}")

    # ================================================================
    # ETAPA 2: Montar programas
    # ================================================================
    logger.info("\n[2/2] Montando programas...")
    from giro.montagem import montar_programa

    programas_gerados = []
    for mmss in sorted(notes_by_mmss.keys()):
        notas = sorted(notes_by_mmss[mmss])
        if not notas:
            continue
        data_terça = get_data_terça(mmss)
        logger.info(f"  Montando GNC_{mmss} ({len(notas)} notas)...")
        try:
            caminho = montar_programa(mmss, notas, data_terça=data_terça, logger=logger)
            if caminho:
                tamanho_mb = caminho.stat().st_size / (1024 * 1024)
                logger.info(f"    ✓ {caminho.name} ({tamanho_mb:.1f} MB)")
                programas_gerados.append(caminho)
                stats["programas_ok"] += 1
            else:
                logger.error(f"    ✗ falha na montagem")
                stats["programas_erro"] += 1
        except Exception as e:
            logger.error(f"    ✗ erro: {e}")
            stats["programas_erro"] += 1

    # RESUMO
    logger.info(f"\n{'='*60}")
    logger.info("RESUMO FINAL — RETOMADA")
    logger.info(f"{'='*60}")
    logger.info(f"Semanas total:       {stats['semanas_total']}")
    logger.info(f"Semanas com notas:   {stats['semanas_com_notas']}")
    logger.info(f"Notas geradas agora:  {stats['notas_geradas']}")
    logger.info(f"Programas montados:   {len(programas_gerados)}")
    logger.info(f"Programas com erro:   {stats['programas_erro']}")

    if programas_gerados:
        logger.info(f"\nProgramas gerados:")
        for p in sorted(programas_gerados):
            st = p.stat()
            logger.info(f"  {p.relative_to(ROOT)}  ({st.st_size/(1024*1024):.1f} MB)")

    semanas_sem_programa = sorted(
        mmss for mmss in notes_by_mmss
        if not any((NOTES_DIR / mmss / f"GNC_{mmss}_N{n:02d}_*").exists()
                   for n in range(1, 11))
    )
    if semanas_sem_programa:
        logger.info(f"\n⚠ Semanas sem programa (nenhuma nota):")
        for s in semanas_sem_programa:
            logger.info(f"  - {s}")

    # Relatório
    report = {
        "status": "concluido" if stats["programas_erro"] == 0 else "com_erro",
        "retomada": True,
        "total_programas": len(programas_gerados),
        "programas_gerados": sorted(p.name for p in programas_gerados),
        "notas_geradas_nesta_rodada": stats["notas_geradas"],
        "total_notas_existentes": sum(len(v) for v in notes_by_mmss.values()),
        "estatisticas": stats,
    }
    report_path = LOGS_DIR / "gerar_programas_retomada_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"\nRelatório: {report_path}")

    return 0 if stats["programas_erro"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
