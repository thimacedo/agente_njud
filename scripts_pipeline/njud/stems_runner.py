"""Executa stems no ambiente isolado configurado, sem alterar .venv_pipeline."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    base = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifesto", type=Path)
    parser.add_argument("destino", type=Path)
    parser.add_argument("--config", type=Path, default=base/"config/njud_stems_runtime.json")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    python = Path(config["python"]); deps = Path(config["dependencias"])
    if not python.is_file() or not (deps/"demucs/pretrained.py").is_file():
        raise SystemExit("Ambiente isolado de stems indisponível; conferir configuração")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(deps) + os.pathsep + str(base/"scripts_pipeline")
    raise SystemExit(subprocess.call([str(python), "-m", "njud.stems", str(args.manifesto.resolve()),
                                     str(args.destino.resolve()), "--repositorio-modelo", config["repositorio_modelo"]], env=env))


if __name__ == "__main__":
    main()
