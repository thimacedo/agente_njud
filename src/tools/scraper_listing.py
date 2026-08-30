import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = "https://radioetv.tjrn.jus.br"
LISTING_URL = f"{BASE}/index.php/radd/radio/programas/noticias-da-hora"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
OUTPUT_DIR = Path("./downloads")
RESULTS_FILE = Path("audio_results_listing.json")

TITLE_RE = re.compile(r'cat-list-row\d+.*?<a[^>]*>(.*?)</a>', re.DOTALL)
MP3_RE = re.compile(r'mp3:["\'](https://radioetv\.tjrn\.jus\.br/images/audio/boletins/[^"\']+\.mp3)["\']')
DATE_IN_FILENAME_RE = re.compile(r"TJRN_(\d{2})_(\d{2})_(\d{4})_")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def fetch_page(start):
    url = f"{LISTING_URL}?start={start}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text, url


def parse_page(html):
    titles_raw = TITLE_RE.findall(html)
    titles = [HTML_TAG_RE.sub("", t).strip() for t in titles_raw]
    mp3s = MP3_RE.findall(html)

    episodes = []
    for i in range(min(len(titles), len(mp3s))):
        mp3_url = mp3s[i]
        filename = mp3_url.split("/")[-1]
        m = DATE_IN_FILENAME_RE.search(filename)
        data = None
        if m:
            dd, mm, yyyy = m.groups()
            try:
                data = datetime(int(yyyy), int(mm), int(dd)).date()
            except ValueError:
                data = None
        episodes.append({
            "titulo": titles[i] if i < len(titles) else None,
            "audio_url": mp3_url,
            "arquivo": filename,
            "data": data.strftime("%d/%m/%Y") if data else None,
            "_data_obj": data,
        })
    return episodes, len(titles), len(mp3s)


def verify(sample_start=0):
    print(f"=== VERIFICAÇÃO: buscando {LISTING_URL}?start={sample_start} ===\n")
    try:
        html, url = fetch_page(sample_start)
    except requests.RequestException as e:
        print(f"[ERRO] Falha ao buscar página: {e}")
        return False

    print(f"GET {url} -> OK, {len(html)} bytes recebidos\n")

    Path("listing_page_sample.html").write_text(html, encoding="utf-8")
    print("HTML salvo em listing_page_sample.html para inspeção manual.\n")

    episodes, n_titles, n_mp3s = parse_page(html)
    print(f"Títulos encontrados (regex cat-list-row): {n_titles}")
    print(f"MP3s encontrados (regex mp3:\"...\"): {n_mp3s}")

    if n_titles == 0 and n_mp3s == 0:
        print("\n[FALHA] Nenhum título nem mp3 encontrado.")
        print("A estrutura real da página não bate com os regex assumidos.")
        print("Abra listing_page_sample.html e me mande um trecho representativo")
        print("de uma linha de item da lista (procure por 'cat-list-row' e 'mp3:').")
        return False

    if n_titles != n_mp3s:
        print(f"\n[AVISO] Quantidade de títulos ({n_titles}) difere de mp3s ({n_mp3s}).")
        print("O zip vai truncar no menor. Pode haver itens sem áudio ou vice-versa.")

    print(f"\nPrimeiros {min(5, len(episodes))} episódios extraídos:")
    for ep in episodes[:5]:
        print(f"  [{ep['data']}] {ep['titulo']}")
        print(f"    -> {ep['audio_url']}")

    print(f"\n{'='*60}")
    if episodes:
        print("[OK] Extração parece funcional. Pode prosseguir com a busca real.")
        return True
    else:
        print("[FALHA] Nenhum episódio combinado (título+mp3). Verifique listing_page_sample.html.")
        return False


def download_file(url, dest_dir):
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0]
    dest = dest_dir / filename
    if dest.exists():
        print(f"    [skip] já existe: {dest}")
        return dest
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"    [ok] baixado: {dest}")
        return dest
    except requests.RequestException as e:
        print(f"    [erro] falha ao baixar {url}: {e}")
        return None


