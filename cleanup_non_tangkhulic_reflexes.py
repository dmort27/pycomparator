#!/usr/bin/env python3
"""
Remove non-Tangkhulic reflexes from Tangkhulic protoforms.

This script removes records from reflex_of where:
- plangid = 17 (Proto-Tangkhulic)
- But the refid points to a reflex whose langid is NOT a descendant of 17

In other words, it removes "reflexes" that claim to be reflexes of 
Proto-Tangkhulic forms but are from non-Tangkhulic languages.
"""

import sqlite3
import sys

DATABASE = "db/borderlands.sqlite3"


def cleanup_non_tangkhulic_reflexes(db_path: str = DATABASE, dry_run: bool = True) -> int:
    """
    Remove non-Tangkhulic reflexes from Proto-Tangkhulic protoforms.
    
    Args:
        db_path: Path to the database
        dry_run: If True, only report what would be deleted without actually deleting
        
    Returns:
        Number of records deleted (or that would be deleted in dry_run mode)
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get the list of Tangkhulic language IDs (descendants of plangid=17)
    c.execute("SELECT langid FROM descendant_of WHERE plangid = 17")
    tangkhulic_langids = {row[0] for row in c.fetchall()}
    
    print(f"Tangkhulic language IDs: {sorted(tangkhulic_langids)}")
    
    # Find reflex_of records where:
    # - plangid = 17 (Proto-Tangkhulic)
    # - refid points to a reflex whose langid is NOT in tangkhulic_langids
    c.execute("""
        SELECT ro.refid, ro.prefid, ro.plangid, r.langid, r.form, r.gloss, ln.name
        FROM reflex_of ro
        JOIN reflexes r ON ro.refid = r.refid
        JOIN langnames ln ON r.langid = ln.langid
        WHERE ro.plangid = 17
          AND r.langid NOT IN (SELECT langid FROM descendant_of WHERE plangid = 17)
    """)
    
    records_to_delete = c.fetchall()
    
    print(f"\nFound {len(records_to_delete)} non-Tangkhulic reflexes linked to Proto-Tangkhulic protoforms")
    
    if records_to_delete:
        print("\nSample of records to delete:")
        for i, (refid, prefid, plangid, langid, form, gloss, langname) in enumerate(records_to_delete[:20]):
            print(f"  refid={refid}, prefid={prefid}, langid={langid} ({langname}), form='{form}', gloss='{gloss}'")
        if len(records_to_delete) > 20:
            print(f"  ... and {len(records_to_delete) - 20} more")
    
    if dry_run:
        print("\n[DRY RUN] No records were deleted. Run with --execute to actually delete.")
    else:
        # Delete the records
        c.execute("""
            DELETE FROM reflex_of
            WHERE plangid = 17
              AND refid IN (
                  SELECT r.refid
                  FROM reflexes r
                  WHERE r.langid NOT IN (SELECT langid FROM descendant_of WHERE plangid = 17)
              )
        """)
        deleted_count = c.rowcount
        conn.commit()
        print(f"\nDeleted {deleted_count} records from reflex_of")
    
    conn.close()
    return len(records_to_delete)


if __name__ == "__main__":
    db_path = DATABASE
    dry_run = True
    
    for arg in sys.argv[1:]:
        if arg == "--execute":
            dry_run = False
        elif arg.startswith("--db="):
            db_path = arg.split("=", 1)[1]
        elif arg in ("-h", "--help"):
            print("Usage: cleanup_non_tangkhulic_reflexes.py [--execute] [--db=PATH]")
            print()
            print("Options:")
            print("  --execute    Actually delete records (default is dry run)")
            print("  --db=PATH    Path to database (default: db/borderlands.sqlite3)")
            sys.exit(0)
    
    cleanup_non_tangkhulic_reflexes(db_path, dry_run)
