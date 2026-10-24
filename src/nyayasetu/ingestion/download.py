"""Download the official bare-act PDFs into data/raw/.

Each act has several sources, tried in order. The first that returns a real PDF wins,
and which source was used is recorded in data/raw/sources.json (provenance).

Run:  python -m nyayasetu.ingestion.download
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# This file lives at src/nyayasetu/ingestion/download.py -> project root is 3 levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "sources.json"

# Sources per act, in order of preference. Recorded in plan.md.
SOURCES = {
    "bns": [
        ("indiacode", "https://www.indiacode.nic.in/bitstream/123456789/20062/1/a202345.pdf"),
        ("prs_gazette", "https://prsindia.org/files/bills_acts/bills_parliament/2023/The%20Bharatiya%20Nyaya%20Sanhita,%202023.pdf"),
    ],
    "bnss": [
        ("indiacode", "https://indiacode.nic.in/bitstream/123456789/20099/3/A2023-46.pdf"),
        ("prs_gazette", "https://prsindia.org/files/bills_acts/bills_parliament/2023/The%20Bharatiya%20Nagarik%20Suraksha%20Sanhita,%202023.pdf"),
    ],
    "bsa": [
        ("indiacode", "https://www.indiacode.nic.in/bitstream/123456789/20063/1/aa202347.pdf"),
        ("prs_gazette", "https://prsindia.org/files/bills_acts/acts_parliament/2023/The%20Bharatiya%20Sakshya%20Bill,%202023.pdf"),
    ],
}

# Some servers reject requests that don't look like a browser.
HEADERS = {"User-Agent": "Mozilla/5.0 (NyayaSetu research project)"}


def make_session() -> requests.Session:
    """A session that automatically retries temporary server errors with backoff."""
    retry = Retry(
        total=3,                                  # a few retries per source, then fall back
        backoff_factor=2,                         # waits roughly 2s, 4s, 8s between tries
        status_forcelist=[500, 502, 503, 504],    # retry only temporary server errors
        allowed_methods=["GET"],
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(HEADERS)
    return session


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def fetch_pdf(session: requests.Session, url: str) -> bytes:
    """Return PDF bytes from url, or raise if the response is an error or not a PDF."""
    response = session.get(url, timeout=180)
    response.raise_for_status()
    # Every real PDF file starts with the bytes "%PDF". If not, we got an error page.
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF (Content-Type: {response.headers.get('Content-Type')})")
    return response.content


def download(session: requests.Session, name: str, sources: list, manifest: dict) -> None:
    """Try each source for one act until one works. Skips if the file already exists."""
    dest = RAW_DIR / f"{name}.pdf"
    if dest.exists():
        used = manifest.get(name, {}).get("source", "unknown (added manually?)")
        print(f"[skip] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB, source: {used})")
        return

    for source_name, url in sources:
        print(f"[get]  {name} from {source_name}")
        try:
            content = fetch_pdf(session, url)
        except Exception as exc:
            print(f"[miss] {name} from {source_name}: {type(exc).__name__}")
            continue  # try the next source
        dest.write_bytes(content)
        manifest[name] = {
            "source": source_name,
            "url": url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(content),
        }
        print(f"[ok]   saved {dest.name} from {source_name} ({len(content) / 1e6:.1f} MB)")
        return

    raise RuntimeError(f"all sources failed for {name}")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()
    manifest = load_manifest()
    failed = []
    for name, sources in SOURCES.items():
        try:
            download(session, name, sources, manifest)
        except Exception as exc:  # keep going so one bad act doesn't block the others
            print(f"[fail] {exc}")
            failed.append(name)

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if failed:
        print(f"\nFailed: {', '.join(failed)}. Run again later (finished files are skipped).")
        sys.exit(1)
    print(f"\nAll acts downloaded. Provenance recorded in {MANIFEST.name}.")


if __name__ == "__main__":
    main()
