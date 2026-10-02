import json
from pathlib import Path

import numpy as np
import pytest

from njud.controle_producao import (
    POLITICA, carregar_pares, limpar_referencia, registrar_revisao,
    sha256, validar_grade, validar_manifesto,
)


def test_limpeza_remove_referencia_sem_processar_resto_da_voz():
    rate = 1000
    rng = np.random.default_rng(72)
    ref = rng.normal(0, .1, (1200, 2))
    voice = rng.normal(0, .008, (4000, 2))
    voice[:2000] = 0
    audio = voice.copy()
    audio[1100:2300] += .8 * ref
    cleaned, report = limpar_referencia(audio, ref, {"cabeca_fim": 1., "corpo_inicio": 2.}, rate)
    np.testing.assert_allclose(cleaned, voice, atol=1e-10)
    np.testing.assert_array_equal(cleaned[:1100], audio[:1100])
    np.testing.assert_array_equal(cleaned[2300:], audio[2300:])
    assert report["reducao_instrumental_db"] < -15
    assert report["escuta_pendente"] is True


def test_referencia_fraca_nao_pode_produzir_corte():
    rng = np.random.default_rng(33)
    with pytest.raises(ValueError, match="não confiável"):
        limpar_referencia(rng.normal(0,.1,(5000,2)), rng.normal(0,.1,(1000,2)),
                          {"cabeca_fim":1.,"corpo_inicio":2.}, 1000)


def test_grade_rejeita_duas_edicoes_na_mesma_data():
    with pytest.raises(ValueError, match="duplicada"):
        validar_grade([{"data_edicao":"2026-09-01","njud":1947},
                       {"data_edicao":"2026-09-01","njud":1948}])


def test_manifesto_rejeita_fonte_alterada_e_tempos_invertidos(tmp_path):
    sources=[]
    for i in range(4):
        p=tmp_path/f"B{i+1}.mp3";p.write_bytes(bytes([i]))
        sources.append({"origem":str(p),"sha256":sha256(p),"boletim":i+1,
                        "limites":{"cabeca_inicio":1.,"cabeca_fim":2.,"corpo_inicio":3.,"corpo_fim":4.,"evidencia":"teste"}})
    data={"njud":1950,"data_edicao":"2026-09-03","data_boletins":"2026-09-02",
          "versao":"v01","referencia_passagem":"ref.mp3","boletins":sources}
    validar_manifesto(data)
    from njud.controle_producao import preparar
    with pytest.raises(ValueError,match="exigem stems"):
        preparar(data,tmp_path/"nao_criar")
    assert not (tmp_path/"nao_criar").exists()
    sources[0]["limites"]["corpo_inicio"]=1
    with pytest.raises(ValueError,match="invertidos"):
        validar_manifesto(data)
    sources[0]["limites"]["corpo_inicio"]=3
    Path(sources[0]["origem"]).write_bytes(b"alterado")
    with pytest.raises(ValueError,match="Fonte alterada"):
        validar_manifesto(data)


def test_pares_preservam_ordem_editorial_e_rejeitam_mudanca(tmp_path):
    pairs=[]
    for b in (2,4,7,6):
        p={"boletim":b}
        for kind in ("cabeca","corpo"):
            f=tmp_path/f"B{b}_{kind}.wav";f.write_bytes(str(b).encode())
            p[kind]=str(f);p[kind+"_sha256"]=sha256(f)
        pairs.append(p)
    (tmp_path/"manifesto_producao.json").write_text(json.dumps({"politica":POLITICA,"data_edicao":"2026-09-16","pares":pairs}))
    _,files=carregar_pares(tmp_path)
    assert [p[0].name for p in files]==["B2_cabeca.wav","B4_cabeca.wav","B7_cabeca.wav","B6_cabeca.wav"]
    files[2][0].write_bytes(b"mudou")
    with pytest.raises(ValueError,match="alterado"):
        carregar_pares(tmp_path)


def test_aprovacao_exige_escuta_e_conferencia_editorial(tmp_path):
    audio=tmp_path/"piloto.mp3";audio.write_bytes(b"audio")
    with pytest.raises(ValueError,match="Aprovação exige"):
        registrar_revisao(audio,tmp_path/"eventos","auditor","aprovado","ok")
    event=registrar_revisao(audio,tmp_path/"eventos","auditor","refazer","residuo_vinheta")
    assert event["sha256"]==sha256(audio)
    assert len(list((tmp_path/"eventos").glob("*.json")))==1


