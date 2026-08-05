from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class JobsGovtClient:
    def __init__(self, base_url: str, headers: dict, body: dict) -> None:
        self.base_url = base_url
        self.headers = headers
        self.body = body
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=2,
            allowed_methods=["GET"],
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry)

        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_listing_page(self, page: str) -> str:
        self.body["in_pg"] = page
        response = self.session.post(
            url=self.base_url+"/jobtools/jncustomsearch.searchResults",
            headers=self.headers,
            data=self.body
        )
        response.raise_for_status()
        return response.text

    def get_job_page(self, url) -> str:
        base = self.base_url
        if not url.startswith("/jobs"):
            base += "/jobtools/"
        response = self.session.get(base+url, timeout=30)
        response.raise_for_status()
        return response.text

class TradeMeClient:
    def __init__(self, url: str, headers: dict, params: dict) -> None:
        self.url = url
        self.headers = headers
        self.base_params= params 
        self.session = requests.Session()

    def get_listings(self, page: int, region)->dict:
        self.headers["canonical_path"]= f"/jobs/{region}"
        self.session.headers.update(self.headers) 
        params = self.base_params | {
            "page": page,
            "rsqid": "f284381cd41a4b8c92dad9f7464e15d3-001",
        }
        response = self.session.get(
            url=self.url,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

