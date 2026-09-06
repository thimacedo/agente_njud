#!/usr/bin/env python3
"""
Painel visual da produção PRODUCAO_2026.

Modos:
    dashboard.py --once      gera o HTML uma vez
    dashboard.py --loop      regenera a cada N segundos (padrão 30)

Saída: data/output/_logs/dashboard.html (abra no navegador; auto-recarrega).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE = Path(r"F:\Projetos\DIVISOR\data\processed\PRODUCAO_2026")
JORNAIS = Path(r"F:\Projetos\DIVISOR\JORNAIS")
ESTADO = BASE / "estado_por_arquivo"
FINAL = BASE / "JORNAIS_FINAL"
HEARTBEAT = BASE / "_heartbeat"
SAIDA = Path(r"F:\Projetos\DIVISOR\data\output\_logs\dashboard.html")

STATUS_OK = ("OK", "ESGOTADO_ACEITO")
CORES = {
    "OK": "#22c55e",
    "ESGOTADO_ACEITO": "#84cc16",
    "ESGOTADO": "#ef4444",
    "ERRO": "#dc2626",
    "FALHA": "#dc2626",
}


def coletar() -> dict:
    demanda_mes: dict[str, set[str]] = {}
    demanda_njud: dict[str, str] = {}
    if JORNAIS.is_dir():
        for mes in sorted(JORNAIS.iterdir()):
            if not mes.is_dir() or mes.name.startswith("_"):
                continue
            for mp3 in mes.rglob("*.mp3"):
                njud = mp3.parent.name
                demanda_mes.setdefault(mes.name, set()).add(njud)
                demanda_njud[njud] = mes.name

    estados: dict[str, dict] = {}
    if ESTADO.is_dir():
        for f in ESTADO.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            chave = Path(d.get("arquivo", f.stem)).stem
            estados[chave] = d

    njud_estado: dict[str, dict[str, int]] = {}
    for d in estados.values():
        njud = d.get("njud", "?")
        st_ = d.get("status", "?")
        njud_estado.setdefault(njud, {})
        njud_estado[njud][st_] = njud_estado[njud].get(st_, 0) + 1

    status_counts: dict[str, int] = {}
    for d in estados.values():
        status_counts[d.get("status", "?")] = status_counts.get(d.get("status", "?"), 0) + 1

    heartbeat = None
    hb_arq = HEARTBEAT / "worker_0.json"
    if hb_arq.exists():
        try:
            hb = json.loads(hb_arq.read_text(encoding="utf-8"))
            idade = time.time() - hb.get("timestamp", 0)
            hb["idade_s"] = round(idade)
            hb["vivo"] = idade < 120
            hb["arquivo"] = Path(hb.get("tarefa_atual", "")).name
            hb["njud_atual"] = Path(hb.get("tarefa_atual", "")).parent.name
            heartbeat = hb
        except Exception:
            pass

    jornais_final = sorted(p.name for p in FINAL.glob("*.mp3")) if FINAL.is_dir() else []

    return {
        "demanda_mes": demanda_mes,
        "demanda_njud": demanda_njud,
        "njud_estado": njud_estado,
        "status_counts": status_counts,
        "heartbeat": heartbeat,
        "jornais_final": jornais_final,
    }


def barra(pct: float, cor: str = "#3b82f6") -> str:
    pct = max(0.0, min(100.0, pct))
    return (
        f'<div class="bar"><div class="fill" style="width:{pct:.1f}%;'
        f'background:{cor}"></div></div>'
    )


def gerar_html(dados: dict) -> str:
    demanda_total = sum(len(v) for v in dados["demanda_mes"].values()) * 4
    contagem: dict[str, int] = {}
    for mes, njuds in dados["demanda_mes"].items():
        for njud in njuds:
            for st_, qtd in dados["njud_estado"].get(njud, {}).items():
                if st_ in STATUS_OK:
                    contagem[mes] = contagem.get(mes, 0) + qtd

    ok_total = sum(
        qtd for st_, qtd in dados["status_counts"].items() if st_ in STATUS_OK
    )
    esgotado = dados["status_counts"].get("ESGOTADO", 0)
    erro = dados["status_counts"].get("ERRO", 0) + dados["status_counts"].get("FALHA", 0)
    processado = sum(dados["status_counts"].values())
    pct_geral = (processado / demanda_total * 100) if demanda_total else 0

    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    hb = dados["heartbeat"]
    if hb:
        vivo = hb.get("vivo", False)
        hb_html = (
            f'<span class="pill {"pill-ok" if vivo else "pill-bad"}">'
            f'{"ATIVO" if vivo else "SEM SINAL"}</span> '
            f"PID {hb.get('pid', '?')} — {hb.get('njud_atual', '?')}: "
            f"<code>{hb.get('arquivo', '?')}</code> "
            f"(atualizado há {hb.get('idade_s', '?')}s)"
        )
    else:
        hb_html = '<span class="pill pill-bad">SEM HEARTBEAT</span>'

    linhas_mes = []
    for mes in sorted(dados["demanda_mes"]):
        njuds = dados["demanda_mes"][mes]
        esperado = len(njuds) * 4
        ok_mes = contagem.get(mes, 0)
        pct = ok_mes / esperado * 100 if esperado else 0
        cor = "#22c55e" if pct >= 100 else "#3b82f6"
        linhas_mes.append(
            f"<tr><td>{mes}</td><td>{len(njuds)}</td><td>{ok_mes}/{esperado}</td>"
            f"<td>{barra(pct, cor)}</td><td>{pct:.0f}%</td></tr>"
        )

    chips = []
    for njud in sorted(dados["demanda_njud"]):
        esperado = 4
        sts = dados["njud_estado"].get(njud, {})
        ok_n = sum(q for s, q in sts.items() if s in STATUS_OK)
        esc = sts.get("ESGOTADO", 0)
        if esc > 0:
            classe, rotulo = "chip-esc", f"{ok_n}/{esperado} +{esc} esc."
        elif ok_n >= esperado:
            classe, rotulo = "chip-ok", njud.replace("NJUD ", "")
        elif ok_n > 0:
            classe, rotulo = "chip-and", f"{njud.replace('NJUD ', '')} ({ok_n})"
        else:
            classe, rotulo = "chip-pen", njud.replace("NJUD ", "")
        chips.append(f'<span class="chip {classe}" title="{njud}: {sts}">{rotulo}</span>')

    if dados["jornais_final"]:
        montagem_html = "<br>".join(dados["jornais_final"])
    else:
        montagem_html = '<span class="muted">Montagem ainda não começou — inicia automaticamente quando todos os cortes terminarem.</span>'

    dist_html = " ".join(
        f'<span class="pill" style="background:#1e293b">{st_}: {qtd}</span>'
        for st_, qtd in sorted(dados["status_counts"].items())
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="20">
<title>DIVISOR — Produção 2026</title>
<style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
 h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
 .muted{{color:#64748b}} code{{background:#1e293b;padding:2px 6px;border-radius:4px;font-size:12px}}
 .cards{{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px}}
 .card{{background:#1e293b;border-radius:10px;padding:16px 20px;min-width:150px}}
 .card .num{{font-size:28px;font-weight:700}} .card .lbl{{color:#94a3b8;font-size:12px}}
 .bar{{background:#334155;border-radius:6px;height:14px;min-width:180px;overflow:hidden}}
 .fill{{height:100%;border-radius:6px;transition:width .6s}}
 table{{border-collapse:collapse;width:100%;max-width:760px}}
 td,th{{padding:6px 10px;border-bottom:1px solid #334155;text-align:left;font-size:14px}}
 th{{color:#94a3b8;font-size:12px;text-transform:uppercase}}
 .pill{{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;background:#334155}}
 .pill-ok{{background:#14532d;color:#86efac}} .pill-bad{{background:#7f1d1d;color:#fca5a5}}
 .chips{{display:flex;flex-wrap:wrap;gap:6px;max-width:1100px}}
 .chip{{padding:4px 9px;border-radius:6px;font-size:12px;font-family:monospace}}
 .chip-ok{{background:#14532d;color:#86efac}} .chip-and{{background:#1e3a8a;color:#93c5fd}}
 .chip-pen{{background:#334155;color:#94a3b8}} .chip-esc{{background:#7f1d1d;color:#fca5a5}}
</style></head><body>
<h1>DIVISOR — Produção 2026 <span class="muted" style="font-size:13px">atualizado {agora} · página recarrega a cada 20s</span></h1>

<div class="cards">
 <div class="card"><div class="num">{processado}/{demanda_total}</div><div class="lbl">cortes processados</div>{barra(pct_geral)}</div>
 <div class="card"><div class="num" style="color:#22c55e">{ok_total}</div><div class="lbl">OK</div></div>
 <div class="card"><div class="num" style="color:#ef4444">{esgotado + erro}</div><div class="lbl">esgotados / erro</div></div>
 <div class="card"><div class="num" style="color:#a78bfa">{len(dados['jornais_final'])}</div><div class="lbl">jornais montados</div></div>
</div>

<h2>Worker</h2>
<div>{hb_html}</div>
<div style="margin-top:8px">{dist_html}</div>

<h2>Progresso por mês</h2>
<table><tr><th>Mês</th><th>NJUDs</th><th>Cortes OK</th><th></th><th>%</th></tr>
{''.join(linhas_mes)}</table>

<h2>Mapa dos 138 NJUDs</h2>
<div class="chips">{''.join(chips)}</div>

<h2>Jornais montados (JORNAIS_FINAL)</h2>
<div>{montagem_html}</div>
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loop", action="store_true", help="regenera continuamente")
    ap.add_argument("--intervalo", type=int, default=30)
    args = ap.parse_args()

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    while True:
        SAIDA.write_text(gerar_html(coletar()), encoding="utf-8")
        if not args.loop:
            break
        time.sleep(args.intervalo)


if __name__ == "__main__":
    sys.exit(main())