def parse_target_dates(raw_list):
    out = set()
    for s in raw_list:
        s = s.strip()
        if not s:
            continue
        out.add(datetime.strptime(s, "%d/%m/%Y").date())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true",
                     help="Só testa a página start=0 e reporta se os regex funcionam, sem varrer nada")
    ap.add_argument("--verify-start", type=int, default=0, help="Página (valor de start) a usar na verificação")
    ap.add_argument("--target-dates", nargs="+", help="Datas DD/MM/AAAA a buscar")
    ap.add_argument("--target-dates-file", help="Arquivo com uma data DD/MM/AAAA por linha")
    ap.add_argument("--start-from", type=int, default=0, help="Valor de 'start' inicial (0 = página mais recente)")
    ap.add_argument("--max-start", type=int, default=16720, help="Valor máximo de 'start' antes de desistir")
    ap.add_argument("--step", type=int, default=20, help="Incremento de 'start' por página (20 = padrão observado)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delay", type=float, default=1.0, help="Segundos entre requisições (gentileza com o servidor)")
    args = ap.parse_args()

    if args.verify_only:
        verify(args.verify_start)
        return

    target_dates = None
    if args.target_dates:
        target_dates = parse_target_dates(args.target_dates)
    elif args.target_dates_file:
        lines = Path(args.target_dates_file).read_text(encoding="utf-8").splitlines()
        target_dates = parse_target_dates(lines)

    if not target_dates:
        print("Informe --target-dates ou --target-dates-file (ou use --verify-only para só testar).")
        return

    data_mais_antiga = min(target_dates)
    print(f"Buscando {len(target_dates)} data(s)-alvo. Mais antiga: {data_mais_antiga.strftime('%d/%m/%Y')}")
    print("Rode --verify-only antes disso se ainda não confirmou a estrutura da página!\n")

    encontrados = {d: [] for d in target_dates}
    resultados_flat = []
    parar = False

    start = args.start_from
    while start <= args.max_start and not parar:
        print(f"\n--- start={start} ---")
        try:
            html, url = fetch_page(start)
        except requests.RequestException as e:
            print(f"[erro] falha ao buscar {url}: {e}")
            break

        episodes, n_titles, n_mp3s = parse_page(html)
        if not episodes:
            print("Nenhum episódio nesta página. Pode ser o fim da listagem.")
            break

        datas_da_pagina = [ep["_data_obj"] for ep in episodes if ep["_data_obj"]]
        if datas_da_pagina:
            mais_recente = max(datas_da_pagina)
            mais_antiga_pag = min(datas_da_pagina)
            print(f"  {len(episodes)} episódios | datas de {mais_antiga_pag.strftime('%d/%m/%Y')} "
                  f"a {mais_recente.strftime('%d/%m/%Y')}")

        for ep in episodes:
            d = ep["_data_obj"]
            if d and d in target_dates:
                print(f"  >>> MATCH [{ep['data']}] {ep['titulo']}")
                encontrados[d].append(ep)
                resultados_flat.append({k: v for k, v in ep.items() if k != "_data_obj"})
                if not args.dry_run:
                    download_file(ep["audio_url"], OUTPUT_DIR)

        if datas_da_pagina and max(datas_da_pagina) < data_mais_antiga:
            print(f"\nTodas as datas desta página já são anteriores a "
                  f"{data_mais_antiga.strftime('%d/%m/%Y')}. Parando.")
            parar = True
            break

        start += args.step
        time.sleep(args.delay)

    print(f"\n{'='*60}")
    print("RESUMO POR DATA-ALVO:")
    for d in sorted(target_dates):
        qtd = len(encontrados[d])
        status = "OK" if qtd > 0 else "!! NADA ENCONTRADO !!"
        print(f"  {d.strftime('%d/%m/%Y')}: {qtd} boletim(ns) — {status}")

    RESULTS_FILE.write_text(json.dumps(resultados_flat, ensure_ascii=False, indent=2))
    print(f"\nResultado salvo em {RESULTS_FILE}")


if __name__ == "__main__":
    main()
