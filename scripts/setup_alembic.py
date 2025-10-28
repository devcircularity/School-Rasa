#!/usr/bin/env python3
# scripts/setup_alembic.py - Complete Alembic setup and migration script
import sys
import os
import subprocess
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_command(cmd, description):
    """Run a shell command and handle errors"""
    print(f"\n{'='*50}")
    print(f"🔧 {description}")
    print(f"{'='*50}")
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print("✅ Output:")
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False

def setup_alembic():
    """Complete Alembic setup process"""
    
    print("🚀 Setting up Alembic for School Assistant API")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("app").exists() or not Path("app/models").exists():
        print("❌ Error: Please run this script from the project root directory")
        print("   Expected structure: project_root/app/models/")
        sys.exit(1)
    
    # Step 1: Install Alembic if not already installed
    print("\n📦 Checking Alembic installation...")
    try:
        import alembic
        print("✅ Alembic is already installed")
    except ImportError:
        print("Installing Alembic...")
        if not run_command([sys.executable, "-m", "pip", "install", "alembic"], "Installing Alembic"):
            print("❌ Failed to install Alembic")
            sys.exit(1)
    
    # Create scripts directory and __init__.py if they don't exist
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    (scripts_dir / "__init__.py").touch()
    
    # Step 2: Recreate database
    print("\n🗄️ Recreating database...")
    try:
        # Import the function directly
        sys.path.insert(0, str(scripts_dir))
        from recreate_db import recreate_database
        
        success = recreate_database()
        if success:
            print("✅ Database recreated successfully")
        else:
            print("❌ Database recreation failed")
            print("Please check your PostgreSQL connection and credentials")
            sys.exit(1)
    except ImportError as e:
        print(f"❌ Failed to import recreate_database function: {e}")
        print("Trying to recreate database manually...")
        
        # Fallback: recreate database inline
        try:
            import psycopg2
            from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
            from urllib.parse import urlparse
            
            db_url = "postgresql+psycopg2://schoolai2_user:StrongPassword123!@localhost/schoolai2rasa"
            parsed = urlparse(db_url)
            
            # Connect to postgres database
            conn = psycopg2.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            target_db = parsed.path.lstrip('/')
            print(f"Dropping and recreating database: {target_db}")
            
            # Drop and create database
            cursor.execute(f"DROP DATABASE IF EXISTS {target_db}")
            cursor.execute(f"CREATE DATABASE {target_db}")
            
            cursor.close()
            conn.close()
            print("✅ Database recreated successfully (fallback method)")
            
        except Exception as fallback_error:
            print(f"❌ Fallback database recreation also failed: {fallback_error}")
            print("Please make sure PostgreSQL is running and create the database manually:")
            print("  sudo -u postgres psql")
            print("  CREATE USER schooluser WITH PASSWORD 'schoolpass';")
            print("  CREATE DATABASE schooldb OWNER schooluser;")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to recreate database: {e}")
        print("Please make sure PostgreSQL is running and credentials are correct")
        sys.exit(1)
    
    # Step 3: Create migrations directory if it doesn't exist
    migrations_dir = Path("migrations")
    if migrations_dir.exists():
        print(f"\n📁 Migrations directory already exists: {migrations_dir}")
        # Clean up existing migrations
        versions_dir = migrations_dir / "versions"
        if versions_dir.exists():
            for file in versions_dir.glob("*.py"):
                if file.name != "__pycache__":
                    file.unlink()
                    print(f"🗑️ Removed old migration: {file}")
    else:
        print(f"\n📁 Creating migrations directory: {migrations_dir}")
        migrations_dir.mkdir(exist_ok=True)
    
    # Create versions directory
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    
    # Create __init__.py files
    (migrations_dir / "__init__.py").touch()
    (versions_dir / "__init__.py").touch()
    
    # Step 4: Test configuration
    print("\n⚙️ Testing configuration...")
    try:
        from app.core.config import settings
        from app.core.db import db_manager
        
        print(f"✅ Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")
        print(f"✅ Environment: {settings.ENV}")
        
        # Test database connection
        health = db_manager.health_check()
        if health["status"] == "healthy":
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {health}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Step 5: Generate initial migration
    print("\n📝 Generating initial migration...")
    if not run_command(
        ["alembic", "revision", "--autogenerate", "-m", "Initial migration with all models"],
        "Generating initial migration"
    ):
        print("❌ Failed to generate initial migration")
        sys.exit(1)
    
    # Step 6: Apply migration
    print("\n⬆️ Applying migration to database...")
    if not run_command(
        ["alembic", "upgrade", "head"],
        "Applying migration"
    ):
        print("❌ Failed to apply migration")
        sys.exit(1)
    
    # Step 7: Verify migration
    print("\n🔍 Verifying migration...")
    if not run_command(
        ["alembic", "current"],
        "Checking current migration version"
    ):
        print("❌ Failed to verify migration")
        sys.exit(1)
    
    # Step 8: Show migration history
    print("\n📊 Migration history:")
    run_command(
        ["alembic", "history", "--verbose"],
        "Showing migration history"
    )
    
    print("\n" + "="*60)
    print("🎉 Alembic setup completed successfully!")
    print("="*60)
    print("\nNext steps:")
    print("1. Your database is now ready with all tables created")
    print("2. Run 'python scripts/init_db.py' to add sample data")
    print("3. Start your FastAPI server: 'python scripts/run_dev.py'")
    print("\nUseful Alembic commands:")
    print("  alembic current              - Show current migration version")
    print("  alembic history              - Show migration history")
    print("  alembic revision --autogenerate -m 'message'  - Create new migration")
    print("  alembic upgrade head         - Apply all pending migrations")
    print("  alembic downgrade -1         - Rollback one migration")
    print("  alembic show <revision>      - Show specific migration details")

if __name__ == "__main__":
    setup_alembic()