#!/usr/bin/env python3
import sys
from pathlib import Path
import argparse
import json
import tempfile
from datetime import datetime
from pydub import AudioSegment

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets" / "vinhetas" / "njud"
VHT_ABERTURA = ASSETS_DIR / "VHT_ABERTURA_NJUD.mp3"
VHT_ENCERRAMENTO = ASSETS_DIR / "VHT_ENCERRAMENTO_NJUD.mp3"
EFEITO_PASSAGEM = ASSETS_DIR / "EFEITO_PASSAGEM_NJUD.mp3"
TRILHA_ESCALADA = ASSETS_DIR / "TRILHA_ESCALADA_NJUD.mp3"
RECEITA = ASSETS_DIR / "RECEITA_NJUD.txt"

def carregar_receita():
    receita={'bg_volume_percent':20,'silence_ms':100}
    if RECEITA.exists():
        text=RECEITA.read_text(encoding='utf-8')
        import re
        m=re.search(r'(\d+)%\s*(?:DO\s*)?VOLUME',text,re.I)
        if m: receita['bg_volume_percent']=int(m.group(1))
    return receita

def percent_to_db(p):
    import math
    return -60.0 if p<=0 else 20*math.log10(p/100.0)

def detectar_silencio_gap(audioseg, padrao_ms=100):
    from pydub.silence import detect_nonsilent
    segs=detect_nonsilent(audioseg,min_silence_len=200,silence_thresh=-35)
    gaps=[]
    for i in range(len(segs)-1):
        g=segs[i+1][0]-segs[i][1]
        if g>50: gaps.append(g)
    if gaps:
        gaps.sort()
        med=gaps[len(gaps)//2]
        return min(max(med,50),500)
    return padrao_ms

def montar_jornal(boletins_paths, output_dir, nome_jornal=None, normalizar=True, target_lufs=-16.0):
    if len(boletins_paths)!=4:
        raise ValueError(f"NJUD requer exatamente 4 boletins, recebidos {len(boletins_paths)}")
    output_path=Path(output_dir)
    output_path.mkdir(parents=True,exist_ok=True)
    if not nome_jornal:
        nome_jornal=f"NJUD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    receita=carregar_receita()
    bg_volume=receita['bg_volume_percent']
    print("Carregando vinhetas...")
    vht_abertura=AudioSegment.from_mp3(str(VHT_ABERTURA))
    vht_encerramento=AudioSegment.from_mp3(str(VHT_ENCERRAMENTO))
    efeito_passagem=AudioSegment.from_mp3(str(EFEITO_PASSAGEM))
    trilha_escalada=AudioSegment.from_mp3(str(TRILHA_ESCALADA))
    for n,v in [("Abertura",vht_abertura),("Encerramento",vht_encerramento),("Passagem",efeito_passagem)]:
        print(f"  OK {n}: {len(v)/1000:.1f}s")
    silencio_ms=detectar_silencio_gap(AudioSegment.from_file(boletins_paths[0]))
    print(f"Silencio entre blocos: {silencio_ms}ms")
    dur_cabecas_ms=sum(len(AudioSegment.from_file(b)) for b in boletins_paths)+silencio_ms*3
    trilha_bg=trilha_escalada
    while len(trilha_bg)<dur_cabecas_ms:
        trilha_bg=trilha_bg+trilha_bg
    trilha_bg=trilha_bg[:dur_cabecas_ms]
    gain_db=percent_to_db(bg_volume)
    trilha_bg=trilha_bg.apply_gain(gain_db)
    bloco_cabecas=AudioSegment.empty()
    for i,bp in enumerate(boletins_paths):
        cab=AudioSegment.from_file(bp)
        bloco_cabecas+=cab
        if i<len(boletins_paths)-1:
            bloco_cabecas+=AudioSegment.silent(duration=silencio_ms)
    bloco_cabecas_bg=bloco_cabecas.overlay(trilha_bg)
    bloco_corpos=AudioSegment.empty()
    for i,bp in enumerate(boletins_paths):
        corpo=AudioSegment.from_file(bp)
        if i>0:
            bloco_corpos+=efeito_passagem
        bloco_corpos+=corpo
    print(f"Bloco cabecas: {len(bloco_cabecas_bg)/1000:.1f}s")
    print(f"Bloco corpos: {len(bloco_corpos)/1000:.1f}s")
    sil=AudioSegment.silent(duration=silencio_ms)
    jornal=vht_abertura+sil+bloco_cabecas_bg+sil+bloco_corpos+sil+vht_encerramento
    duracao=len(jornal)/1000
    print(f"Duracao: {int(duracao//60)}:{int(duracao%60):02d}")
    tmp=output_path/f"{nome_jornal}_raw.mp3"
    jornal.export(str(tmp),format="mp3",bitrate="192k")
    final_path=output_path/f"{nome_jornal}.mp3"
    import subprocess
    if normalizar:
        cmd=["ffmpeg","-y","-i",str(tmp),"-af",f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11","-b:a","192k",str(final_path)]
        r=subprocess.run(cmd,capture_output=True,text=True)
        if r.returncode!=0:
            raise RuntimeError(f"ffmpeg falhou: {r.stderr[-500:]}")
        print(f"Normalizado -> {final_path}")
        tmp.unlink()
    else:
        tmp.rename(final_path)
    print(f"JORNAL PRONTO: {final_path}")
    return {"nome":nome_jornal,"duracao_total_s":round(duracao,1),"arquivo_final":str(final_path),"bg_volume_percent":bg_volume,"silence_between_blocks_ms":silencio_ms}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--b1",required=True)
    p.add_argument("--b2",required=True)
    p.add_argument("--b3",required=True)
    p.add_argument("--b4",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--nome",default=None)
    p.add_argument("--sem-normalizar",action="store_true")
    args=p.parse_args()
    montar_jornal(
        boletins_paths=[args.b1,args.b2,args.b3,args.b4],
        output_dir=args.output,
        nome_jornal=args.nome,
        normalizar=not args.sem_normalizar,
    )
