#!/usr/bin/env python3
"""
OSINT Hunter Pro v2.0 - July 2025
Author: ChatGPT OSINT-HQ
License: MIT

Description:
A terminal-based, Debian-compatible, advanced OSINT tool to perform
extreme deep dorking and scraping on multiple search engines (Google, DuckDuckGo,
Yandex), GitHub, Pastebin, and other leak-rich sources. It accepts queries
like emails, usernames, names with optional gender and country filters.
Results are saved locally and sent live to a Discord webhook with timestamps.

Features:
- Multi-engine scraping with polite rate limiting
- Dynamic user-agent rotation (20+ UAs)
- Deep dorking with many patterns (emails, IPs, combos, tokens, URLs)
- Country and gender prioritized dork tailoring
- Pastebin and GitHub scraping via search queries
- Output to JSON, TXT + Discord webhook posting
- Parallel and sequential modes
- Detailed CLI interface with usage instructions

Requirements:
  pip install httpx beautifulsoup4 rich

Usage example:
  python3 osint_hunter_pro.py --target "user@example.com" --engines google duckduckgo yandex github pastebin --deep --country us --gender male --parallel

"""

import sys
import os
import time
import re
import json
import argparse
import random
import string
from datetime import datetime
from urllib.parse import quote_plus
import asyncio
import httpx
from bs4 import BeautifulSoup
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.console import Console

console = Console()

# --- Constants & Globals ---

DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1400885326670729309/0JVOdlZMDC_Jqm9SoKm9I20iCNSBub1Ocq1c6TiepY0H7-FsfS2rNZC7Eymi-WF2KIJ8"

# User agents pool (20+ realistic UAs)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4_0) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/16.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:102.0) Gecko/20100101 Firefox/102.0",
    "Mozilla/5.0 (Linux; Android 13; SM-G780G) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/115.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_6) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Edg/115.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/113.0.5672.93 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_7_8) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; SM-A515F) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/113.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (iPad; CPU OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/15.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)"
    " Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
]

# Country code to domain TLD / search parameter map
COUNTRIES = {
    "us": "us",
    "se": "se",
    "uk": "uk",
    "de": "de",
    "fr": "fr",
    "ca": "ca",
    "au": "au",
    "ru": "ru",
    "cn": "cn",
    "in": "in",
    # Extend as needed
}

# Supported engines & base search URLs (dork-ready)
SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/html?q=",
    "yandex": "https://yandex.com/search/?text=",
    "github": "https://github.com/search?q=",
    "pastebin": "https://pastebin.com/search?q=",
}

# Deep dork patterns - adapt with your own intelligence
# Searching for emails, IPs, combos, tokens, urls, keys leaks, etc.
BASE_DORKS = [
    '"@{}"',  # Simple email fragment or domain
    '"{}"',   # Exact match
    '"{}" filetype:env',
    '"{}" filetype:log',
    '"{}" filetype:ini',
    '"{}" filetype:txt',
    '"{}" filetype:xml',
    '"{}" intext:"password"',
    '"{}" intext:"passwd"',
    '"{}" intext:"api_key"',
    '"{}" intext:"secret"',
    '"{}" intext:"token"',
    '"{}" intext:"combo"',
    '"{}" ext:json',
    '"{}" ext:env',
    '"{}" ext:log',
    '"{}" ext:ini',
    '"{}" ext:txt',
    '"{}" ext:xml',
]

# Extended deep dork variants (rough, extreme)
EXTREME_DORKS = [
    'site:pastebin.com "{}"',
    'site:github.com "{}"',
    'site:github.com "{}" path:/"{}"',
    '"{}" "password" | "passwd" | "secret" | "token"',
    '"{}" "api_key" | "apikey" | "secret_key"',
    '"{}" "combo list" | "leak" | "dump"',
    '"{}" filetype:xls | filetype:xlsx | filetype:csv',
    '"{}" ext:sql | ext:db',
]

# Regex patterns for extracting meaningful intel from results
PATTERNS = {
    "emails": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ips": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "urls": re.compile(r"https?://[^\s'\"]+"),
    "api_keys": re.compile(r"(?i)(api[_-]?key|secret|token)[\s:=]+['\"]?[\w-]{8,}['\"]?"),
    "combo_lists": re.compile(r"[a-zA-Z0-9._%-]+:[a-zA-Z0-9._%-]+"),
}

