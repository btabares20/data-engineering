from bs4 import BeautifulSoup
import re
import os
import json

source_name = 'jobs_govt_nz'
base_dir = f'./raw_data/{source_name}/'
files_list = os.listdir(base_dir)

jobs =[]
for file in files_list:
    with open(os.path.join(base_dir,file), 'r') as f:
        data = f.read()


    soup = BeautifulSoup(data, "html.parser")
    details_table = soup.select_one("div[class^='job-details']")
    raw_title = soup.find('title')
    job_title = ""
    if raw_title:
        job_title = raw_title.text.split('|')[0].strip()

    job_desc_raw = soup.find("div", class_="jobDesc")
    job_desc = ""
    if job_desc_raw:
        job_desc = re.sub(r'\n+', r'\n',(job_desc_raw.text).strip()) # re.sub removes extra \n (s)

    job = { "job_title": job_title }
    if details_table:
        for row in details_table.find_all('tr'):
            first_td = row.find_all('td')[0].get_text(strip=True)
            second_td = row.find_all('td')[1].get_text(strip=True)
            job[first_td.lower().replace(":","").replace(" ","_")] = second_td
        jobs.append(job)

with open('parsed.json', 'w+') as file:
    for job in jobs:
        file.write(json.dumps(job) + "\n")
