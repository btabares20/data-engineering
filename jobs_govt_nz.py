import requests
from bs4 import BeautifulSoup

BASE_URL = "https://jobs.govt.nz"
DATA_DIR = "./data"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
}

BODY = [
    ("in_version", ""),
    ("in_sessionid", ""),
    ("in_graphic", ""),
    ("javaProxyUrl", ""),
    ("in_param", ""),
    ("in_organid", "16563"),
    ("in_others", ""),
    ("in_others", ""),
    ("in_orderby", "dateinput desc"),
    ("in_skills", ""),
    ("in_location", ""),
    ("in_others", ""),
    ("in_multi01", ""),
    ("in_multi01_id", "1802"),
    ("in_searchBut", ""),
]

response = requests.post(
    url=BASE_URL+"/jobtools/jncustomsearch.searchResults",
    headers=HEADERS,
    data=BODY,
)
all_jobs=[]
parser = BeautifulSoup(response.text, "html.parser")
for tr in parser.find_all('tr'):
    title_td = tr.find('td', class_='job_title')
    if not title_td:
        continue
    first_link = title_td.find('a')
    
    job = {
        "job_title_text": first_link.text.strip() if first_link else None,
        "job_url": first_link['href'] if first_link else None,
        "company": title_td.find('div', class_=None).text.replace('at ', '').strip() if title_td.find('div', class_=None) else None,
    }
    
    all_jobs.append(job)

job_links= []
for job in all_jobs:
    job_url: str = job.get('job_url')
    details_url_base = BASE_URL
    if not job_url.startswith("/jobs"):
        details_url_base += "/jobtools/"
    job_links.append(details_url_base + job_url)

job_details = []
for idx, job in enumerate(job_links):
    job_deets = requests.get(job)
    details_parser= BeautifulSoup(job_deets.text, 'html.parser')
    with open(f'{DATA_DIR}/{all_jobs[idx]['job_title_text'].replace('/','_')}.html','w+') as html_file:
        html_file.write(details_parser.prettify())
    #details_table = details_parser.find('div', class_="job_details")
    #job_details.append(details_table)
    