# Rate limits and delays (seconds)
MIN_DELAY = 1.5
MAX_DELAY = 3.0

# Max concurrency
MAX_CONCURRENT_REQUESTS = 5


# --- Utility Functions ---

def generate_user_agent(index: int) -> str:
    """Rotate user agents every 10 requests."""
    return USER_AGENTS[(index // 10) % len(USER_AGENTS)]


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def build_dorks(query: str, deep: bool, country: str = None, gender: str = None) -> list:
    """Generate dorks with given parameters, including country and gender prioritization."""
    dorks = []

    q = query.strip()
    # Add country filter if valid
    country_filter = ""
    if country and country.lower() in COUNTRIES:
        country_filter = f" country:{COUNTRIES[country.lower()]}"
    
    # Gender used to add more tailored dorks, e.g. firstname+gender leaks
    gender = gender.lower() if gender else None

    # Basic dorks
    for pattern in BASE_DORKS:
        dork = pattern.format(q) + country_filter
        dorks.append(dork)

    if deep:
        # Add extreme deep dorks too
        for pattern in EXTREME_DORKS:
            try:
                dork = pattern.format(q, q)
                if country_filter:
                    dork += country_filter
                dorks.append(dork)
            except Exception:
                continue

    # Optionally add gender-based dorks (if given and query looks like a first name)
    if gender and len(q.split()) == 1:
        gender_dorks = [
            f'"{q}" "{gender}" email',
            f'"{q}" "{gender}" password',
            f'"{q}" "{gender}" leak',
        ]
        dorks.extend(gender_dorks)

    return list(set(dorks))  # unique


async def fetch(client: httpx.AsyncClient, url: str, user_agent: str):
    """Async HTTP GET with UA header and error handling."""
    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = await client.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.text
        else:
            console.log(f"[red]HTTP {resp.status_code} at {url}")
            return ""
    except Exception as e:
        console.log(f"[red]Exception fetching {url}: {e}")
        return ""


def extract_intel(html: str) -> dict:
    """Extract intel patterns from raw html/text."""
    found = {k: set() for k in PATTERNS.keys()}
    for key, pattern in PATTERNS.items():
        matches = pattern.findall(html)
        if matches:
            found[key].update(matches)
    return found


async def post_to_discord(webhook_url: str, content: str):
    """Post a message to Discord webhook asynchronously."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(webhook_url, json={"content": content})
            if resp.status_code not in (200, 204):
                console.log(f"[yellow]Discord webhook returned status {resp.status_code}")
        except Exception as e:
            console.log(f"[red]Failed to send Discord message: {e}")


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-\.]", "_", name)


# --- Core scanning logic ---

async def query_engine(client, engine: str, dork: str, ua_index: int):
    """Query one search engine with a dork, return extracted intel."""
    base_url = SEARCH_ENGINES.get(engine)
    if not base_url:
        console.log(f"[red]Unsupported engine: {engine}")
        return {}

    encoded_dork = quote_plus(dork)
    url = base_url + encoded_dork

    user_agent = generate_user_agent(ua_index)

    html = await fetch(client, url, user_agent)
    if not html:
        return {}

    # Extract intel from html
    intel = extract_intel(html)
    return intel


async def run_queries(target: str, engines: list, deep: bool, country: str, gender: str, parallel: bool):
    """Run queries across engines and dorks, aggregate results."""
    dorks = build_dorks(target, deep, country, gender)

    total_queries = len(dorks) * len(engines)
    console.log(f"Total queries to run: {total_queries}")

    results_agg = {k: set() for k in PATTERNS.keys()}

    ua_index = 0
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async with httpx.AsyncClient() as client:

        async def sem_query(engine, dork, idx):
            async with semaphore:
                nonlocal ua_index
                ua_index += 1
                intel = await query_engine(client, engine, dork, ua_index)
                await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                return intel

        tasks = []
        for dork in dorks:
            for engine in engines:
                if parallel:
                    tasks.append(sem_query(engine, dork, ua_index))
                else:
                    # sequential: await one by one
                    intel = await sem_query(engine, dork, ua_index)
                    for k in results_agg:
                        results_agg[k].update(intel.get(k, []))
                    console.log(f"[green]Queried {engine} for dork: {dork[:60]}...")

        if parallel and tasks:
            progress = Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(), TimeElapsedColumn())
            with progress:
                task = progress.add_task("[cyan]Running queries...", total=len(tasks))
                for future in asyncio.as_completed(tasks):
                    intel = await future
                    for k in results_agg:
                        results_agg[k].update(intel.get(k, []))
                    progress.update(task, advance=1)
                    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

    return results_agg


def save_results(target: str, results: dict):
    """Save results locally in JSON and TXT formats."""
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_target = sanitize_filename(target)
    basepath = f"results_{safe_target}_{now}"

    # JSON output
    json_path = basepath + ".json"
    with open(json_path, "w", encoding="utf-8") as fjson:
        json.dump({k: list(v) for k, v in results.items()}, fjson, indent=2)

    # TXT output
    txt_path = basepath + ".txt"
    with open(txt_path, "w", encoding="utf-8") as ftxt:
        ftxt.write(f"OSINT Hunter Pro Scan Results for: {target}\n")
        ftxt.write(f"Timestamp: {datetime.utcnow().isoformat()} UTC\n\n")
        for key, items in results.items():
            ftxt.write(f"{key.upper()} [{len(items)}]:\n")
            for item in sorted(items):
                ftxt.write(f"  {item}\n")
            ftxt.write("\n")

    return json_path, txt_path


async def send_results_discord(results: dict, target: str):
    """Send all intel to Discord webhook in batches."""
    header = f"**OSINT Hunter Pro Scan Results for:** `{target}`  \nTimestamp: {timestamp()}\n"
    content = header
    max_chunk = 1800  # Discord message limit buffer

    def chunkify(text, size):
        return [text[i:i+size] for i in range(0, len(text), size)]

    # Format the results into Discord messages
    messages = []
    for key, items in results.items():
        if not items:
            continue
        part = f"__**{key.upper()} [{len(items)}]**__:\n"
        for item in sorted(items):
            part += f"- {item}\n"
            if len(part) > max_chunk:
                messages.append(part)
                part = ""
        if part:
            messages.append(part)

    # Send header + each chunk separately
    if messages:
        await post_to_discord(DISCORD_WEBHOOK_URL, content)
        for msg in messages:
            await post_to_discord(DISCORD_WEBHOOK_URL, msg)
    else:
        await post_to_discord(DISCORD_WEBHOOK_URL, content + "\nNo results found.")


# --- Main CLI ---

def parse_args():
    parser = argparse.ArgumentParser(description="OSINT Hunter Pro v2.0 - Extreme Deep OSINT Scraper")
    parser.add_argument("--target", type=str, required=True,
                        help='Target query: full email, "@domain.ext", username, or name')
    parser.add_argument("--engines", nargs="+", default=list(SEARCH_ENGINES.keys()),
                        choices=SEARCH_ENGINES.keys(),
                        help="Search engines to use (default: all)")
    parser.add_argument("--deep", action="store_true",
                        help="Enable extreme deep dorking mode")
    parser.add_argument("--country", type=str, default=None,
                        help="Country code to prioritize (e.g. us, se, uk)")
    parser.add_argument("--gender", type=str, choices=["male", "female"], default=None,
                        help="Optional gender hint for name-based queries")
    parser.add_argument("--parallel", action="store_true",
                        help="Run queries in parallel (faster but heavier on resources)")
    parser.add_argument("--no-discord", action="store_true",
                        help="Disable sending results to Discord webhook")
    parser.add_argument("--version", action="version", version="OSINT Hunter Pro v2.0 (July 2025)")
    return parser.parse_args()


async def main():
    args = parse_args()

    console.print(f"[bold cyan]OSINT Hunter Pro v2.0 - Starting scan on target:[/bold cyan] {args.target}")
    console.print(f"[yellow]Engines:[/yellow] {', '.join(args.engines)} | Deep: {args.deep} | Country: {args.country} | Gender: {args.gender}")
    console.print(f"[yellow]Mode:[/yellow] {'Parallel' if args.parallel else 'Sequential'}")

    results = await run_queries(args.target, args.engines, args.deep, args.country, args.gender, args.parallel)

    json_path, txt_path = save_results(args.target, results)
    console.print(f"[green]Results saved locally to:[/green] {json_path} and {txt_path}")

    if not args.no_discord:
        console.print("[blue]Sending results to Discord webhook...[/blue]")
        await send_results_discord(results, args.target)
        console.print("[green]Results sent to Discord webhook.[/green]")

    console.print("[bold green]Scan complete.[/bold green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[red]Scan interrupted by user.[/red]")
        sys.exit(1)
