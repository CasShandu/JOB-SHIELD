import sqlite3

DB = "jobshield.db"

sample_jobs = [
    ("ShopRite", "Cashier", 1, "cash handling,customer service", "Johannesburg"),
    ("FNB Bank", "Bank Teller", 2, "customer service,finance,cash management", "Pretoria"),
    ("Pick n Pay", "Store Manager", 3, "team leadership,inventory,retail management", "Durban"),
    ("TechCo", "Junior Software Developer", 1, "python,html,css,flask", "Cape Town"),
    ("TransNet", "Driver", 2, "transportation,communication,time management", "Soweto")
]

conn = sqlite3.connect(DB)
cur = conn.cursor()
for job in sample_jobs:
    cur.execute("INSERT INTO employers (company,title,min_experience,skills,location) VALUES (?,?,?,?,?)", job)

conn.commit()
conn.close()
print("Inserted sample job listings into jobshield.db")
