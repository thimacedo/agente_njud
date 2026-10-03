"""Montagem BOLETIM por intervalos auditados; não usa duração estimada da cabeça."""
import hashlib,json,re,subprocess,sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

PROGRAMA_BOLETIM='BOLETIM'
def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def validar_manifesto_boletim(m):
    if m.get('programa')!=PROGRAMA_BOLETIM:raise ValueError('Programa incorreto')
    datetime.strptime(m['data'],'%d_%m_%Y')
    if not 1<=m['numero']<=99:raise ValueError('Número inválido')
    if not re.fullmatch(r'[A-Z0-9_]+',m['retranca']):raise ValueError('Retranca inválida')
    if not m.get('autorizacao_autopilot',False):raise ValueError('Autopilot sem autorização')
    for key in ['fonte','transcricao','roteiro']:
        if sha256(m[key])!=m[key+'_sha256']:raise ValueError('Hash divergente: '+key)
    tx=json.loads(Path(m['transcricao']).read_text(encoding='utf-8'))
    if tx['sha256'].lower()!=m['fonte_sha256'].lower():raise ValueError('Transcrição de outra fonte')
    end=0
    for part in ['cabeca','off']:
        if not m.get(part):raise ValueError('Parte vazia: '+part)
        for a,b in m[part]:
            if not 0<=a<b<=tx['duracao'] or a<end:raise ValueError('Intervalo inválido/sobreposto')
            end=b
    if not m.get('evidencias_limites') or not m.get('revisao_textual_concluida'):raise ValueError('Limites não revisados')
    if m.get('auditoria_voz_resultado')!='aprovado_automaticamente':raise ValueError('Voz não liberada pela auditoria')
    if sha256(m['auditoria_voz'])!=m['auditoria_voz_sha256']:raise ValueError('Auditoria de voz alterada')
    audit=json.loads(Path(m['auditoria_voz']).read_text(encoding='utf8'))
    if any(audit.get(k)!=m[k] for k in ['fonte_sha256','cabeca','off']):raise ValueError('Auditoria de outro corte/fonte')
    if audit.get('claquetes') or re.search(r'\b(?:repete|repetir|repeti|repetindo|repita|refaz|refazer|claquete)\b',audit.get('texto',''),re.I):raise ValueError('Instruções residuais na voz')
    return m

def montar_manifesto_boletim(manifesto,saida,assets):
    from pydub import AudioSegment
    from boletim.etapas.etapa_montagem import montar_boletim_com_vinhetas
    from boletim.etapas.etapa_triagem import triagem_audio
    path=Path(manifesto);m=validar_manifesto_boletim(json.loads(path.read_text(encoding='utf-8-sig')))
    saida=Path(saida);saida.mkdir(parents=True,exist_ok=True)
    nome=f"BOLETIM_RADIO_TJRN_{m['data']}_B{m['numero']}__{m['retranca']}.mp3"
    target=saida/nome
    if target.exists():raise FileExistsError(str(target))
    asset_names=['VHT_ABERTURA_BOLETIM.mp3','VHT_PASSAGEM_BOLETIM.mp3','VHT_ENCERRAMENTO_BOLETIM.mp3','BG - BOLETIM.mp3']
    asset_paths=[Path(assets)/n for n in asset_names]
    if not all(p.is_file() for p in asset_paths):raise ValueError('Assets BOLETIM ausentes')
    audio=AudioSegment.from_file(m['fonte']);triagem=triagem_audio(audio)
    if triagem.get('canal_morto'):
        audio=audio.split_to_mono()[0 if triagem['canal_morto']=='direito' else 1]
    def juntar(intervalos):
        parts=[audio[round(a*1000):round(b*1000)] for a,b in intervalos]
        return sum(parts[1:],parts[0])
    head=juntar(m['cabeca']);off=juntar(m['off'])
    vht=[AudioSegment.from_file(p) for p in asset_paths[:3]]
    result=montar_boletim_com_vinhetas(head+off,*vht,cabeça_duracao=len(head)/1000)
    # Reservar exclusivamente; exportação não pode sobrescrever uma entrega.
    with target.open('xb') as f:result.export(f,format='mp3',bitrate='192k',parameters=['-ar','44100'])
    decode=subprocess.run(['ffmpeg','-v','error','-i',str(target),'-f','null','-'],capture_output=True,text=True)
    if decode.returncode or decode.stderr.strip():raise ValueError('Decodificação falhou: '+decode.stderr)
    measure=subprocess.run(['ffmpeg','-hide_banner','-i',str(target),'-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    loud=json.loads(measure.stderr[measure.stderr.rfind('{'):measure.stderr.rfind('}')+1])
    expected=(len(head)+len(off)+sum(len(v) for v in vht))/1000
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(target)],text=True))
    ok=abs(duration-expected)<.25 and -17.5<=float(loud['input_i'])<=-14.5 and float(loud['input_tp'])<=-1.0
    report=dict(programa=PROGRAMA_BOLETIM,nome=nome,arquivo=str(target.resolve()),sha256=sha256(target),manifesto=str(path.resolve()),manifesto_sha256=sha256(path),auditoria_voz=m['auditoria_voz'],auditoria_voz_sha256=m['auditoria_voz_sha256'],conteudo_liberado=True,duracao=duration,duracao_prevista=expected,loudness=loud,decodificacao_integral=True,tecnico_ok=ok,escuta_humana=False,autorizacao='autopilot sem auditoria humana de áudio — usuário',assets=[dict(nome=p.name,sha256=sha256(p)) for p in asset_paths],triagem=triagem)
    with (saida/(nome+'.auditoria.json')).open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    if not ok:raise ValueError('Auditoria técnica reprovada')
    return report

def sincronizar_boletim(relatorio,destino):
    """Único ponto de escrita do espelho BOLETIM; nunca sobrescreve."""
    import shutil
    report=json.loads(Path(relatorio).read_text(encoding='utf-8'))
    if report.get('programa')!=PROGRAMA_BOLETIM or not report.get('tecnico_ok') or not report.get('conteudo_liberado'):
        raise ValueError('Entrega sem auditoria técnica válida')
    if sha256(report['manifesto'])!=report['manifesto_sha256']:raise ValueError('Manifesto alterado')
    if sha256(report['auditoria_voz'])!=report['auditoria_voz_sha256']:raise ValueError('Auditoria de voz alterada')
    origem=Path(report['arquivo']).resolve()
    if sha256(origem)!=report['sha256']:raise ValueError('Master alterado')
    destino=Path(destino).resolve();destino.mkdir(parents=True,exist_ok=True)
    target=destino/origem.name
    if target.exists():raise FileExistsError(str(target))
    with origem.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst)
    if sha256(target)!=report['sha256']:raise ValueError('Cópia divergente')
    return dict(origem=str(origem),destino=str(target),sha256=report['sha256'])

if __name__=='__main__':
    import argparse,os
    p=argparse.ArgumentParser();p.add_argument('manifesto');p.add_argument('--saida',required=True);p.add_argument('--assets',required=True);a=p.parse_args()
    os.environ['DIVISOR_ASSETS']=a.assets
    print(json.dumps(montar_manifesto_boletim(a.manifesto,a.saida,a.assets),ensure_ascii=True))
