import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

AUDIO_EXT_RE = re.compile(r"\.(mp3|wav|m4a|ogg|m3u8)(\?.*)?$", re.IGNORECASE)
OUTPUT_DIR = Path("./downloads")
RESULTS_FILE = Path("audio_results_playwright.json")
LISTING_URL = "https://www.tjrn.jus.br/tjrnplay/programastv/noticias-da-hora/"


def discover_news_urls(page, listing_url, max_pages=None):
    page.goto(listing_url, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    hrefs = page.eval_on_selector_all(
        "a[href*='/tjrnplay/programastv/noticias-da-hora/']",
        "els => els.map(e => e.getAttribute('href'))",
    )
    base = "https://www.tjrn.jus.br"
    urls = set()
    for h in hrefs:
        if not h:
            continue
        full = urljoin(base, h)
        if full.rstrip("/") != listing_url.rstrip("/"):
            urls.add(full)
    urls = sorted(urls)
    if max_pages:
        urls = urls[:max_pages]
    return urls


def extract_audio_from_page(browser, url):
    audio_urls = set()
    context = browser.new_context(user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ))
    page = context.new_page()

    def on_response(response):
        req_url = response.url
        if AUDIO_EXT_RE.search(req_url):
            audio_urls.add(req_url)
        try:
            ctype = response.headers.get("content-type", "")
            if "audio" in ctype:
                audio_urls.add(req_url)
        except Exception:
            pass

    page.on("response", on_response)
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)
        for sel in [
            "button[aria-label*='play' i]",
            "button[aria-label*='reproduzir' i]",
            "[class*='play' i]",
            "audio",
        ]:
            try:
                el = page.query_selector(sel)
                if el:
                    el.click(timeout=2000)
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                continue
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"    [erro navegando] {e}")
    finally:
        context.close()
    return audio_urls


def download_file(url, dest_dir, referer=None):
    import requests
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0] or "audio.mp3"
    dest = dest_dir / filename
    if dest.exists():
        print(f"    [skip] já existe: {dest}")
        return dest
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"    [ok] baixado: {dest}")
        return dest
    except Exception as e:
        print(f"    [erro] falha ao baixar {url}: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listing-url", default=LISTING_URL)
    ap.add_argument("--urls-file", default=None)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headless", action="store_true", default=True)
    args = ap.parse_args()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        if args.urls_file:
            news_urls = [
                line.strip() for line in Path(args.urls_file).read_text().splitlines() if line.strip()
            ]
        else:
            page = browser.new_page()
            news_urls = discover_news_urls(page, args.listing_url, max_pages=args.max_pages)
            page.close()
            print(f"Encontradas {len(news_urls)} notícias na listagem.")

        if args.max_pages:
            news_urls = news_urls[: args.max_pages]

        results = []
        for i, url in enumerate(news_urls, 1):
            print(f"\n[{i}/{len(news_urls)}] {url}")
            audio_urls = extract_audio_from_page(browser, url)
            if audio_urls:
                print(f"    áudio(s) detectado(s): {audio_urls}")
                for au in audio_urls:
                    results.append({"page": url, "audio_url": au})
                    if not args.dry_run:
                        download_file(au, OUTPUT_DIR, referer=url)
            else:
                print("    nenhum áudio detectado na rede")
            time.sleep(0.5)

        browser.close()

    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n=== Concluído. {len(results)} áudios detectados. Resultado em {RESULTS_FILE} ===")


if __name__ == "__main__":
    main()
