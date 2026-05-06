from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential


DEFAULT_HEADERS = {
    "User-Agent": "paper-daily/0.1 (+https://github.com/)",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
}


def client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS)


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def get_text(url: str, params: dict | None = None) -> str:
    with client() as http:
        response = http.get(url, params=params)
        response.raise_for_status()
        return response.text


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
def get_json(url: str, params: dict | None = None) -> dict:
    with client() as http:
        response = http.get(url, params=params)
        response.raise_for_status()
        return response.json()
