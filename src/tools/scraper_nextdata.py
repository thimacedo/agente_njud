import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

BASE = "https://www.tjrn.jus.br"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": f"{BASE}/tjrnplay/programastv/noticias-da-hora/",
}

LISTING_PATH = "tjrnplay/programastv/noticias-da-hora"
OUTPUT_DIR = Path("./downloads")
AUDIO_EXT_RE = re.compile(r"https?://[^\s\"'<>]+?\.(mp3|wav|m4a|ogg)(\?[^\s\"'<>]*)?", re.IGNORECASE)


def discover_buildid():
    r = requests.get(f"{BASE}/{LISTING_PATH}/", headers={"User-Agent": HEADERS["User-Agent"]}, timeout=20)
    r.raise_for_status()
    m = re.search(r'"buildId":"([^"]+)"', r.text)
    if not m:
        raise RuntimeError("Não foi possível encontrar o buildId no HTML. Bot detection pode ter bloqueado.")
    return m.group(1)


def fetch_json(buildid, rel_path):
    url = f"{BASE}/_next/data/{buildid}/{rel_path}.json"
    r = requests.get(url, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        return None, url, r.status_code
    try:
        return r.json(), url, 200
    except json.JSONDecodeError:
        return None, url, r.status_code


def find_audio_urls(obj):
    found = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            for m in AUDIO_EXT_RE.finditer(node):
                found.add(m.group(0))

    walk(obj)
    return found


def find_news_links(listing_json):
    links = set()
    pattern = re.compile(r"(tjrnplay/programastv/noticias-da-hora/[a-z0-9\-]+)/?", re.IGNORECASE)

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            for m in pattern.finditer(node):
                slug_path = m.group(1)
                if slug_path.rstrip("/") != LISTING_PATH:
                    links.add(slug_path.rstrip("/"))

    walk(listing_json)
    return links


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
    ap.add_argument("--buildid", help="buildId do Next.js")
    ap.add_argument("--discover-buildid", action="store_true")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.discover_buildid:
        try:
            bid = discover_buildid()
            print(f"buildId atual: {bid}")
        except Exception as e:
            print(f"Falha ao descobrir buildId: {e}", file=sys.stderr)
            sys.exit(1)
        return

    buildid = args.buildid
    if not buildid:
        print("Nenhum --buildid informado, tentando descobrir automaticamente...")
        try:
            buildid = discover_buildid()
            print(f"buildId descoberto: {buildid}")
        except Exception as e:
            print(f"Falha: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"\n=== Buscando listagem: {LISTING_PATH} ===")
    listing_json, url, status = fetch_json(buildid, LISTING_PATH)
    print(f"GET {url} -> {status}")
    if listing_json is None:
        print("Não foi possível obter JSON da listagem.")
        sys.exit(1)

    Path("listing_raw.json").write_text(json.dumps(listing_json, ensure_ascii=False, indent=2))
    print("JSON da listagem salvo em listing_raw.json")

    news_links = find_news_links(listing_json)
    print(f"\nEncontrados {len(news_links)} possíveis links de notícia na listagem.")
    for l in list(news_links)[:10]:
        print(f"  - {l}")

    if not news_links:
        print("\nNenhum link de notícia encontrado automaticamente.")
        return

    news_links = sorted(news_links)
    if args.max_pages:
        news_links = news_links[: args.max_pages]

    all_results = []
    for i, rel_path in enumerate(news_links, 1):
        print(f"\n[{i}/{len(news_links)}] {rel_path}")
        news_json, url, status = fetch_json(buildid, rel_path)
        if news_json is None:
            print(f"    falhou ({status}): {url}")
            continue
        audio_urls = find_audio_urls(news_json)
        if audio_urls:
            print(f"    áudio(s) encontrado(s): {audio_urls}")
            for au in audio_urls:
                full_url = urljoin(BASE, au)
                all_results.append({"page": rel_path, "audio_url": full_url})
                if not args.dry_run:
                    download_file(full_url, OUTPUT_DIR)
        else:
            print("    nenhum áudio encontrado neste JSON")
        time.sleep(0.5)

    Path("audio_results.json").write_text(json.dumps(all_results, ensure_ascii=False, indent=2))
    print(f"\n=== Concluído. {len(all_results)} áudios encontrados. Resultado em audio_results.json ===")


if __name__ == "__main__":
    main()
