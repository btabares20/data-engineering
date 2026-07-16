import requests
from bs4 import BeautifulSoup
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

BASE_URL = "https://jobs.govt.nz"
SOURCE_NAME = 'jobs_govt_nz'
DATA_DIR = f"./raw_data/{SOURCE_NAME}"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
}

BODY = {
    "in_version": "",
    "in_sessionid": "",
    "in_graphic": "",
    "javaProxyUrl": "",
    "in_param": "",
    "in_organid": "16563",
    "in_others": "",
    "in_orderby": "dateinput desc",
    "in_skills": "",
    "in_location": "",
    "in_multi01": "",
    "in_multi01_id": "1802",
    "in_searchBut": "",
    "in_pg": "0",
}
def main():
    page = "0"
    next_page = 1
    total_jobs = 0
    while True:
        logging.info(f"Fetching jobs from page # {next_page}")
        if total_jobs and int(page) >= int(total_jobs):
            break
        BODY['in_pg']=page
        response = requests.post(
            url=BASE_URL+"/jobtools/jncustomsearch.searchResults",
            headers=HEADERS,
            data=BODY,
        )
        page=str(next_page*20)
        next_page+=1

        all_jobs=[]
        parser = BeautifulSoup(response.text, "html.parser")
        if not total_jobs:
            total_jobs = parser.find("input",attrs={"name":"in_totalrows"})
            total_jobs = total_jobs.get("value") if total_jobs else 0
            logging.info(f"Found {total_jobs} jobs")

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
        # FIXME: This is redundant
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
            details_table = details_parser.select_one("div[class^='job-details']")
            job_reference = None
            if details_table:
                for row in details_table.find_all('tr'):
                    if "Reference" in row.find_all('td')[0].get_text(strip=True):
                        job_reference = row.find_all('td')[1].get_text(strip=True)
                        break
            filename = job_reference or all_jobs[idx]['job_title_text']
            job_filename = f'{DATA_DIR}/{filename.replace('/','_')}.html'
            logging.info(f"Downloading ref# {job_filename} - {all_jobs[idx]['job_title_text']}")
            #job_details.append(details_table)
            with open(job_filename,'w+') as html_file:
                html_file.write(details_parser.prettify())
if __name__ == "__main__":
    main()
