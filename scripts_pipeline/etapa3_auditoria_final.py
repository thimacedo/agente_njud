#!/usr/bin/env python3
"""
ETAPA 3: Auditoria de montagem - Gera relatório final
"""
from pathlib import Path
from pydub import AudioSegment
import json
import re
from datetime import datetime

output = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/data/output/JORNAIS_FINAL")
divididos = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/data/processed/PRODUCAO_2026/JORNAIS_DIVIDIDOS")
logs_dir = Path(r"E:/02_Projetos_Trabalho/Projetos_Ativos/DIVISOR/logs")

MIN_DUR = 5 * 60 * 1000
MAX_DUR = 15 * 60 * 1000

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

njuds_aprovados = []
njuds_rejeitados = []
pendencias = []
erros_detail = []
montados = {}

for f in output.glob("*.mp3"):
    m = re.search(r'NJUD_(\d+)', f.stem)
    if m:
        num = int(m.group(1))
        montados[num] = f

for num, f in sorted(montados.items()):
    try:
        audio = AudioSegment.from_file(str(f), format="mp3")
        duracao_ms = len(audio)
        duracao_s = duracao_ms / 1000
        duracao_min = duracao_s / 60
        tamanho = f.stat().st_size
        problemas = []
        
        if duracao_ms < MIN_DUR:
            problemas.append(f"Duracao insuficiente: {int(duracao_s//60)}:{int(duracao_s%60):02d} ({duracao_min:.1f} min) - minimo 5 min")
        elif duracao_ms > MAX_DUR:
            problemas.append(f"Duracao excede limite: {int(duracao_s//60)}:{int(duracao_s%60):02d} ({duracao_min:.1f} min) - maximo 15 min")
        
        njud_dir = divididos / f"NJUD {num}"
        if njud_dir.exists():
            cabecas = list(njud_dir.glob("*_CABECA.mp3"))
            corpos = list(njud_dir.glob("*_CORPO.mp3"))
            bases_cab = {ff.stem.replace('_CABECA', '') for ff in cabecas}
            bases_cop = {ff.stem.replace('_CORPO', '') for ff in corpos}
            pares = len(bases_cab & bases_cop)
            if pares < 4:
                problemas.append(f"Apenas {pares}/4 pares completos em JORNAIS_DIVIDIDOS")
        else:
            problemas.append(f"Nao encontrado em JORNAIS_DIVIDIDOS (possivel orfao)")
        
        if problemas:
            njuds_rejeitados.append({
                "njud": f"NJUD {num}",
                "problemas": problemas,
                "duracao": f"{int(duracao_s//60)}:{int(duracao_s%60):02d}",
                "minutos": round(duracao_min, 1),
                "tamanho_bytes": tamanho,
                "arquivo": f.name
            })
            for p in problemas:
                erros_detail.append(f"NJUD {num}: {p}")
        else:
            njuds_aprovados.append({
                "njud": f"NJUD {num}",
                "duracao": f"{int(duracao_s//60)}:{int(duracao_s%60):02d}",
                "minutos": round(duracao_min, 1),
                "tamanho_bytes": tamanho,
                "arquivo": f.name
            })
    except Exception as e:
        njuds_rejeitados.append({
            "njud": f"NJUD {num}",
            "problemas": [f"Erro ao ler arquivo: {e}"],
            "duracao": "N/A",
            "minutos": 0,
            "tamanho_bytes": f.stat().st_size if f.exists() else 0,
            "arquivo": f.name
        })
        erros_detail.append(f"NJUD {num}: Erro ao ler - {e}")

total_esperados = 0
for njud_dir in divididos.iterdir():
    if not njud_dir.is_dir():
        continue
    m = re.search(r'NJUD\s+(\d+)', njud_dir.name)
    if not m:
        continue
    num = int(m.group(1))
    cabecas = list(njud_dir.glob("*_CABECA.mp3"))
    corpos = list(njud_dir.glob("*_CORPO.mp3"))
    bases_cab = {ff.stem.replace('_CABECA', '') for ff in cabecas}
    bases_cop = {ff.stem.replace('_CORPO', '') for ff in corpos}
    pares = len(bases_cab & bases_cop)
    
    if pares >= 4:
        total_esperados += 1
        if num not in montados:
            pendencias.append({
                "njud": f"NJUD {num}",
                "motivo": f"Nao foi montado (4 cortes OK disponiveis em JORNAIS_DIVIDIDOS)"
            })
            erros_detail.append(f"NJUD {num}: NAO MONTADO (4 cortes OK disponiveis)")

relatorio = {
    "timestamp": timestamp,
    "total_njuds_auditados": len(montados),
    "total_esperados_com_4_cortes_ok": total_esperados,
    "njuds_aprovados": njuds_aprovados,
    "njuds_rejeitados": njuds_rejeitados,
    "njuds_nao_fluxados": pendencias,
    "resumo": {
        "aprovados": len(njuds_aprovados),
        "rejeitados": len(njuds_rejeitados),
        "pendencias": len(pendencias),
    },
    "detalhes_erro": erros_detail
}

relatorio_path = logs_dir / f"relatorio_auditoria_{timestamp}.json"
with open(relatorio_path, 'w', encoding='utf-8') as f:
    json.dump(relatorio, f, indent=2, ensure_ascii=False)

print(f"Relatorio gerado: {relatorio_path}")
print(f"Total auditados: {len(montados)} | Aprovados: {len(njuds_aprovados)} | Rejeitados: {len(njuds_rejeitados)} | Pendencias: {len(pendencias)}")
print(f"Esperados com 4 cortes OK: {total_esperados}")
print(f"Erros: {len(erros_detail)}")

# Retornar para o agente pai
resultado_json = {
    "auditoria_ok": "NAO_OK" if (njuds_rejeitados or pendencias) else "OK",
    "erro": "; ".join(erros_detail[:5]) if erros_detail else "",
    "njuds_aprovados": str(len(njuds_aprovados)),
    "njuds_rejeitados": str(len(njuds_rejeitados)),
    "pendencias": str(len(pendencias)),
    "relatorio_path": str(relatorio_path),
    "resultado": f"Auditoria concluida: {len(njuds_aprovados)} aprovados, {len(njuds_rejeitados)} rejeitados, {len(pendencias)} pendentes. Relatorio: {relatorio_path}"
}
print("\n=== RESULTADO FINAL ===")
print(json.dumps(resultado_json, indent=2, ensure_ascii=False))
