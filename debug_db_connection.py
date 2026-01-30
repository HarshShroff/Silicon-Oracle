#!/usr/bin/env python3
"""
Database Connection Test Script
Run this to test your Supabase connection string
"""

import os
import sys

def test_connection():
    """Test database connection with detailed error reporting."""

    # Get DATABASE_URL from environment
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("\nTo test, run:")
        print('  export DATABASE_URL="postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres"')
        print('  python test_db_connection.py')
        return False

    print(f"🔍 Testing connection to: {database_url[:50]}...")

    try:
        # Try importing psycopg2 (PostgreSQL driver)
        try:
            import psycopg2
            print("✅ psycopg2 installed")
        except ImportError:
            print("❌ psycopg2 not installed")
            print("   Run: pip install psycopg2-binary")
            return False

        # Parse connection string
        print("\n📋 Connection Details:")
        if database_url.startswith("postgresql://"):
            parts = database_url.replace("postgresql://", "").split("@")
            if len(parts) == 2:
                user_pass = parts[0]
                host_db = parts[1]
                print(f"   User: {user_pass.split(':')[0]}")
                print(f"   Host: {host_db.split(':')[0]}")
                print(f"   Port: {host_db.split(':')[1].split('/')[0]}")
                print(f"   Database: {host_db.split('/')[-1]}")

        # Attempt connection
        print("\n🔌 Attempting connection...")
        conn = psycopg2.connect(database_url)
        print("✅ Connection successful!")

        # Test query
        print("\n📊 Testing query...")
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ PostgreSQL version: {version[:50]}...")

        # Check if tables exist
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()

        if tables:
            print(f"\n✅ Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("\n⚠️  No tables found (this is OK for first run)")
            print("   Tables will be created automatically on first app startup")

        cursor.close()
        conn.close()

        print("\n✅ ALL TESTS PASSED!")
        print("Your database connection is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ CONNECTION FAILED!")
        print(f"Error: {str(e)}")
        print("\n🔧 Common fixes:")
        print("1. Check password in connection string")
        print("2. Ensure connection string ends with /postgres")
        print("3. Verify Supabase project is active")
        print("4. Check if SSL is required (add ?sslmode=require)")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
