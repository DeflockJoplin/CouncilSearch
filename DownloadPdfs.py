#!/usr/bin/env python
"""
Joplin City‑Council PDF/packet scraper (2023‑2025)

Changes compared with the previous version:
* Extracts the meeting date from each meeting page.
* Saves each file as <MMDDYYYY>_<type><original‑extension>.
  – agenda  → “…_agenda.pdf”
  – minutes → “…_minutes.pdf”
  – packet  → “…_packet.<ext>”
  – other   → “…_other.<ext>”

All other behaviour (progress bars, polite delays, duplicate skipping) is unchanged.
"""

import re
import time
from pathlib import Path
from typing import List, Set, Tuple

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ----------------------------------------------------------------------
BASE_URL = "https://www.joplinmo.org"
# Example: https://www.joplinmo.org/AgendaCenter/City-Council-26?MOBILE=ON&year=2023
LIST_URL_TMPL = BASE_URL + "/AgendaCenter/City-Council-26?MOBILE=ON&year={year}"

# ----------------------------------------------------------------------
def fetch(url: str) -> str:
    """GET *url* and return its HTML (raises on failure)."""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text


def absolute_url(href: str) -> str:
    """Convert a possibly‑relative href into a full URL."""
    if href.startswith("http"):
        return href
    return BASE_URL + (href if href.startswith("/") else "/" + href)


def extract_meeting_ids(list_html: str) -> List[int]:
    """Pull every numeric meeting ID from the yearly overview page."""
    soup = BeautifulSoup(list_html, "html.parser")
    ids: List[int] = []
    for a in soup.find_all("a", href=True):
        m = re.search(r"/AgendaCenter/26/(\d+)", a["href"])
        if m:
            ids.append(int(m.group(1)))
    # Preserve order, drop duplicates
    seen: Set[int] = set()
    uniq: List[int] = []
    for i in ids:
        if i not in seen:
            uniq.append(i)
            seen.add(i)
    return uniq


def parse_meeting_date(page_html: str) -> str:
    """
    Extract the meeting date from the meeting page and return it as MMDDYYYY.
    The page usually contains a header like:
        “Monday, May 1, 2023”
    If the date cannot be parsed, fall back to the meeting ID (so we still get a filename).
    """
    soup = BeautifulSoup(page_html, "html.parser")
    # Try a few common selectors – the exact markup can vary slightly.
    possible_texts = []

    # 1. Look for a <h1>/<h2>/<h3> that contains a month name
    for tag in soup.find_all(["h1", "h2", "h3", "div", "span"]):
        txt = tag.get_text(strip=True)
        if txt:
            possible_texts.append(txt)

    # 2. Look for a <meta> or <title> that contains a date
    if soup.title:
        possible_texts.append(soup.title.string or "")

    month_names = (
        "January February March April May June July August September October November December"
    )
    month_regex = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    date_pattern = re.compile(
        rf"{month_regex}\s+(\d{{1,2}}),?\s+(\d{{4}})", re.IGNORECASE
    )

    for txt in possible_texts:
        m = date_pattern.search(txt)
        if m:
            month_str, day_str, year_str = m.group(1), m.group(2), m.group(3)
            # Convert month name to number
            month_num = {
                "January": "01",
                "February": "02",
                "March": "03",
                "April": "04",
                "May": "05",
                "June": "06",
                "July": "07",
                "August": "08",
                "September": "09",
                "October": "10",
                "November": "11",
                "December": "12",
            }[month_str.capitalize()]
            day_num = day_str.zfill(2)
            return f"{month_num}{day_num}{year_str}"
    # If we get here we couldn't locate a readable date – caller will handle fallback.
    return ""


