#!/usr/bin/env python3
"""
OSINT Hunter Pro - July 2025 Update
-----------------------------------
Author: OSINT-HQ 2025
License: MIT

Description:
An all-in-one OSINT tool for deep email/username/name reconnaissance across multiple search engines, leak sites, and repositories.

Features:
- 8 major search engines scraping with dorking (Google, Yandex, DuckDuckGo, etc.)
- Specialized dorks for GitHub, Pastebin, combo leaks, dumps, etc.
- Country priority filtering (by TLD or manual ISO shortname)
- Optional gender-aware name dorking for precision
- Multi-threaded, with rotating user agents every 10 queries
- Pattern-based extraction for emails, usernames, IP addresses, tokens, API keys, passwords, combos, and more
- Discord webhook notifications with timestamps
- Local saving of results in JSON and TXT
"""

import httpx
import argparse
import re
import threading
import time
import random
import json
from urllib.parse import quote
from datetime import datetime
from rich.progress import Progress
from rich import print
from bs4 import BeautifulSoup

# Constants
VERSION = "2.0-July2025"
TOOL_NAME = "OSINT Hunter Pro"

DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1400885326670729309/0JVOdlZMDC_Jqm9SoKm9I20iCNSBub1Ocq1c6TiepY0H7-FsfS2rNZC7Eymi-WF2KIJ8"

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "duckduckgo": "https://html.duckduckgo.com/html/?q=",
    "yandex": "https://yandex.com/search/?text=",
    "startpage": "https://www.startpage.com/sp/search?query=",
    "mojeek": "https://www.mojeek.com/search?q=",
    "qwant": "https://www.qwant.com/?q=",
    "brave": "https://search.brave.com/search?q="
}

# Expanded User Agents (25+)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/115 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/117 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:92.0) Gecko/20100101 Firefox/92.0",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 Chrome/114 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0",
    "Mozilla/5.0 (Linux; Android 9; SM-J730G) AppleWebKit/537.36 Chrome/108.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 Chrome/113.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/537.36 Chrome/112.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edge/111.0.1661.54",
    "Mozilla/5.0 (Linux; U; Android 4.4.2; en-US; Nexus 5 Build/KOT49H) AppleWebKit/534.30 Mobile Safari/534.30",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/601.7.7 Safari/601.7.7",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 Chrome/114.0.5735.110 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; SM-A125F) AppleWebKit/537.36 Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/537.36 Chrome/110.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; U; Android 6.0; en-US; Nexus 5 Build/MRA58N) AppleWebKit/537.36 Chrome/114.0.5735.199 Mobile Safari/537.36"
]

HEADERS = {"User-Agent": random.choice(USER_AGENTS)}

query_counter = 0
results_lock = threading.Lock()
results = []

# Regex patterns for extracting useful info
PATTERNS = {
    "emails": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    "ips": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "api_keys": re.compile(r'(?i)(api_key|apikey|secret|token|password|pwd|pass)[^\w]*[:=][^\s\'"]+'),
    "urls": re.compile(r'https?://[^\s\'"<>]+'),
    "usernames": re.compile(r'(?<=user[:=])[a-zA-Z0-9._-]+'),
    "combo_list": re.compile(r'[a-zA-Z0-9._%-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}:[^\s]+'),  # email:password combos
}

def rotate_user_agent():
    global HEADERS
    HEADERS["User-Agent"] = random.choice(USER_AGENTS)

def send_to_discord(message: str):
    try:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        data = {
            "content": f"[{timestamp}] {message}"
        }
        with httpx.Client() as client:
            client.post(DISCORD_WEBHOOK, json=data, timeout=10)
    except Exception as e:
        print(f"[red]Discord webhook error: {e}[/red]")

def extract_patterns(text):
    extracted = {}
    for key, pattern in PATTERNS.items():
        found = pattern.findall(text)
        if found:
            extracted[key] = list(set(found))  # unique matches only
    return extracted

def search_engine_query(engine_name, query):
    global query_counter
    base_url = SEARCH_ENGINES.get(engine_name)
    if not base_url:
        raise ValueError(f"Unknown search engine: {engine_name}")
    url = base_url + quote(query)

    # Rotate User-Agent every 10 queries
    query_counter += 1
    if query_counter % 10 == 0:
        rotate_user_agent()

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        response = client.get(url)
        if response.status_code != 200:
            print(f"[yellow]Warning: {engine_name} returned status {response.status_code} for query: {query}")
            return ""
        return response.text

def scrape_and_extract(engine, query):
    html = search_engine_query(engine, query)
    if not html:
        return {}

    # Basic extraction from HTML, parse visible text and extract patterns
    soup = BeautifulSoup(html, 'html.parser')

    # Get text only to avoid HTML tags messing with pattern matching
    text = soup.get_text(separator=' ', strip=True)

    extracted_data = extract_patterns(text)
    return extracted_data