def test_divisor_nao_usa_fallback_proporcional(tmp_path):
    from divisor_boletins.__main__ import _salvar_cortado
    result=_salvar_cortado(object(),{"calibracao":{"tempo_inicio_s":0},"ancora":{}},tmp_path,"B1")
    assert "erro_corte" in result
    assert not list(tmp_path.glob("*.mp3"))


def test_montador_rejeita_brutos_sem_manifesto(tmp_path):
    from montagem_jornais import montar_jornal
    source=tmp_path/"NJUD_1950";source.mkdir()
    assert montar_jornal(source,tmp_path/"out") is None
    assert not (tmp_path/"out").exists()


def test_aprovacao_nao_aceita_limite_de_duracao_apenas_declarado(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import njud.controle_producao as controle
    audio=tmp_path/"piloto.mp3";audio.write_bytes(b"audio")
    monkeypatch.setattr(controle.subprocess,"run",lambda *a,**k: SimpleNamespace(stdout='{"format":{"duration":"301"}}'))
    checks={k:True for k in ("escuta_integral","cortes_sem_residuos","voz_preservada","conteudo_ordem_data","apresentacao_editorial","duracao")}
    with pytest.raises(ValueError,match="Duração real"):
        registrar_revisao(audio,tmp_path/"eventos","auditor","aprovado","ok",checks)
    assert not (tmp_path/"eventos").exists()


def test_auxiliar_que_duplicava_boletins_esta_bloqueado():
    from njud.process_njud_local import montar_jornal
    with pytest.raises(RuntimeError, match="desativado"):
        montar_jornal(["B1.mp3","B2.mp3","B3.mp3","B4.mp3"], "out")


def test_bg_da_escalada_nao_e_somado_aos_corpos(monkeypatch, tmp_path):
    import montagem_jornais as m
    from pydub import AudioSegment
    from pydub.generators import Sine
    head=AudioSegment.silent(duration=100,frame_rate=44100)
    body=Sine(440).to_audio_segment(duration=500).apply_gain(-10)
    effect=AudioSegment.silent(duration=20,frame_rate=44100)
    pairs=[(Path(f"C{i}"),Path(f"B{i}")) for i in range(4)]
    monkeypatch.setattr(m,"_localizar_pares_cabeca_corpo",lambda p:pairs)
    monkeypatch.setattr(m,"_carregar_vinheta",lambda *a:effect)
    monkeypatch.setattr(m,"normalizar_lufs",lambda *a:None)
    monkeypatch.setattr(m,"normalize",lambda a:a)
    monkeypatch.setattr(m.AudioSegment,"from_file",lambda p:head if str(p).startswith('C') else body)
    monkeypatch.setattr(m,"preparar_trilha_bg",lambda d,v:Sine(880).to_audio_segment(duration=d))
    class Log:
        def error(self,*a):pass
    audio=m._montar_de_cortes(tmp_path,"1950",20,Log())
    # Abertura 20 + 4 cabecas 100 + 3 pausas 80 + passagem 20 = 680ms.
    for i in range(4):
        start=680+i*(500+120+20)
        assert audio[start:start+500].raw_data==body.raw_data


def test_stem_precisa_da_origem_certa_e_evidencia_de_fim_frase(tmp_path):
    data={"njud":1950,"data_edicao":"2026-09-03","data_boletins":"2026-09-02",
          "versao":"v04","referencia_passagem":"ref.mp3","boletins":[]}
    for b in range(1,5):
        source=tmp_path/f"B{b}.mp3";source.write_bytes(bytes([b]))
        voice=tmp_path/f"B{b}_VOZ.wav";voice.write_bytes(bytes([b,1]))
        bg=tmp_path/f"B{b}_BG.wav";bg.write_bytes(bytes([b,2]))
        item={"boletim":b,"origem":str(source),"sha256":sha256(source),
              "limites":{"cabeca_inicio":1.,"cabeca_fim":2.,"corpo_inicio":3.,"corpo_fim":4.,"evidencia":"transcricao"},
              "stems":{"origem_sha256":sha256(source),"voz":str(voice),"voz_sha256":sha256(voice),
                       "acompanhamento":str(bg),"acompanhamento_sha256":sha256(bg)}}
        data["boletins"].append(item)
    with pytest.raises(ValueError,match="fim da frase"):
        validar_manifesto(data)
    for item in data["boletins"]:
        item["limites"]["evidencia_fim_frase"]={"analise":"pausa verificada"}
    validar_manifesto(data)
    data["boletins"][0]["stems"]["origem_sha256"]="errado"
    with pytest.raises(ValueError,match="não corresponde"):
        validar_manifesto(data)
