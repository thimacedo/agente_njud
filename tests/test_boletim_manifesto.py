import hashlib,json
import pytest
from boletim.controle_manifesto import validar_manifesto_boletim

def manifesto(tmp_path):
    fonte=tmp_path/'fonte';fonte.write_bytes(b'audio preservado')
    roteiro=tmp_path/'roteiro';roteiro.write_text('CABEÇA e OFF')
    tx=tmp_path/'transcricao.json';tx.write_text(json.dumps({'sha256':hashlib.sha256(fonte.read_bytes()).hexdigest(),'duracao':60}))
    m=dict(programa='BOLETIM',data='01_10_2026',numero=1,retranca='TJRN_NOTICIA',autorizacao_autopilot=True,cabeca=[[2,8]],off=[[10,25],[30,50]],evidencias_limites={'cabeca':'frase completa','off':'frase completa'},revisao_textual_concluida=True)
    for key,p in [('fonte',fonte),('roteiro',roteiro),('transcricao',tx)]:m[key]=str(p);m[key+'_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    audit=tmp_path/'auditoria.json';audit.write_text(json.dumps({k:m[k] for k in ['fonte_sha256','cabeca','off']}))
    m.update(auditoria_voz=str(audit),auditoria_voz_sha256=hashlib.sha256(audit.read_bytes()).hexdigest(),auditoria_voz_resultado='aprovado_automaticamente')
    return m

def test_boletim_retake_keeps_original_and_explicit_parts(tmp_path):
    m=manifesto(tmp_path);before=(tmp_path/'fonte').read_bytes()
    assert validar_manifesto_boletim(m)['off']==[[10,25],[30,50]]
    assert (tmp_path/'fonte').read_bytes()==before

@pytest.mark.parametrize('change',[{'data':'31_09_2026'},{'numero':0},{'programa':'NJUD'},{'off':[[7,20]]},{'off':[[10,25],[24,30]]},{'cabeca':[]},{'autorizacao_autopilot':False},{'revisao_textual_concluida':False},{'auditoria_voz_resultado':'divergencia_editorial'}])
def test_boletim_rejects_unsafe_manifest(tmp_path,change):
    m=manifesto(tmp_path);m.update(change)
    with pytest.raises(ValueError):validar_manifesto_boletim(m)

def test_boletim_changed_source_rejected(tmp_path):
    m=manifesto(tmp_path);(tmp_path/'fonte').write_bytes(b'outra fonte')
    with pytest.raises(ValueError,match='Hash divergente'):validar_manifesto_boletim(m)


def test_audit_cannot_release_different_cuts(tmp_path):
    m=manifesto(tmp_path);m['off']=[[10,24],[30,50]]
    with pytest.raises(ValueError,match='outro corte'):validar_manifesto_boletim(m)


@pytest.mark.parametrize('instruction',['Repete','repetir','repita','refazer'])
def test_instruction_in_text_rejected_even_when_old_list_empty(tmp_path,instruction):
    m=manifesto(tmp_path);audit=tmp_path/'auditoria.json';data=json.loads(audit.read_text());data.update(texto=instruction,claquetes=[]);audit.write_text(json.dumps(data));m['auditoria_voz_sha256']=hashlib.sha256(audit.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='Instruções residuais'):validar_manifesto_boletim(m)

def test_repeticao_de_indebito_is_not_a_claquete(tmp_path):
    m=manifesto(tmp_path);audit=tmp_path/'auditoria.json';data=json.loads(audit.read_text());data.update(texto='repetição de indébito',claquetes=[]);audit.write_text(json.dumps(data));m['auditoria_voz_sha256']=hashlib.sha256(audit.read_bytes()).hexdigest()
    assert validar_manifesto_boletim(m)
