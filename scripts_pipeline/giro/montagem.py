"""Montagem GIRO para entradas explícitas, sem sincronização externa."""
import argparse
from pathlib import Path
from pydub import AudioSegment
from pydub.effects import normalize

def montar_programa(codigo, notas, output_dir, data_str, assets_dir=None):
    if not 4 <= len(notas) <= 6:
        raise ValueError('GIRO exige entre 4 e 6 notas')
    assets = Path(assets_dir) if assets_dir else Path(__file__).resolve().parents[2] / 'assets/vinhetas/giro'
    abertura, passagem, encerramento = [
        AudioSegment.from_mp3(str(assets / nome)) for nome in (
            'VHT_ABERTURA_GIRO.mp3', 'VHT_PASSAGEM_GIRO.mp3', 'VHT_ENCERRAMENTO_GIRO.mp3')]
    audio = abertura
    for i, nota in enumerate(notas):
        if i:
            audio += passagem
        audio += normalize(AudioSegment.from_mp3(str(nota)))
    audio += encerramento
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f'GNC_{codigo}_{data_str}.mp3'
    audio.export(str(out), format='mp3')
    return out

def main():
    parser = argparse.ArgumentParser(description='Monta GIRO com notas locais')
    parser.add_argument('entrada', type=Path)
    parser.add_argument('saida', type=Path)
    parser.add_argument('--codigo', required=True)
    parser.add_argument('--data', required=True)
    args = parser.parse_args()
    montar_programa(args.codigo, sorted(args.entrada.glob('*.mp3')), args.saida, args.data)

if __name__ == '__main__':
    main()
