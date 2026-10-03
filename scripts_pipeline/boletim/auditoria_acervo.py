"""Auditoria BOLETIM somente leitura, retomável por hash, fora do espelho."""
import os,json,re,hashlib,subprocess,gc,shutil
from datetime import datetime,timezone
from pathlib import Path
PATTERN=re.compile(r'\b(?:repete|repetir|repeti|repetindo|repita|refaz|refazer|claquete)\b',re.I)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def auditar_acervo(pasta,saida,modelo_nome='base',limite=None):
 from faster_whisper import WhisperModel
 from pydub import AudioSegment
 os.environ['OMP_NUM_THREADS']=os.environ['MKL_NUM_THREADS']='1'
 root=Path(pasta).resolve();out=Path(saida).resolve()
 if root==out or root in out.parents:raise ValueError('Auditoria não pode escrever na origem')
 out.mkdir(parents=True,exist_ok=True)
 for d in ['fontes','resultados','analise','logs']:(out/d).mkdir(exist_ok=True)
 files=sorted(root.rglob('*.mp3'));events=out/'logs/eventos.jsonl';results=[]
 def state(status,current=None,error=None):
  data=dict(programa='BOLETIM',pid=os.getpid(),status=status,atual=current,total=len(files),concluidos=len(results),com_suspeitas=sum(bool(x.get('suspeitas')) for x in results),erros=sum(bool(x.get('erro')) for x in results),atualizado=datetime.now(timezone.utc).isoformat(),origem=str(root),saida=str(out),erro=error)
  tmp=out/'estado.tmp';tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');os.replace(tmp,out/'estado.json')
 def event(data):
  with events.open('a',encoding='utf8') as f:f.write(json.dumps(data,ensure_ascii=False)+'\n')
 state('iniciando');model=WhisperModel(modelo_nome,device='cpu',compute_type='int8',cpu_threads=1,local_files_only=True)
 try:
  for i,source in enumerate(files):
   if limite and i>=limite:break
   digest=sha(source);m=re.search(r'_(\d{2}_\d{2}_\d{4})_B(\d+)(?:_|\.)',source.name,re.I)
   key=(f'{m[1]}_B{m[2]}' if m else source.stem[:40])+'_'+digest[:12];target=out/'resultados'/(key+'.json')
   if target.exists():
    old=json.loads(target.read_text(encoding='utf8'))
    if old['sha256']!=digest:raise ValueError('Cache de outra fonte')
    results.append(old);continue
   state('executando',str(source));copy=out/'fontes'/(key+'.mp3')
   if not copy.exists():
    with source.open('rb') as src,copy.open('xb') as dst:shutil.copyfileobj(src,dst)
   if sha(copy)!=digest:raise ValueError('Cópia diferente da fonte')
   item=dict(programa='BOLETIM',arquivo=str(source),copia=str(copy),nome=source.name,sha256=digest,escuta_humana=False,modelo=modelo_nome,suspeitas=[],erro=None)
   print('AUDITANDO',i+1,'/',len(files),source.name,flush=True)
   try:
    decode=subprocess.run(['ffmpeg','-v','error','-i',str(copy),'-f','null','-'],capture_output=True,text=True)
    item['decodificacao_integral']=decode.returncode==0 and not decode.stderr.strip()
    if not item['decodificacao_integral']:raise ValueError('Decodificação: '+decode.stderr[-500:])
    duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(copy)],text=True));item['duracao']=duration
    measure=subprocess.run(['ffmpeg','-hide_banner','-i',str(copy),'-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    item['loudness']=json.loads(measure.stderr[measure.stderr.rfind('{'):measure.stderr.rfind('}')+1])
    wav=out/'analise'/(key+'.wav');audio=AudioSegment.from_file(copy).set_channels(1).set_frame_rate(16000);audio.export(wav,format='wav');del audio;gc.collect()
    segs,_=model.transcribe(str(wav),language='pt',word_timestamps=True,beam_size=1,best_of=1,vad_filter=False)
    data=[dict(start=s.start,end=s.end,text=s.text,words=[dict(word=w.word,start=w.start,end=w.end,probability=w.probability) for w in s.words or []]) for s in segs]
    item['segmentos']=data;item['texto']=' '.join(s['text'] for s in data)
    item['suspeitas']=[dict(tipo='instrucao_gravacao',**w,contexto=s['text']) for s in data for w in s['words'] if PATTERN.search(w['word'])]
    for a,b in zip(data,data[1:]):
     ta=re.sub(r'\W+',' ',a['text'].lower()).strip();tb=re.sub(r'\W+',' ',b['text'].lower()).strip()
     if ta==tb and len(ta.split())>=5 and a['start']>12 and b['end']<duration-10:item['suspeitas'].append(dict(tipo='frase_repetida',start=a['start'],end=b['end'],texto=a['text']))
    item['conclusao']='suspeita_requer_confirmacao' if item['suspeitas'] else 'nao_localizado_pelo_ASR_nao_equivale_ausencia'
   except Exception as e:item['erro']=repr(e);item['conclusao']='auditoria_incompleta'
   with target.open('x',encoding='utf8') as f:json.dump(item,f,ensure_ascii=False,indent=2)
   results.append(item);event(dict(arquivo=str(source),resultado=str(target),suspeitas=item['suspeitas'],erro=item['erro']));state('executando',str(source))
   print('CONCLUIDO',len(results),'SUSPEITAS',len(item['suspeitas']),'ERRO',item['erro'],flush=True)
  state('concluido' if len(results)==len(files) else 'lote_piloto_concluido')
  summary=dict(programa='BOLETIM',total=len(files),auditados=len(results),pendentes=len(files)-len(results),suspeitas=[dict(arquivo=x['arquivo'],sha256=x['sha256'],ocorrencias=x['suspeitas']) for x in results if x.get('suspeitas')],erros=[dict(arquivo=x['arquivo'],erro=x['erro']) for x in results if x.get('erro')],escuta_humana=False,alteracoes_na_origem=0)
  (out/'resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
  return summary
 except BaseException as e:state('interrompido',error=repr(e));raise
