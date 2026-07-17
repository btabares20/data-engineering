from bs4 import BeautifulSoup
import re
import json

from db.engine import db_context
from db.models import Raw

source_name = 'jobs_govt_nz'

def main():
    jobs =[]
    with db_context() as db:
        raws = db.query(Raw).filter(Raw.parsed == False).all()
        for raw in raws:
            data = raw.raw_html
            soup = BeautifulSoup(str(data), "html.parser")
            details_table = soup.select_one("div[class^='job-details']")
            raw_title = soup.find('title')
            job_title = ""
            if raw_title:
                job_title = raw_title.text.split('|')[0].strip()

            job_desc_raw = soup.find("div", class_="jobDesc")
            job_desc = ""
            if job_desc_raw:
                job_desc = re.sub(r'\n+', r'\n',(job_desc_raw.text).strip()) # re.sub removes extra \n (s)

            job = { 
                   "job_title": job_title,
                   "raw_id": str(raw.id)
            }
            if details_table:
                for row in details_table.find_all('tr'):
                    first_td = row.find_all('td')[0].get_text(strip=True)
                    second_td = row.find_all('td')[1].get_text(strip=True)
                    job[first_td.lower().replace(":","").replace(" ","_")] = second_td
            jobs.append(job)

        with open('parsed.json', 'w+') as file:
            for job in jobs:
                file.write(json.dumps(job) + "\n")

if __name__ == "__main__":
    main()
