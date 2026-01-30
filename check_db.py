#!/usr/bin/env python3
"""
Diagnostic script to check database state.
Run: python check_db.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask_app import create_app
from flask_app.extensions import db
from flask_app.models import User, ShadowPosition

app = create_app()

with app.app_context():
    print("=" * 60)
    print("DATABASE DIAGNOSTIC")
    print("=" * 60)
    print(f"\nDatabase URI: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")

    # Check users
    print("\n--- USERS ---")
    users = User.query.all()
    if not users:
        print("No users found!")
    else:
        for user in users:
            print(f"  ID: {user.id}, Username: {user.username}, Email: {user.email}")

    # Check positions
    print("\n--- ALL POSITIONS ---")
    positions = ShadowPosition.query.all()
    if not positions:
        print("No positions found!")
    else:
        for pos in positions:
            print(f"  ID: {pos.id}, User ID: {pos.user_id}, Ticker: {pos.ticker}, "
                  f"Qty: {pos.quantity}, Active: {pos.is_active}")

    # Check position-user mapping
    print("\n--- POSITION-USER MAPPING ---")
    for pos in positions:
        owner = User.query.get(pos.user_id)
        if owner:
            print(f"  Position {pos.ticker} belongs to user '{owner.username}' (ID: {owner.id})")
        else:
            print(f"  Position {pos.ticker} has user_id={pos.user_id} - NO MATCHING USER!")

    print("\n" + "=" * 60)
