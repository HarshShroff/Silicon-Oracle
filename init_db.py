#!/usr/bin/env python3
"""
Silicon Oracle - Database Initialization Script

This script initializes the database schema for both SQLite and PostgreSQL (Supabase).
Run this script to create all necessary tables.

Usage:
    python init_db.py                    # Uses default config (SQLite)
    DATABASE_URL=... python init_db.py   # Uses specified PostgreSQL database

For Supabase, set:
    DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def init_database():
    """Initialize the database and create all tables."""
    from flask_app import create_app
    from flask_app.extensions import db
    from flask_app.models import User, ShadowPosition

    # Create app with configuration
    app = create_app()

    with app.app_context():
        print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("-" * 50)

        # Create all tables
        print("Creating database tables...")
        db.create_all()

        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()

        print(f"\nTables created: {len(tables)}")
        for table in tables:
            columns = [col['name'] for col in inspector.get_columns(table)]
            print(f"  - {table}: {len(columns)} columns")
            for col in columns:
                print(f"      * {col}")

        print("\n" + "=" * 50)
        print("Database initialization complete!")
        print("=" * 50)

        # Show connection info for Supabase
        if "supabase" in app.config['SQLALCHEMY_DATABASE_URI'].lower():
            print("\nConnected to Supabase PostgreSQL!")
            print("Your database is ready for multi-user access.")
        elif "sqlite" in app.config['SQLALCHEMY_DATABASE_URI'].lower():
            print("\nUsing local SQLite database.")
            print("For multi-user support, set DATABASE_URL to your Supabase connection string.")


def create_test_user():
    """Create a test user (for development only)."""
    from flask_app import create_app
    from flask_app.extensions import db
    from flask_app.models import User

    app = create_app()

    with app.app_context():
        # Check if test user exists
        test_user = User.query.filter_by(username='testuser').first()
        if test_user:
            print("Test user already exists.")
            return

        # Create test user
        user = User(
            username='testuser',
            email='test@example.com'
        )
        user.set_password('testpass123')

        db.session.add(user)
        db.session.commit()

        print("Test user created:")
        print("  Username: testuser")
        print("  Password: testpass123")


if __name__ == "__main__":
    print("=" * 50)
    print("Silicon Oracle - Database Initialization")
    print("=" * 50)
    print()

    # Check for command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--test-user':
            create_test_user()
            sys.exit(0)
        elif sys.argv[1] == '--help':
            print(__doc__)
            sys.exit(0)

    init_database()
