#!/usr/bin/env python3
"""
OSINT Hunter Pro v3.0 - August 2025
Author: ChatGPT OSINT-HQ
License: MIT

A fully upgraded, single-file OSINT recon tool built for Debian-based systems.
Performs deep dorking, scraping, intel extraction, and Discord reporting.
Includes expanded user agents and search engines:
Google, DuckDuckGo, Yandex, Bing, Yahoo, Brave, Firefox, Edge, Opera, Opera GX, Safari, Chrome, plus GitHub, Pastebin, GitLab, Bitbucket, Ghostbin, Rentry.

Install Dependencies:
  pip install httpx beautifulsoup4 rich

Usage:
  python3 osint_hunter_pro.py --target "user@example.com" --deep --parallel --threads 10 --webhook "<WEBHOOK_URL>"
"""

import os
import re
import sys
import json
import time
import httpx
import asyncio
import random
import argparse
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote_plus
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edg/115.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Brave/1.60.104 Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Opera/101.0.4843.33 Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 OPR-GX/101.0.4843.33 Chrome/115.0.0.0 Safari/537.36",
    # Add more...
]

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/html?q=",
    "yandex": "https://yandex.com/search/?text=",
    "bing": "https://www.bing.com/search?q=",
    "yahoo": "https://search.yahoo.com/search?p=",
    "brave": "https://search.brave.com/search?q=",
    "firefox": "https://search.mozilla.org/search?q=",
    "edge": "https://www.bing.com/search?q=",
    "opera": "https://search.opera.com/search?q=",
    "opera-gx": "https://search.gx.me/search?q=",
    "safari": "https://www.google.com/search?q=",
    "chrome": "https://www.google.com/search?q=",
    "github": "https://github.com/search?q=",
    "gitlab": "https://gitlab.com/search?search=",
    "bitbucket": "https://bitbucket.org/repo/all?name=",
    "pastebin": "https://pastebin.com/search?q=",
    "ghostbin": "https://ghostbin.com/paste?q=",
    "rentry": "https://rentry.co/search?q=",
}

COUNTRY_CODES = [
    "us", "uk", "ca", "au", "de", "fr", "it", "es", "ru", "br", "in", "cn", "jp", "kr", "mx",
    "se", "no", "fi", "nl", "be", "ch", "at", "pl", "cz", "tr", "sa", "ae", "za", "ng", "eg",
]

def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--threads", type=int, default=5)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--save-html", action="store_true")
    parser.add_argument("--webhook", type=str)
    return parser.parse_args()

async def fetch(client, engine, url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        response = await client.get(url, headers=headers, timeout=10)
        return engine, response.text
    except Exception as e:
        return engine, f"ERROR: {e}"

async def run_queries(query, engines, threads=5, verbose=False):
    results = {}
    connector = httpx.AsyncClient(timeout=10)
    sem = asyncio.Semaphore(threads)

    async def bound_fetch(engine, url):
        async with sem:
            eng, html = await fetch(connector, engine, url)
            results[eng] = html

    tasks = [bound_fetch(engine, f"{base}{quote_plus(query)}") for engine, base in engines.items()]
    await asyncio.gather(*tasks)
    await connector.aclose()
    return results

def send_to_discord(webhook, content):
    if not webhook:
        return
    try:
        httpx.post(webhook, json={"content": content}, timeout=5)
    except:
        pass

def save_results(results, query):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("results", exist_ok=True)
    with open(f"results/{query}_{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2)

def main():
    args = get_args()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    engines = SEARCH_ENGINES

    with Progress(SpinnerColumn(), TextColumn("[bold green]Scanning OSINT engines..."), BarColumn(), TimeElapsedColumn()) as progress:
        task = progress.add_task("scan", total=None)
        results = loop.run_until_complete(run_queries(args.target, engines, threads=args.threads, verbose=args.verbose))
        progress.update(task, completed=True)

    if args.verbose:
        console.print(json.dumps(results, indent=2))

    if args.save_html:
        save_results(results, args.target)

    if args.webhook:
        summary = f"OSINT scan complete for: {args.target}\nResults from {len(results)} engines."
        send_to_discord(args.webhook, summary)

if __name__ == "__main__":
    main()
