"""Regressões: ordem global, cortes duplicados e deslocamentos acumulados."""
from shared.core import Corte, sincronizar_transcricao_com_cortes
from boletim.etapas.etapa_cortes import processar_cortes_boletim
from pydub import AudioSegment
from pydub.generators import Sine

def test_timestamps():
    segments = [{'start':10,'end':20,'text':'um dois tres quatro cinco seis sete oito nove dez'}]
    actual = sincronizar_transcricao_com_cortes(segments, [Corte(0,2), Corte(14,16)])
    assert [(s['start'],s['end']) for s in actual] == [(8,12),(12,16)], actual

def cut(audio, reps, claps, segments=None):
    return processar_cortes_boletim(segments or [], audio, reps, claps, None,
        {'marcadores':{1:0},'assinaturas':[]},1,1)[1]['audio']

def test_order():
    audio = sum((Sine(200+i*25).to_audio_segment(duration=1000) for i in range(20)), AudioSegment.empty())
    result = cut(audio,[{'inicio':2,'fim':4}],{1:{'inicio':14,'fim':16}})
    expected = audio[:2000]+audio[4000:14000]+audio[16000:]
    assert result.raw_data == expected.raw_data

def test_duplicate_overlap():
    audio = Sine(400).to_audio_segment(duration=20000)
    result = cut(audio,[],{1:{'inicio':0,'fim':2}},[{'start':0,'end':2,'text':'B1.'}])
    assert len(result) == 18000
    result = cut(audio,[{'inicio':1,'fim':3}],{1:{'inicio':2,'fim':4}})
    assert len(result) == 17000

