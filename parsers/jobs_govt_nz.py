from bs4 import BeautifulSoup
import re
import json

from db.engine import db_context
from db.models import Raw

source_name = 'jobs_govt_nz'

def main():
    jobs =[]
    with db_context() as db:
        raws = db.query(Raw).filter(Raw.parsed == False, Raw.source == "jobs_govt_nz").all()
        for raw in raws:
            data = raw.raw
            soup = BeautifulSoup(str(data), "html.parser")
            details_table = soup.select_one("div[class^='job-details']")

            job_desc_raw = soup.find("div", class_="jobDesc")
            job_desc = ""
            if job_desc_raw:
                job_desc = re.sub(r'\n+', r'\n',(job_desc_raw.text).strip()) # re.sub removes extra \n (s)

            job = { 
                   "job_title": raw.job_title,
                   "job_url": raw.job_url,
                   "raw_id": str(raw.id)
            }
            if details_table:
                for row in details_table.find_all('tr'):
                    first_td = row.find_all('td')[0].get_text(strip=True)
                    second_td = row.find_all('td')[1].get_text(strip=True)
                    if any(keyword in first_td for keyword in ("File links", "Attachment")):
                        file_td = row.find_all('td')[1]
                        if file_td:
                            file_link_a = file_td.find('a')
                            second_td = file_link_a["href"] if file_link_a else None
                        else: 
                            second_td = None 
                    job[first_td.lower().replace(":","").replace(" ","_")] = second_td
            jobs.append(job)

        with open('jobs_govt_nz_parsed.json', 'w+') as file:
            for job in jobs:
                file.write(json.dumps(job) + "\n")

if __name__ == "__main__":
    main()
