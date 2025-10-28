#!/usr/bin/env python3
# scripts/check_db.py - Check database connection and status
import sys
import os
import psycopg2
from urllib.parse import urlparse

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_database_connection():
    """Check if database connection is working"""
    
    db_url = "postgresql+psycopg2://schoolai2_user:StrongPassword123!@localhost/schoolai2rasa"
    parsed = urlparse(db_url)
    
    print("Database Connection Check")
    print("=" * 40)
    print(f"Host: {parsed.hostname}")
    print(f"Port: {parsed.port}")
    print(f"Database: {parsed.path.lstrip('/')}")
    print(f"User: {parsed.username}")
    print("-" * 40)
    
    try:
        # Try to connect
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password
        )
        
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Connection successful!")
        print(f"PostgreSQL version: {version[:50]}...")
        
        # Check if database is empty
        cursor.execute("""
            SELECT count(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        table_count = cursor.fetchone()[0]
        print(f"Tables in database: {table_count}")
        
        if table_count == 0:
            print("📝 Database is empty - ready for initial migration")
        else:
            print("📋 Existing tables found:")
            cursor.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            tables = cursor.fetchall()
            for table in tables:
                print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if PostgreSQL is running: sudo systemctl status postgresql")
        print("2. Verify database credentials in .env file")
        print("3. Ensure database and user exist:")
        print("   sudo -u postgres psql")
        print("   CREATE USER schooluser WITH PASSWORD 'schoolpass';")
        print("   CREATE DATABASE schooldb OWNER schooluser;")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    if check_database_connection():
        sys.exit(0)
    else:
        sys.exit(1)