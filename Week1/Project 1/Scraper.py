import re
import requests
from bs4 import BeautifulSoup
import sqlite3
import csv
import schedule
import time
from datetime import datetime

headers={"User-Agent":"Mozilla/5.0"}

LIMIT=100

db=sqlite3.connect("jobs.db",check_same_thread=False)

cursor=db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS jobs(
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
company TEXT,
location TEXT,
salary TEXT,
tags TEXT,
posted_at TEXT,
created_at TEXT,
UNIQUE(title,company,location)
)
""")

db.commit()

def export_csv():

    rows=cursor.execute(
        "SELECT title,company,location,salary,tags,posted_at,created_at FROM jobs"
    ).fetchall()

    with open(
        "dashboard.csv",
        "w",
        newline="",
        encoding="utf8"
    ) as f:

        writer=csv.writer(f)

        writer.writerow([
            "Title",
            "Company",
            "Location",
            "Salary",
            "Tags",
            "Posted",
            "Created"
        ])

        writer.writerows(rows)

    print("CSV Updated")

def clean(text):
    return re.sub(r"[^A-Za-z0-9 ,.\-/()\[\]&+#@%']","",text).strip()

def scrape():

    print("Running:",datetime.now())

    try:
        response=requests.get(
            "https://remoteok.com/?&action=get_jobs&premium=0&offset=",
            headers=headers,
            timeout=15
        )
        response.raise_for_status()
        response.encoding="utf-8"

    except requests.RequestException as e:
        print("Request failed:",e)
        return

    soup=BeautifulSoup(
        response.text,
        "html.parser"
    )

    jobs=soup.select("tr.job")

    count=0

    for job in jobs:

        if count>=LIMIT:
            break

        title=job.select_one('h2[itemprop="title"]')

        if not title:
            continue

        company=job.select_one('h3[itemprop="name"]')

        location=job.select_one(".location")

        salary=job.select_one(".salary")

        time_tag=job.select_one("td.time time")

        posted_at=time_tag["datetime"] if time_tag and time_tag.has_attr("datetime") else "N/A"

        tags=[]

        for tag in job.select("td.tags h3"):

            text=tag.get_text(strip=True)

            if text:
                tags.append(text)

        title=clean(title.get_text(strip=True))

        company=clean(company.get_text(strip=True)) if company else "N/A"

        location=clean(location.get_text(strip=True)) if location else "N/A"
        salary=clean(salary.get_text(strip=True)) if salary else "N/A"

        tags=", ".join(tags) if tags else "N/A"

        try:

            cursor.execute(
                "INSERT INTO jobs(title,company,location,salary,tags,posted_at,created_at) VALUES(?,?,?,?,?,?,?)",
                (
                    title,
                    company,
                    location,
                    salary,
                    tags,                    
                    posted_at,
                    datetime.now().isoformat()
                )
            )

            count+=1            

        except sqlite3.IntegrityError:
            pass

        except sqlite3.Error as e:
            print("DB error:",e)

    db.commit()

    export_csv()
    
    print("Output stored to Database and CSV file. Format will be\n title | company | location | salary | tags | posted_at | created_at \n Database and CSV file will be updated every 12 hours.")
    print("Inserted:",count)


scrape()

schedule.every(12).hours.do(scrape)

while True:

    schedule.run_pending()

    time.sleep(60)