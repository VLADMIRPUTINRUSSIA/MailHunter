#!/usr/bin/env python3
"""
OSINT Hunter - Deep Targeted Search Engine Scraper
MIT License
Author: OSINT-HQ (2025)
Description: Terminal-based, Debian-compatible, deep dork search and scraping engine for emails, usernames, names.
"""

import httpx
import re
import time
import json
import argparse
import random
from datetime import datetime
from bs4 import BeautifulSoup
from rich import print
from rich.progress import Progress
import threading

# Constants
VERSION = "1.1"
TOOL_NAME = "OSINT Hunter Deep"
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1400885326670729309/0JVOdlZMDC_Jqm9SoKm9I20iCNSBub1Ocq1c6TiepY0H7-FsfS2rNZC7Eymi-WF2KIJ8"

# Rotating User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/117 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:92.0) Gecko/20100101 Firefox/92.0",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 Chrome/114 Mobile Safari/537.36",
]

HEADERS = {"User-Agent": random.choice(USER_AGENTS)}

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://html.duckduckgo.com/html/?q=",
    "yandex": "https://yandex.com/search/?text=",
    "startpage": "https://www.startpage.com/sp/search?query=",
    "mojeek": "https://www.mojeek.com/search?q=",
    "qwant": "https://www.qwant.com/?q=",
    "brave": "https://search.brave.com/search?q="
}

DORKS = [
    'filetype:txt intext:"{}"',
    'intext:"{}" site:pastebin.com',
    'intitle:"index of" "{}"',
    'inurl:"{}"',
    '"{}" ext:sql | ext:log | ext:txt | ext:json',
    '"{}" AND ("password" | "credentials")',
    '"{}" site:github.com',
    'site:reddit.com "{}"',
    'site:linkedin.com/in "{}"',
    'site:twitter.com "{}"',
    'cache:"{}"',
    'related:"{}"',
    'allintext:"{}"',
    'allinurl:"{}"'
]

query_counter = 0


def extract_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if 'http' in href:
            links.add(href)
    return list(links)


def rotate_user_agent():
    global HEADERS
    HEADERS = {"User-Agent": random.choice(USER_AGENTS)}


def search_engine_query(engine, query):
    global query_counter
    if query_counter % 10 == 0:
        rotate_user_agent()
    url = SEARCH_ENGINES.get(engine, "") + httpx.utils.quote(query)
    try:
        response = httpx.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"[yellow]Warning: {engine} query failed: {e}[/yellow]")
    return ""


def generate_dork_queries(target):
    return [d.format(target) for d in DORKS]


def save_results(results, target):
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    fname = target.replace('@', '_at_').replace('.', '_')
    json_path = f"results_{fname}_{timestamp}.json"
    txt_path = f"results_{fname}_{timestamp}.txt"
    with open(json_path, 'w') as jf:
        json.dump(results, jf, indent=2)
    with open(txt_path, 'w') as tf:
        for engine, links in results.items():
            tf.write(f"\n=== {engine.upper()} ===\n")
            for link in links:
                tf.write(f"{link}\n")
    print(f"[green]Results saved: {json_path}, {txt_path}[/green]")
    return txt_path


def send_to_discord(path):
    try:
        with open(path, 'r') as f:
            content = f.read()[:1900]  # Discord limit
        httpx.post(DISCORD_WEBHOOK, json={"content": f"**{TOOL_NAME} Results**\nTimestamp: {datetime.utcnow()} UTC\n```{content}```"})
    except Exception as e:
        print(f"[red]Discord send error: {e}[/red]")


def scan_target_on_engine(engine, queries, results):
    global query_counter
    results[engine] = []
    for query in queries:
        html = search_engine_query(engine, query)
        links = extract_links(html)
        results[engine].extend(links)
        query_counter += 1
        time.sleep(2)


def run_scan(target, engines, deep=False, parallel=False):
    dork_queries = generate_dork_queries(target) if deep else [target]
    results = {}

    if parallel:
        threads = []
        for engine in engines:
            t = threading.Thread(target=scan_target_on_engine, args=(engine, dork_queries, results))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
    else:
        with Progress() as progress:
            task = progress.add_task("[cyan]Scraping...", total=len(engines) * len(dork_queries))
            for engine in engines:
                results[engine] = []
                for query in dork_queries:
                    html = search_engine_query(engine, query)
                    links = extract_links(html)
                    results[engine].extend(links)
                    query_counter += 1
                    progress.update(task, advance=1)
                    time.sleep(2)

    return results


def main():
    parser = argparse.ArgumentParser(description=f"{TOOL_NAME} v{VERSION}")
    parser.add_argument("--target", required=True, help="Email, username or name to scan")
    parser.add_argument("--deep", action="store_true", help="Enable deep dorking")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel engine search")
    parser.add_argument("--engines", default="google,duckduckgo,yandex,startpage,mojeek,qwant,brave",
                        help="Comma-separated list of engines")
    args = parser.parse_args()

    engines = [e.strip() for e in args.engines.split(",") if e.strip() in SEARCH_ENGINES]

    print(f"[bold blue]{TOOL_NAME} v{VERSION}[/bold blue]")
    print(f"Target: [bold]{args.target}[/bold] | Engines: {len(engines)} | Deep: {args.deep} | Parallel: {args.parallel}")

    results = run_scan(args.target, engines, deep=args.deep, parallel=args.parallel)
    path = save_results(results, args.target)
    send_to_discord(path)
    print("[bold green]Scan complete.[/bold green]")


if __name__ == "__main__":
    main()
