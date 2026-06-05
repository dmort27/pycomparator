#!/usr/bin/env python3
"""
Populate the ipaform column for all existing reflexes in the database.

This script batch-updates all reflexes with their normalized IPA forms.
Run this once after adding the ipaform column to the schema.
"""

import sqlite3
import sys
from ipa_normalize import normalize_to_ipa

DATABASE = "db/borderlands.sqlite3"
BATCH_SIZE = 1000


def populate_ipaforms(db_path: str = DATABASE) -> None:
    """Populate ipaform for all reflexes in the database."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get total count
    c.execute("SELECT COUNT(*) FROM reflexes WHERE ipaform IS NULL OR ipaform = ''")
    total_null = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM reflexes")
    total = c.fetchone()[0]
    
    print(f"Total reflexes: {total}")
    print(f"Reflexes needing ipaform: {total_null}")
    
    if total_null == 0:
        print("All reflexes already have ipaform populated.")
        return
    
    # Fetch all reflexes that need updating
    c.execute("SELECT refid, form FROM reflexes")
    rows = c.fetchall()
    
    # Compute ipaform for each
    updates = []
    for refid, form in rows:
        ipaform = normalize_to_ipa(form) if form else ""
        updates.append((ipaform, refid))
    
    # Batch update
    print(f"Updating {len(updates)} reflexes...")
    for i in range(0, len(updates), BATCH_SIZE):
        batch = updates[i:i + BATCH_SIZE]
        c.executemany("UPDATE reflexes SET ipaform = ? WHERE refid = ?", batch)
        conn.commit()
        print(f"  Updated {min(i + BATCH_SIZE, len(updates))}/{len(updates)}")
    
    print("Done!")
    
    # Verify
    c.execute("SELECT COUNT(*) FROM reflexes WHERE ipaform IS NULL OR ipaform = ''")
    remaining = c.fetchone()[0]
    print(f"Reflexes still without ipaform: {remaining}")
    
    # Show some examples
    print("\nSample transformations:")
    c.execute("SELECT form, ipaform FROM reflexes WHERE form != ipaform LIMIT 10")
    for form, ipaform in c.fetchall():
        print(f"  {form} → {ipaform}")
    
    conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else DATABASE
    populate_ipaforms(db_path)
