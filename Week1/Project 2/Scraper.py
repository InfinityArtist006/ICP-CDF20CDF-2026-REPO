import requests
import sqlite3
import csv
import os
import time
from datetime import datetime

API_URL="https://api.spaceflightnewsapi.net/v4/articles/"
DB_NAME="articles.db"
CHECKPOINT="last_article_id.txt"
LOG_FILE="logs.txt"
CSV_FILE="articles.csv"

def log(msg):
    text=str(datetime.now())+" | "+msg
    print(text)
    with open(LOG_FILE,"a",encoding="utf8") as f:
        f.write(text+"\n")

def db():
    conn=sqlite3.connect(DB_NAME)
    cur=conn.cursor()
    cur.execute(""" CREATE TABLE IF NOT EXISTS articles(id INTEGER PRIMARY KEY AUTOINCREMENT,article_id INTEGER UNIQUE,title TEXT,published_date TEXT,source TEXT,url TEXT,summary TEXT,ingested_at TEXT)""")
    conn.commit()
    return conn

def checkpoint():
    if not os.path.exists(CHECKPOINT):
        return 0
    try:
        with open(CHECKPOINT,"r") as f:
            return int(f.read().strip())
    except:
        return 0

def save_checkpoint(x):
    with open(CHECKPOINT,"w") as f:
        f.write(str(x))

def fetch(url):
    for i in range(3):
        try:
            r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=30)
            if r.status_code==200:
                return r.json()
        except:
            pass
        log("retry "+str(i+1))
        time.sleep(5)
    return None

def export_csv(conn):
    cur=conn.cursor()
    cur.execute("""SELECT article_id,title,published_date,source,url,summary,ingested_at FROM articles ORDER BY article_id DESC""")
    rows=cur.fetchall()
    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf8"
    ) as f:
        writer=csv.writer(f)
        writer.writerow(["ArticleID","Title","PublishedDate","Source","URL","Summary","IngestedAt"])
        writer.writerows(rows)

def stats(conn):
    cur=conn.cursor()
    print("\nTop Sources\n")
    cur.execute("""SELECT source,count(*) FROM articles GROUP BY source ORDER BY count(*) DESC LIMIT 10 """)
    rows=cur.fetchall()
    for i in rows:
        print(i[0],":",i[1])

def main():
    log("started")
    conn=db()
    cur=conn.cursor()
    last_id=checkpoint()
    newest=last_id
    inserted=0
    limit=100
    seen=set()
    url=API_URL

    while url and inserted<limit:
        data=fetch(url)
        if not data:
            break
        stop=False
        for article in data["results"]:
            aid=article["id"]
            
            if aid<=last_id:
                stop=True
                break
            if inserted>=limit:
                break
            if aid in seen:
                continue

            seen.add(aid)

            title=article.get("title","").strip()
            published=article.get("published_at","")
            source=article.get("news_site","")
            article_url=article.get("url","")
            summary=article.get("summary","").replace("\n"," ").strip()
            cur.execute("SELECT 1 FROM articles WHERE article_id=?",(aid,))

            if cur.fetchone():
                continue
            
            cur.execute(""" INSERT OR IGNORE INTO articles(article_id,title,published_date,source,url,summary,ingested_at) VALUES(?,?,?,?,?,?,?)""",
            (aid,title,published,source,article_url,summary,datetime.now().isoformat()))
            conn.commit()

            inserted+=1
            if aid>newest:
                newest=aid

            save_checkpoint(newest)
            print(title,"|",source)

        if stop:
            break
        url=data.get("next")
    export_csv(conn)
    stats(conn)
    conn.close()
    log("inserted "+str(inserted))

main()