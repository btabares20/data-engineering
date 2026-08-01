from abc import ABC, abstractmethod

import requests

class Client(ABC):
    @abstractmethod
    def get_listing_page(self, page)->str:
        ...

    @abstractmethod
    def get_job_page(self, url)->str:
        ...

class JobsGovtClient(Client):
    def __init__(self, base_url: str, headers: dict, body: dict) -> None:
        self.base_url = base_url
        self.headers = headers
        self.body = body
        self.session = requests.Session()

    def get_listing_page(self, page: str) -> str:
        body = self.body["page"] = page
        response = self.session.post(
            url=self.base_url+"/jobtools/jncustomsearch.searchResults",
            headers=self.headers,
            data=self.body
        )
        response.raise_for_status()
        return response.text

    def get_job_page(self, url) -> str:
        response = self.session.get(url)
        response.raise_for_status()
        return response.text

