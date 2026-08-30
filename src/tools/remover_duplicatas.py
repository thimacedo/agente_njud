#!/usr/bin/env python3
"""Etapa 1: Remoção de duplicatas exatas por hash de conteúdo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import csv
import hashlib
from datetime import datetime

try:
    from config.settings import Settings
    settings = Settings()
    BASE = Path(settings.BASE_DIR)
except Exception:
    BASE = Path("F:/Projetos/DIVISOR")

LOGS = BASE / "logs"
DUP_NJUD = LOGS / "relatorio_duplicatas_njud.csv"
DUP_BOLETIM = LOGS / "relatorio_duplicatas_boletim.csv"
LOG_REMOÇÃO = LOGS / "remocao_duplicatas.log"


def file_hash(path: Path, block_size: int = 65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def main():
    print("=== ETAPA 1: REMOÇÃO DE DUPLICATAS EXATAS ===\n")
    LOG_REMOÇÃO.parent.mkdir(parents=True, exist_ok=True)
    log_lines = []
    log_lines.append(f"[{datetime.now().isoformat()}] Iniciando remoção de duplicatas")

    removidos = 0
    erros = 0

    # Processar duplicatas NJUD
    if DUP_NJUD.exists():
        with open(DUP_NJUD, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"Duplicatas NJUD_*: {len(rows)}")

        # Agrupar por hash
        from collections import defaultdict
        grupos = defaultdict(list)
        for row in rows:
            h = row.get("hash", "")
            arq1 = row.get("arquivo1", "")
            arq2 = row.get("arquivo2", "")
            if h and arq1:
                grupos[h].append(Path(arq1))
            if h and arq2:
                grupos[h].append(Path(arq2))

        for h, paths in grupos.items():
            paths_unicos = []
            vistos = set()
            for p in paths:
                if p.exists() and p not in vistos:
                    paths_unicos.append(p)
                    vistos.add(p)
            if len(paths_unicos) > 1:
                # Manter primeiro, remover demais
                manter = paths_unicos[0]
                for p in paths_unicos[1:]:
                    try:
                        if p.exists():
                            p.unlink()
                            log_lines.append(f"REMOVIDO: {p} (hash={h[:12]}...)")
                            removidos += 1
                    except Exception as e:
                        log_lines.append(f"ERRO: {p} -> {e}")
                        erros += 1
    else:
        print("Relatório de duplicatas NJUD não encontrado.")

    # Processar duplicatas BOLETIM
    if DUP_BOLETIM.exists():
        with open(DUP_BOLETIM, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"Duplicatas BOLETIM_RADIO_TJRN*: {len(rows)}")

        from collections import defaultdict
        grupos = defaultdict(list)
        for row in rows:
            h = row.get("hash", "")
            arq1 = row.get("arquivo1", "")
            arq2 = row.get("arquivo2", "")
            if h and arq1:
                grupos[h].append(Path(arq1))
            if h and arq2:
                grupos[h].append(Path(arq2))

        for h, paths in grupos.items():
            paths_unicos = []
            vistos = set()
            for p in paths:
                if p.exists() and p not in vistos:
                    paths_unicos.append(p)
                    vistos.add(p)
            if len(paths_unicos) > 1:
                manter = paths_unicos[0]
                for p in paths_unicos[1:]:
                    try:
                        if p.exists():
                            p.unlink()
                            log_lines.append(f"REMOVIDO: {p} (hash={h[:12]}...)")
                            removidos += 1
                    except Exception as e:
                        log_lines.append(f"ERRO: {p} -> {e}")
                        erros += 1
    else:
        print("Relatório de duplicatas BOLETIM não encontrado.")

    log_lines.append(f"Concluído: removidos={removidos}, erros={erros}")
    LOG_REMOÇÃO.write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nRemovidos: {removidos}")
    print(f"Erros: {erros}")
    print(f"Log: {LOG_REMOÇÃO}")


if __name__ == "__main__":
    main()
