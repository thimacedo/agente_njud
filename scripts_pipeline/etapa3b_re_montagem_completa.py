#!/usr/bin/env python3
"""
ETAPA 3b: Re-montagem usando arquivos COMPLETOS em vez de cortes CABEÇA/CORPO.
Os cortes estão excessivamente truncados; os arquivos completos existem em 
JORNAIS_DIVIDIDOS e somam 5-9 min por NJUD.
"""
from pathlib import Path
from pydub import AudioSegment
import re
import json
from datetime import datetime

BASE_DIR = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR")
divididos = BASE_DIR / "data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS"
output = BASE_DIR / "data/output/JORNAIS_FINAL"
logs_dir = BASE_DIR / "logs"

output.mkdir(parents=True, exist_ok=True)
logs_dir.mkdir(parents=True, exist_ok=True)

MIN_DUR = 5 * 60 * 1000
MAX_DUR = 15 * 60 * 1000

assets = BASE_DIR / "assets" / "vinhetas"
vht_abertura_name = "VHT_ABERTURA_NJUD.mp3"
vht_encerramento_name = "VHT_ENCERRAMENTO_NJUD.mp3"
trilha_name = "TRILHA_ESCALADA_NJUD.mp3"
passagem_name = "VHT_PASSAGEM_BOLETIM.mp3"

print("=" * 70)
print("ETAPA 3b: RE-MONTAGEM COM ARQUIVOS COMPLETOS")
print("=" * 70)

def load_vinheta(name, desc):
    path = assets / name
    if not path.exists():
        print(f"Vinheta nao encontrada: {path} ({desc}) - usando silencio")
        return None
    try:
        return AudioSegment.from_file(str(path))
    except Exception as e:
        print(f"Erro ao carregar {desc}: {e}")
        return None

vht_abertura = load_vinheta(vht_abertura_name, "Abertura")
vht_encerramento = load_vinheta(vht_encerramento_name, "Encerramento")
trilha = load_vinheta(trilha_name, "Trilha escalada")
passagem = load_vinheta(passagem_name, "Passagem entre boletins")

print(f"Vinhetas: Abertura={vht_abertura is not None}, Encerramento={vht_encerramento is not None}")
print(f"Trilha={trilha is not None}, Passagem={passagem is not None}")

relatorio = {
    "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
    "tipo": "re_montagem_completa",
    "njuds_processados": [],
    "njuds_corretos": [],
    "njuds_com_problemas": [],
}

