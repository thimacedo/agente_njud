import argparse
import json
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://radioetv.tjrn.jus.br"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
}
OUTPUT_DIR = Path("./downloads")
RESULTS_FILE = Path("audio_results_joomla.json")


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_article(html, page_url):
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1.article-title")
    title = title_el.get_text(strip=True) if title_el else None

    published_el = soup.select_one("dd.published")
    published = (
        published_el.get_text(strip=True).replace("Publicado em", "").strip()
        if published_el
        else None
    )

    audio_url = None
    source_el = soup.select_one("article audio source[src]")
    if source_el and source_el.get("src"):
        audio_url = urljoin(page_url, source_el["src"])
    else:
        download_link = soup.find(
            "a", string=lambda s: s and "baixar audio" in s.lower()
        )
        if download_link and download_link.get("href"):
            audio_url = urljoin(page_url, download_link["href"])

    next_url = None
    next_el = soup.select_one("ul.pager li.next a[href]")
    if next_el:
        next_url = urljoin(page_url, next_el["href"])

    return {
        "url": page_url,
        "title": title,
        "published": published,
        "audio_url": audio_url,
        "next_url": next_url,
    }


def find_latest_article_url(listing_html, listing_url):
    soup = BeautifulSoup(listing_html, "html.parser")
    link = soup.select_one("a[href*='noticias-da-hora/']")
    if link and link.get("href"):
        return urljoin(listing_url, link["href"])
    return None


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-url", help="URL de um artigo específico para começar")
    ap.add_argument(
        "--listing-url",
        help="URL da listagem, para descobrir o artigo mais recente automaticamente",
    )
    ap.add_argument(
        "--max-pages", type=int, default=20, help="Quantidade de edições a percorrer via 'next'"
    )
    ap.add_argument("--dry-run", action="store_true", help="Não baixa, só lista o que encontrou")
    ap.add_argument(
        "--delay", type=float, default=0.8, help="Segundos de espera entre requisições"
    )
    args = ap.parse_args()

    current_url = args.start_url
    if not current_url and args.listing_url:
        print(f"Buscando listagem: {args.listing_url}")
        listing_html = fetch(args.listing_url)
        current_url = find_latest_article_url(listing_html, args.listing_url)
        if not current_url:
            print("Não foi possível achar um link de artigo na listagem.")
            print("Salvando listing_raw.html para inspeção manual.")
            Path("listing_raw.html").write_text(listing_html, encoding="utf-8")
            return
        print(f"Artigo mais recente encontrado: {current_url}")

    if not current_url:
        print("Informe --start-url ou --listing-url")
        return

    results = []
    seen = set()
    for i in range(args.max_pages):
        if not current_url or current_url in seen:
            break
        seen.add(current_url)
        print(f"\n[{i+1}/{args.max_pages}] {current_url}")

        try:
            html = fetch(current_url)
        except requests.RequestException as e:
            print(f"    [erro] falha ao buscar página: {e}")
            break

        info = parse_article(html, current_url)
        print(f"    título: {info['title']}")
        print(f"    publicado: {info['published']}")
        print(f"    áudio: {info['audio_url']}")

        if info["audio_url"]:
            results.append(info)
            if not args.dry_run:
                download_file(info["audio_url"], OUTPUT_DIR)
        else:
            print("    [aviso] nenhum áudio encontrado nesta página")

        current_url = info["next_url"]
        time.sleep(args.delay)

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n=== Concluído. {len(results)} edições processadas. Resultado em {RESULTS_FILE} ===")


if __name__ == "__main__":
    main()
