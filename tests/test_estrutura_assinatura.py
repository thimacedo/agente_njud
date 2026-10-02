"""Regressão da assinatura institucional repartida pelo faster-whisper."""
import pytest
from boletim.etapas.etapa_estrutura import detectar_estrutura


@pytest.mark.parametrize('ending', ['do Norte, Lívia Rodrigues', 'e do Norte, Lívia Rodrigues', 'Norte, Lívia Rodrigues'])
def test_signature_split_before_norte_keeps_next_bulletin(ending):
    segments = [
        {'start': 0.0, 'end': 10.0, 'text': 'Primeiro boletim e seu conteúdo.'},
        {'start': 10.0, 'end': 12.0, 'text': 'Do Tribunal de Justiça do Rio Grande'},
        {'start': 12.0, 'end': 14.0, 'text': ending},
        {'start': 15.0, 'end': 25.0, 'text': 'B2. Segundo boletim e seu conteúdo.'},
    ]
    structure = detectar_estrutura(segments, 1, 2)
    assert len(structure['assinaturas']) == 1
    assert set(structure['marcadores']) == {1, 2}
    assert structure['marcadores'][2] <= 15.0
