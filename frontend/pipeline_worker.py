"""Run the current audio pipelines in a cancellable child process.

The result manifest is written only after an actual output has been produced.
Each invocation receives private input/output directories from the server.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from datetime import date
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / 'scripts_pipeline'))


def processar(tipo: str, entrada: Path, saida: Path) -> Path:
    from pydub import AudioSegment

    saida.mkdir(parents=True, exist_ok=True)
    # Decode accepted formats into MP3 for pipelines whose input is MP3-only.
    preparados = saida / 'entrada'
    preparados.mkdir()
    inputs = sorted(p for p in entrada.iterdir() if p.is_file())
    if not inputs:
        raise ValueError('Nenhum áudio de entrada')
    for p in inputs:
        AudioSegment.from_file(str(p)).export(str(preparados / f'{p.stem}.mp3'), format='mp3')

    if tipo == 'boletins':
        if len(inputs) != 1:
            raise ValueError('Boletins espera exatamente 1 áudio')
        from boletim.processar_boletim_canonico import processar_canonico
        audio = next(preparados.glob('*.mp3'))
        resultado = processar_canonico(audio)
        if resultado.get('erro'):
            raise RuntimeError(resultado['erro'])
        pasta = audio.parent / f'{audio.stem}_saida'
        outputs = [pasta / item['arquivo'] for item in resultado.get('boletims_gerados', [])]
        if not outputs or any(not p.is_file() or not p.stat().st_size for p in outputs):
            raise RuntimeError('Nenhum boletim válido gerado')
        if len(outputs) == 1:
            return outputs[0]
        arquivo = saida / 'boletins.zip'
        with zipfile.ZipFile(arquivo, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in outputs:
                z.write(p, p.name)
        return arquivo

    if tipo == 'njud':
        if len(inputs) != 4:
            raise ValueError('NJUD exige exatamente 4 boletins')
        from divisor_boletins.__main__ import dividir
        from montagem_jornais import montar_jornal
        cortes = saida / 'cortes'
        if dividir(preparados, cortes, aplicar=True) != 0:
            raise RuntimeError('Falha na divisão dos boletins NJUD')
        output = montar_jornal(cortes, saida, logger=logging.getLogger('njud.web'))
    elif tipo == 'giro':
        from giro.giro_montar_gnc import montar_gnc
        output = montar_gnc(entrada.name, sorted(preparados.glob('*.mp3')),
                           date.today().strftime('%d-%m-%Y'), pasta_saida=saida)
    else:
        raise ValueError(f'Tipo inválido: {tipo}')

    if output is None or not output.is_file() or not output.stat().st_size:
        raise RuntimeError('Nenhum programa válido gerado')
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tipo', choices=['boletins', 'njud', 'giro'])
    parser.add_argument('entrada', type=Path)
    parser.add_argument('saida', type=Path)
    args = parser.parse_args()
    output = processar(args.tipo, args.entrada, args.saida)
    (args.saida / 'resultado.json').write_text(
        json.dumps({'output_path': str(output.resolve())}), encoding='utf-8')


if __name__ == '__main__':
    main()
