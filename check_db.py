import sqlite3
import json
from pathlib import Path

db_path = Path("c:/dev/temp_acento/data/classifications.db")

if not db_path.exists():
    print("Database file still not created or missing.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
    SELECT filename, lender, waiver_type, confidence_score, status, raw_llm_response 
    FROM email_classifications
    ORDER BY created_at DESC
""")

rows = cursor.fetchall()
conn.close()

if not rows:
    print("No records found in database.")
else:
    print(f"Total processed classifications in DB: {len(rows)}\n")
    print("-" * 80)
    for row in rows:
        filename, lender, waiver_type, confidence, status, reasoning = row
        print(f"File:     {filename}")
        print(f"AI Result: [Lender: {lender}] | [Waiver: {waiver_type}]")
        print(f"Score:    {confidence:.2f}")
        print(f"Reason:   {reasoning[:150]}...")
        print("-" * 80)
