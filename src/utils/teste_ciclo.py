"""Teste dirigido do ciclo fechado: 1 boletim real, sem multiprocessing.

Valida: cortar -> auditar -> classificar motivo -> escalar estratégia.
Roda com --max-workers 1 equivalente (processo único, serial).
"""
import sys
import json
from pathlib import Path

# Módulos locais (processo_unico etc.) vivem no mesmo diretório deste script.
sys.path.insert(0, str(Path(__file__).parent))

from processo_unico import ciclo_arquivo, EstadoArquivo, TentativaLog
from dataclasses import asdict


class EstadoArquivoUnico:
    """Mesmo contrato de EstadoProcesso, mas persistindo em um JSON por arquivo."""

    def __init__(self, caminho: Path, arquivo: str, njud: str):
        from processo_unico import EstadoArquivo as EA, TentativaLog
        self.caminho = caminho
        if caminho.exists():
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            tentativas = [TentativaLog(**t) for t in dados.pop("tentativas", [])]
            self._e = EA(tentativas=tentativas, **dados)
        else:
            self._e = EA(arquivo=arquivo, njud=njud)

    def obter_ou_criar(self, arquivo, njud):
        return self._e

    def salvar(self):
        from dataclasses import asdict
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(asdict(self._e), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("boletim", help="Caminho de UM mp3 para testar o ciclo")
    parser.add_argument("--saida", default="data/teste_ciclo")
    args = parser.parse_args()

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    pasta_estado = saida / "estado_por_arquivo"

    from faster_whisper import WhisperModel
    from divisor_boletins.audio import processar_arquivo
    from divisor_boletins.log import LogPipeline
    from analisar_cortes_individuais import analisar_par

    logger = LogPipeline(saida / "_logs")
    print("Carregando Whisper...")
    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=2)

    boletim = Path(args.boletim).resolve()
    njud = boletim.parent.name

    def cortar_fn(arq, estrategia):
        destino = saida / "cortes" / njud
        r = processar_arquivo(arq, destino, modelo, logger, apply=True,
                              estrategia=estrategia)
        if r is None:
            raise RuntimeError(f"processar_arquivo falhou ({estrategia})")
        return r.arquivo_cabeca, r.arquivo_corpo

    def auditar_fn(cabeca, corpo):
        return analisar_par(cabeca, corpo, modelo)

    estado = EstadoArquivoUnico(pasta_estado / f"{boletim.stem}.json",
                                str(boletim), njud)
    e = ciclo_arquivo(estado, str(boletim), njud, cortar_fn, auditar_fn)

    print(f"\n=== RESULTADO ===")
    print(f"status final: {e.status}")
    for t in e.tentativas:
        print(f"  [{t.timestamp}] {t.estrategia} -> {t.resultado} {t.motivo}")


if __name__ == "__main__":
    main()
