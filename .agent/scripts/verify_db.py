import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

try:
    from src.db_manager import db
    from supabase import Client
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def check_database():
    print(f"Checking database connection...")
    
    if not db.client:
        print("❌ DBManager failed to initialize client. Check SUPABASE_URL and SUPABASE_KEY env vars.")
        return False

    try:
        # 1. Connection check (simple query)
        # We can try to select from a table we expect to exist or just check health if possible?
        # Supabase-py doesn't have a direct 'ping', but we can query 'profiles' or similar.
        print("✅ Client initialized.")
        
        # 2. Check Tables
        # Using RPC if available or simpler method?
        # Supabase postgrest doesn't easily expose information_schema via the JS/Python client usually 
        # unless permissions allow.
        # However, we can try to query each table we expect to exist with limit=0 to see if it errors.
        
        expected_tables = [
            "profiles",
            "projects",
            "analysis_history",
            "saved_queries",
            "custom_rules",
            "audit_log"
        ]
        
        missing_tables = []
        existing_tables = []
        
        print("\nVerifying tables:")
        for table in expected_tables:
            try:
                # Select 1 row just to check existence
                db.client.table(table).select("count", count="exact").limit(0).execute()
                print(f"  ✅ Table '{table}' found.")
                existing_tables.append(table)
            except Exception as e:
                # If error contains "relation ... does not exist"
                err_str = str(e).lower()
                if "does not exist" in err_str or "info" in err_str: # API might return 404
                     print(f"  ❌ Table '{table}' NOT found or not accessible.")
                     missing_tables.append(table)
                else:
                     print(f"  ⚠️ Error checking '{table}': {e}")
                     # allow it might be permission issue but likely table exists?
                     # assume missing for safety if strictly verifying schema
                     missing_tables.append(table)

        print("\n" + "="*40)
        if not missing_tables:
            print("🎉 ALL CHECKS PASSED: Database schema is correct.")
            return True
        else:
            print(f"❌ ISSUES FOUND: Missing {len(missing_tables)} tables.")
            print("Run 'database/supabase_schema.sql' in your Supabase SQL Editor.")
            return False

    except Exception as e:
        print(f"❌ Unexpected error during verification: {e}")
        return False

if __name__ == "__main__":
    success = check_database()
    sys.exit(0 if success else 1)
