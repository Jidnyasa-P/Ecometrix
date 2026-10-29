from __future__ import annotations
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def session() -> requests.Session:
    """HTTP session with retries and an identifying User-Agent (required by Nominatim and Overpass etiquette)."""
    s = requests.Session()
    retry = Retry(total=5, backoff_factor=2.0, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET", "POST"]))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    contact = os.environ.get("ECOMETRIX_CONTACT", "https://github.com/ecometrix/ecometrix")
    s.headers.update({"User-Agent": f"ecometrix-pipeline/0.4 (+{contact})"})
    return s
