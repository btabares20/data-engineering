import json
import sqlite3

with sqlite3.connect("staging.db") as conn:
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS staging (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title TEXT,
        employer TEXT,
        location TEXT,
        position_type TEXT,
        category TEXT,
        date_listed TEXT,
        salary_range TEXT,
        closing_date TEXT,
        external_reference TEXT UNIQUE,
        attachment TEXT,
        file_links TEXT,
        website TEXT
    )
    """)

    with open('parsed.json', 'r') as file:
        for line in file:
            data = json.loads(line.strip())
            data_to_insert = (
                data["job_title"],
                data["employer"],
                data["location"],
                data["position_type"],
                data["category"],
                data["date_listed"],
                data["salary_range"],
                data["closing_date"],
                data["reference"],
                data["attachment"],
                data["file_links"],
                data["website"],
            )
            cursor.execute("""
                INSERT INTO staging (
                    job_title, employer, location, position_type, category,
                    date_listed, salary_range, closing_date,
                    external_reference, attachment, file_links, website
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(external_reference)
                DO UPDATE SET
                    job_title = excluded.job_title,
                    employer = excluded.employer,
                    location = excluded.location,
                    position_type = excluded.position_type,
                    category = excluded.category,
                    date_listed = excluded.date_listed,
                    salary_range = excluded.salary_range,
                    closing_date = excluded.closing_date,
                    attachment = excluded.attachment,
                    file_links = excluded.file_links,
                    website = excluded.website
            """, data_to_insert)            
