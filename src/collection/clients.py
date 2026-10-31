from urllib.parse import urljoin, quote
import requests
from collection.request_policy import source_policy

class JobsGovtClient:
    def __init__(self, base_url: str, headers: dict, body: dict) -> None:
        self.base_url = base_url
        self.headers = headers
        self.body = body
        self.session = requests.Session()
        self.policy = source_policy("jobs_govt_nz")

    def _request(self, method, url, **kwargs):
        return self.policy.request(
            self.session, method, url,
            retry_exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
            **kwargs,
        )

    def get_listing_page(self, page: str) -> str:
        self.body["in_pg"] = page
        response = self._request(
            "POST",
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
        response = self._request("GET", urljoin(base + "/", url))
        response.raise_for_status()
        return response.text

class TradeMeClient:
    def __init__(self, url: str, headers: dict, params: dict) -> None:
        self.url = url
        self.headers = headers
        self.base_params= params 
        self.session = requests.Session()
        self.policy = source_policy("trade_me")

    def get_listings(self, page: int, region)->dict:
        params = self.base_params | {
            "page": page,
            "canonical_path": f"/jobs/{region}",
        }
        response = self.policy.request(
            self.session, "GET",
            url=self.url,
            params=params,
            headers=self.headers,
            retry_exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        )
        response.raise_for_status()
        return response.json()

    def get_job_details(self, listing_id):
        url = "https://api.trademe.co.nz/v1/Listings/" + quote(str(listing_id), safe="") + ".json"
        return self.policy.request(
            self.session, "GET", url, headers=self.headers,
            retry_exceptions=(requests.exceptions.Timeout, requests.exceptions.ConnectionError),
        ).json()