for njud_dir in sorted(divididos.iterdir()):
    if not njud_dir.is_dir():
        continue
    
    m = re.search(r'NJUD\s+(\d+)', njud_dir.name)
    if not m:
        continue
    num = int(m.group(1))
    
    full_files = sorted([f for f in njud_dir.glob("*.mp3") 
                        if not f.name.endswith("_CABECA.mp3") 
                        and not f.name.endswith("_CORPO.mp3")])
    
    if len(full_files) < 4:
        continue
    
    print(f"\n--- NJUD {num} ---")
    print(f"  Arquivos completos: {len(full_files)}")
    
    datas = []
    for f in full_files:
        m_data = re.search(r"_(\d{2})_(\d{2})_(\d{4})_", f.name)
        if m_data:
            dia, mes, ano = m_data.groups()
            datas.append(f"{dia}-{mes}-{ano}")
    
    data_str = datas[0] if datas else None
    
    total_ms = 0
    duracoes = []
    for f in full_files:
        try:
            audio = AudioSegment.from_file(str(f))
            total_ms += len(audio)
            duracoes.append(f"{len(audio)/1000:.0f}s")
        except Exception as e:
            print(f"  Erro ao ler {f.name}: {e}")
    
    total_min = total_ms / 60000
    print(f"  Duracao total: {total_min:.1f}min ({total_ms/1000:.0f}s)")
    print(f"  Duracoes: {', '.join(duracoes)}")
    
    if len(full_files) >= 4 and total_ms >= MIN_DUR:
        print(f"  Montando com {len(full_files)} boletins completos...")
        
        jornal = AudioSegment.empty()
        
        if vht_abertura:
            jornal += vht_abertura
        
        if len(full_files) > 0:
            if passagem and len(jornal) > 0:
                jornal += passagem
            f0 = str(full_files[0])
            jornal += AudioSegment.from_file(f0)
        
        for i in range(1, min(len(full_files), 8)):
            if passagem:
                jornal += passagem
            fpath = str(full_files[i])
            try:
                jornal += AudioSegment.from_file(fpath)
            except Exception as e:
                print(f"    Erro no boletim {i+1}: {e}")
        
        if vht_encerramento:
            jornal += vht_encerramento
        
        codigo = str(num)
        if not data_str:
            data_str = "sem_data"
        nome_saida = f"NJUD_{codigo}_{data_str}.mp3"
        caminho_saida = output / nome_saida
        
        try:
            jornal.export(str(caminho_saida), format="mp3")
            duracao_final = len(jornal) / 60000
            tamanho_mb = caminho_saida.stat().st_size / (1024*1024)
            
            relatorio["njuds_processados"].append({
                "njud": f"NJUD {num}",
                "arquivo_saida": nome_saida,
                "duracao_min": round(duracao_final, 1),
                "tamanho_mb": round(tamanho_mb, 1),
                "quantidade_boletins": len(full_files),
            })
            
            if duracao_final >= 5 and duracao_final <= 15:
                relatorio["njuds_corretos"].append(f"NJUD {num}")
                print(f"  OK: {nome_saida} ({duracao_final:.1f}min, {tamanho_mb:.1f}MB) APROVADO")
            else:
                relatorio["njuds_com_problemas"].append({
                    "njud": f"NJUD {num}",
                    "problema": f"Duracao fora do padrao: {duracao_final:.1f}min",
                    "duracao_min": round(duracao_final, 1),
                })
                print(f"  ALERTA: {nome_saida} ({duracao_final:.1f}min) FORA DO PADRAO")
                
        except Exception as e:
            relatorio["njuds_com_problemas"].append({
                "njud": f"NJUD {num}",
                "problema": f"Erro na exportacao: {e}",
            })
            print(f"  ERRO ao exportar: {e}")
    else:
        print(f"  PULADO: {len(full_files)} completos, {total_min:.1f}min (nao atende requisitos)")
        relatorio["njuds_com_problemas"].append({
            "njud": f"NJUD {num}",
            "problema": f"Insuficiente para montagem: {len(full_files)} completos, {total_min:.1f}min",
        })

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
relatorio_path = logs_dir / f"relatorio_re_montagem_{timestamp}.json"
with open(relatorio_path, "w", encoding="utf-8") as f:
    json.dump(relatorio, f, indent=2, ensure_ascii=False)

print(f"\n{'=' * 70}")
print(f"RE-MONTAGEM CONCLUÍDA")
print(f"{'=' * 70}")
print(f"Total processados: {len(relatorio['njuds_processados'])}")
print(f"Corretos (>=5min): {len(relatorio['njuds_corretos'])}")
print(f"Com problemas: {len(relatorio['njuds_com_problemas'])}")
print(f"Relatorio: {relatorio_path}")

resultado = {
    "auditoria_ok": "NAO_OK" if relatorio["njuds_com_problemas"] else "OK",
    "erro": "; ".join([p.get("problema", "") for p in relatorio["njuds_com_problemas"]]) if relatorio["njuds_com_problemas"] else "",
    "njuds_aprovados": str(len(relatorio["njuds_corretos"])),
    "njuds_rejeitados": str(len([p for p in relatorio["njuds_com_problemas"] if "duracao" in p.get("problema", "").lower()])),
    "pendencias": "0",
    "relatorio_path": str(relatorio_path),
    "resultado": f"Re-montagem concluida: {len(relatorio['njuds_processados'])} NJUDs processados, {len(relatorio['njuds_corretos'])} corretos, {len(relatorio['njuds_com_problemas'])} com problemas. Relatorio: {relatorio_path}"
}
print(f"\n=== RESULTADO FINAL ===")
print(json.dumps(resultado, indent=2, ensure_ascii=False))
