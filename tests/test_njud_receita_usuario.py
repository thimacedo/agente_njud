import json
from pathlib import Path
import pytest
import montagem_jornais as m

def test_limite_padrao_e_excecao_explicita():
    assert m.limite_duracao_njud({}) == 300
    with pytest.raises(ValueError,match='orientação humana'):
        m.limite_duracao_njud({'limite_duracao_s':900})
    assert m.limite_duracao_njud({'limite_duracao_s':900,'autorizacao_duracao':{'autorizada':True,'responsavel':'Thiago','mensagem':'Manter as notas integrais, mesmo acima de 5 minutos'}})==900
    for invalid in [True,1000,float('nan')]:
        with pytest.raises(ValueError):m.limite_duracao_njud({'limite_duracao_s':invalid})

def test_passagem_unica_preserva_notas_sem_bg(tmp_path,monkeypatch):
    from pydub import AudioSegment
    from pydub.generators import Sine
    head=AudioSegment.silent(duration=100,frame_rate=44100)
    body=Sine(440).to_audio_segment(duration=500).apply_gain(-10)
    effect=AudioSegment.silent(duration=20,frame_rate=44100)
    pairs=[(Path(f'C{i}'),Path(f'B{i}')) for i in range(4)]
    monkeypatch.setattr(m,'_localizar_pares_cabeca_corpo',lambda p:pairs)
    monkeypatch.setattr(m,'_carregar_vinheta',lambda *a:effect)
    monkeypatch.setattr(m,'normalize',lambda a:a)
    monkeypatch.setattr(m.AudioSegment,'from_file',lambda p:head if str(p).startswith('C') else body)
    monkeypatch.setattr(m,'preparar_trilha_bg',lambda d,v:Sine(880).to_audio_segment(duration=d))
    (tmp_path/'manifesto_producao.json').write_text(json.dumps({'passagem_entre_notas':False,'autorizacao_receita':{'receita_literal':'abertura, cabeças, passagem, notas, encerramento'}}))
    class Log:
        def error(self,*a):pass
    audio=m._montar_de_cortes(tmp_path,'1969',20,Log())
    assert len(audio)==680+4*(500+120)+20
    for i in range(4):
        start=680+i*(500+120)
        assert audio[start:start+500].raw_data==body.raw_data

def test_passagem_unica_sem_orientacao_rejeitada(tmp_path,monkeypatch):
    (tmp_path/'manifesto_producao.json').write_text(json.dumps({'passagem_entre_notas':False}))
    monkeypatch.setattr(m,'_localizar_pares_cabeca_corpo',lambda p:[(Path('C'),Path('B'))]*4)
    from pydub import AudioSegment
    monkeypatch.setattr(m,'_carregar_vinheta',lambda *a:AudioSegment.silent(duration=20))
    monkeypatch.setattr(m.AudioSegment,'from_file',lambda p:AudioSegment.silent(duration=100))
    monkeypatch.setattr(m,'preparar_trilha_bg',lambda d,v:AudioSegment.silent(duration=d))
    class Log:
        def error(self,*a):pass
    with pytest.raises(ValueError,match='Passagem única'):
        m._montar_de_cortes(tmp_path,'1969',20,Log())
