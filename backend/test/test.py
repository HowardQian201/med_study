import os
from supabase import create_client, Client
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def get_supabase_client():
    """Create and return a Supabase client."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_ANON_KEY environment variables")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def test_insert():
    """Test INSERT operation."""
    print("=== Testing INSERT ===")
    supabase = get_supabase_client()
    
    user_data = {
        "id": 2,
        "test_str": "Test User 2",
    }
    
    result = supabase.table('test_table').insert(user_data).execute()
    print(f"Inserted: {result.data}")
    return result.data

def test_select():
    """Test SELECT operations."""
    print("\n=== Testing SELECT ===")
    supabase = get_supabase_client()
    
    # Select all records
    print("1. Select all records:")
    result = supabase.table('test_table').select("*").execute()
    print(f"All records: {result.data}")
    
    # Select specific columns
    print("\n2. Select specific columns:")
    result = supabase.table('test_table').select("id, test_str").execute()
    print(f"Specific columns: {result.data}")
    
    # Select with filter
    print("\n3. Select with filter:")
    result = supabase.table('test_table').select("*").eq('id', 2).execute()
    print(f"Filtered records: {result.data}")
    
    # Select with multiple filters
    print("\n4. Select with multiple filters:")
    result = supabase.table('test_table').select("*").neq('test_str', '').limit(5).execute()
    print(f"Multiple filters: {result.data}")
    
    return result.data

def test_update():
    """Test UPDATE operation."""
    print("\n=== Testing UPDATE ===")
    supabase = get_supabase_client()
    
    # Update specific record
    updated_data = {
        "test_str": "Updated Test User 2"
    }
    
    result = supabase.table('test_table').update(updated_data).eq('id', 2).execute()
    print(f"Updated: {result.data}")
    return result.data

def test_upsert():
    """Test UPSERT operation (insert or update if exists)."""
    print("\n=== Testing UPSERT ===")
    supabase = get_supabase_client()
    
    # This will update if id=2 exists, or insert if it doesn't
    upsert_data = {
        "id": 2,
        "test_str": "Upserted Test User 2"
    }
    
    result = supabase.table('test_table').upsert(upsert_data).execute()
    print(f"Upserted: {result.data}")
    
    # Insert a new record with upsert
    new_upsert_data = {
        "id": 3,
        "test_str": "New Test User 3"
    }
    
    result = supabase.table('test_table').upsert(new_upsert_data).execute()
    print(f"New upserted: {result.data}")
    
    return result.data

def test_delete():
    """Test DELETE operation."""
    print("\n=== Testing DELETE ===")
    supabase = get_supabase_client()
    
    # Delete specific record
    result = supabase.table('test_table').delete().eq('id', 3).execute()
    print(f"Deleted: {result.data}")
    return result.data

def test_advanced_queries():
    """Test advanced query operations."""
    print("\n=== Testing ADVANCED QUERIES ===")
    supabase = get_supabase_client()
    
    # Insert some test data first
    test_data = [
        {"id": 4, "test_str": "Alpha User"},
        {"id": 5, "test_str": "Beta User"},
        {"id": 6, "test_str": "Charlie User"}
    ]
    
    print("1. Inserting test data for advanced queries:")
    supabase.table('test_table').insert(test_data).execute()
    
    # Order by
    print("\n2. Order by test_str:")
    result = supabase.table('test_table').select("*").order('test_str').execute()
    print(f"Ordered: {result.data}")
    
    # Limit and offset
    print("\n3. Limit and offset:")
    result = supabase.table('test_table').select("*").limit(2).offset(1).execute()
    print(f"Limited: {result.data}")
    
    # Text search
    print("\n4. Text search (contains):")
    result = supabase.table('test_table').select("*").ilike('test_str', '%User%').execute()
    print(f"Text search: {result.data}")
    
    # Count
    print("\n5. Count records:")
    result = supabase.table('test_table').select("*", count="exact").execute()
    print(f"Count: {result.count}")
    
    return result.data

def cleanup_test_data():
    """Clean up test data."""
    print("\n=== CLEANUP ===")
    supabase = get_supabase_client()
    
    # Delete all test records (be careful with this in production!)
    result = supabase.table('test_table').delete().gte('id', 2).execute()
    print(f"Cleaned up records: {result.data}")
    return result.data

if __name__ == "__main__":
    print(f"Connecting to: {SUPABASE_URL}")
    
    try:
        # Run all test operations
        # test_insert()
        # test_select()
        # test_update()
        # test_upsert()
        # test_advanced_queries()
        # test_delete()
        
        # Show final state
        print("\n=== FINAL STATE ===")
        supabase = get_supabase_client()
        final_result = supabase.table('test_table').select("*").execute()
        print(f"Final records: {final_result.data}")
        
        # Uncomment the next line if you want to clean up all test data
        cleanup_test_data()
        
        print("\n✅ All operations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e).__name__}")