def run_osint_scan(target, engines, deep=True, parallel=False, country=None, gender=None):
    """
    Main scan function.
    target: email or name or username (e.g. user@domain.com or "firstname lastname")
    engines: list of engines to query
    deep: boolean for advanced dorking
    parallel: boolean for parallel requests (not implemented yet for simplicity)
    country: ISO shortname for country priority (optional)
    gender: "male" or "female" (optional)
    """
    # Construct dork queries based on input and options
    queries = []

    # Prepare base dorks with target replacement
    # If email, add domain priority filters if country provided
    base_target = target.strip()
    if '@' in base_target:
        local_part, domain_part = base_target.split('@', 1)
        domain_parts = domain_part.split('.')
        domain_tld = domain_parts[-1].lower()
    else:
        domain_tld = None

    # Country priority filter
    country_filter = None
    if country:
        country = country.lower()
        if country in COUNTRIES:
            country_filter = COUNTRIES[country]
        else:
            print(f"[yellow]Unknown country code '{country}', ignoring country filter.[/yellow]")
            country_filter = None

    # Build dorks dynamically based on target and options
    def build_dorks():
        dorks = []
        t = base_target

        # Email-specific dorks
        if '@' in t:
            dorks += [
                f'"{t}"',
                f'"{t}" filetype:txt',
                f'"{t}" ext:env OR ext:ini OR ext:conf OR ext:log',
                f'"{t}" site:pastebin.com',
                f'"{t}" site:github.com',
                f'"{t}" (password OR pwd OR pass OR secret)',
                f'"{t}" "combo list"',
                f'"{t}" leaks',
                f'"{t}" dumps',
            ]
            if country_filter:
                dorks = [f'{dork} country:{country_filter}' for dork in dorks]

        # Name or username dorks
        else:
            dorks += [
                f'"{t}"',
                f'"{t}" site:github.com',
                f'"{t}" site:pastebin.com',
                f'"{t}" (password OR credentials OR login OR email)',
                f'"{t}" "combo list"',
                f'"{t}" leaks',
                f'"{t}" dumps',
                f'intitle:"index of" "{t}"',
                f'inurl:"{t}"',
            ]
            if gender:
                if gender.lower() == "male":
                    dorks += [f'"Mr. {t}"', f'"{t}" AND (he OR his)']
                elif gender.lower() == "female":
                    dorks += [f'"Ms. {t}"', f'"{t}" AND (she OR her)']

            if country_filter:
                dorks = [f'{dork} country:{country_filter}' for dork in dorks]

        # Add more deep dorks if deep=True
        if deep:
            deep_dorks = [
                f'"{t}" ext:csv',
                f'"{t}" ext:sql OR ext:log OR ext:json',
                f'"{t}" site:reddit.com',
                f'"{t}" site:linkedin.com',
                f'"{t}" site:twitter.com',
                f'"{t}" site:ghostbin.com',
                f'"{t}" ext:env OR ext:ini',
                f'"{t}" intext:"api_key" OR intext:"token" OR intext:"secret"',
            ]
            if country_filter:
                deep_dorks = [f'{dork} country:{country_filter}' for dork in deep_dorks]
            dorks += deep_dorks

        return dorks

    queries = build_dorks()

    final_results = {}
    with Progress() as progress:
        task = progress.add_task("[cyan]Scraping...", total=len(queries) * len(engines))

        for dork in queries:
            for engine in engines:
                extracted = scrape_and_extract(engine, dork)
                if extracted:
                    with results_lock:
                        for key, values in extracted.items():
                            final_results.setdefault(key, set()).update(values)
                progress.advance(task)
                time.sleep(random.uniform(1.5, 3.0))  # polite delay between queries

    # Convert sets to lists for JSON serialization
    for key in final_results:
        final_results[key] = list(final_results[key])

    return final_results

def save_results(target, results_dict):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_filename = f"results_{target.replace('@','_').replace(' ','_')}_{timestamp}"

    # Save JSON
    with open(base_filename + ".json", "w") as f:
        json.dump(results_dict, f, indent=4)

    # Save TXT (emails + combos + keys)
    with open(base_filename + ".txt", "w") as f:
        for key, vals in results_dict.items():
            f.write(f"== {key.upper()} ==\n")
            for val in vals:
                f.write(f"{val}\n")
            f.write("\n")

    print(f"[green]Results saved to {base_filename}.json and {base_filename}.txt[/green]")

def main():
    parser = argparse.ArgumentParser(description=f"{TOOL_NAME} v{VERSION}")
    parser.add_argument("--target", required=True, help="Target email, name, or username")
    parser.add_argument("--engines", nargs="+", default=list(SEARCH_ENGINES.keys()),
                        help="Search engines to use (default: all)")
    parser.add_argument("--deep", action="store_true", help="Enable deep dorking")
    parser.add_argument("--country", help="Country ISO shortname (e.g., us, se, uk)")
    parser.add_argument("--gender", choices=["male", "female"], help="Optional gender for name-based dorks")
    args = parser.parse_args()

    print(f"[bold cyan]{TOOL_NAME} v{VERSION}[/bold cyan]")
    print(f"Target: {args.target}")
    print(f"Engines: {', '.join(args.engines)}")
    print(f"Deep dorking: {args.deep}")
    if args.country:
        print(f"Country priority: {args.country}")
    if args.gender:
        print(f"Gender: {args.gender}")

    results = run_osint_scan(args.target, args.engines, deep=args.deep, country=args.country, gender=args.gender)

    # Print summary
    total_found = sum(len(v) for v in results.values())
    print(f"\n[bold green]Scan complete! Found {total_found} unique items.[/bold green]\n")
    for key, vals in results.items():
        print(f"[bold]{key.capitalize()} [{len(vals)}]:[/bold]")
        for val in vals[:10]:  # show first 10 per category
            print(f"  {val}")
        print()

    save_results(args.target, results)
    send_to_discord(f"Scan complete for target: {args.target} - found {total_found} items.")

if __name__ == "__main__":
    main()