def extract_file_links(page_html: str) -> List[Tuple[str, str]]:
    """
    Return a list of (url, type) tuples for every downloadable file on a meeting page.
    Types are one of: "agenda", "minutes", "packet", "other".
    """
    soup = BeautifulSoup(page_html, "html.parser")
    files: List[Tuple[str, str]] = []

    # Extensions we treat as generic downloadable files
    EXTENSIONS = (".pdf", ".zip", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Normalise to an absolute URL early – makes later checks easier
        url = absolute_url(href)

        # --------------------------------------------------------------
        # Direct file extensions (pdf, zip, etc.)
        if url.lower().endswith(EXTENSIONS):
            # Guess the type from the URL path if possible
            if "/agenda/" in url.lower() or "/viewfile/agenda/" in url.lower():
                ftype = "agenda"
            elif "/minutes/" in url.lower() or "/viewfile/minutes/" in url.lower():
                ftype = "minutes"
            elif "/packet/" in url.lower() or "/viewfile/packet/" in url.lower():
                ftype = "packet"
            else:
                ftype = "other"
            files.append((url, ftype))
            continue

        # --------------------------------------------------------------
        #  ViewFile endpoints – agenda, minutes, packet
        # Strip any query string for the path‑based checks
        clean_path = url.split("?")[0].lower()

        if "/viewfile/agenda/" in clean_path:
            # If the query string contains “packet=true” we treat it as a packet
            if "packet=true" in url.lower():
                ftype = "packet"
            else:
                ftype = "agenda"
            files.append((url, ftype))

        elif "/viewfile/minutes/" in clean_path:
            files.append((url, "minutes"))

        elif "/viewfile/packet/" in clean_path:
            files.append((url, "packet"))

        # --------------------------------------------------------------
        # Anything else that looks like a file (rare cases)
    # --------------------------------------------------------------

    # De‑duplicate while preserving order
    seen: Set[Tuple[str, str]] = set()
    uniq: List[Tuple[str, str]] = []
    for pair in files:
        if pair not in seen:
            uniq.append(pair)
            seen.add(pair)
    return uniq


def download(url: str, dst: Path):
    """Stream‑download *url* into *dst* (creates parent directories)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=30) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)


def build_filename(date_str: str, ftype: str, url: str) -> str:
    """
    Construct a clear filename:
        <MMDDYYYY>_<type><original‑extension>

    If the date could not be parsed we fall back to the meeting ID (passed in
    *date_str* as that fallback) so the file still gets a deterministic name.
    """
    ext = Path(url).suffix  # includes the dot, e.g. ".pdf"
    # Guard against empty extensions – default to .pdf
    if not ext:
        ext = ".pdf"
    return f"{date_str}_{ftype}{ext}"


def scrape_year(year: int, out_root: Path):
    """Scrape agenda, minutes, and packet files for a given *year*."""
    print(f"\n=== Scraping year {year} ===")
    list_url = LIST_URL_TMPL.format(year=year)
    list_html = fetch(list_url)

    meeting_ids = extract_meeting_ids(list_html)
    if not meeting_ids:
        print(f"⚠️  No meetings found for {year}")
        return

    year_dir = out_root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    for meeting_id in tqdm(meeting_ids, desc=f"{year} meetings"):
        meeting_url = f"{BASE_URL}/AgendaCenter/26/{meeting_id}?MOBILE=ON&year={year}"
        try:
            meeting_html = fetch(meeting_url)
        except Exception as exc:
            print(f"[!] Could not load meeting page {meeting_id}: {exc}")
            continue

        # ------------------------------------------------------------------
        # Determine the date string for this meeting (MMDDYYYY).  If parsing fails,
        # we simply use the meeting ID as a fallback so filenames remain unique.
        date_str = parse_meeting_date(meeting_html)
        if not date_str:
            date_str = f"id{meeting_id}"   # fallback identifier

        # ------------------------------------------------------------------
        # Gather every downloadable file on the page
        file_links = extract_file_links(meeting_html)

        for file_url, ftype in file_links:
            filename = build_filename(date_str, ftype, file_url)
            dst = year_dir / filename

            if dst.exists():
                # Already have it – skip
                continue

            try:
                download(file_url, dst)
                time.sleep(0.5)               # be polite to the server
                print(f"Saved: {dst.relative_to(out_root)}")
            except Exception as exc:
                print(f"[!] Failed to download {file_url}: {exc}")


def main():
    out_root = Path("joplin_council_pdfs")
    for yr in range(2022, 2026):   # 2023, 2024, 2025
        scrape_year(yr, out_root)


if __name__ == "__main__":
    main()