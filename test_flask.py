#!/usr/bin/env python3.11
"""Test script to verify Flask app functionality"""

import requests
import json

# Base URL
BASE_URL = "http://localhost:5001"


def test_endpoints():
    """Test key endpoints to ensure data is accessible."""

    # Test chart API
    print("Testing chart API...")
    response = requests.get(f"{BASE_URL}/api/stock/AAPL/chart?period=1mo&interval=1d")
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Chart API returned {len(data)} data points")
    else:
        print(f"✗ Chart API failed: {response.status_code}")

    # Test quote API
    print("\nTesting quote API...")
    response = requests.get(f"{BASE_URL}/api/stock/AAPL/quote")
    if response.status_code == 200:
        data = response.json()
        if "current" in data:
            print(f"✓ Quote API: AAPL = ${data['current']:.2f}")
        else:
            print(f"✗ Quote API returned: {data}")
    else:
        print(f"✗ Quote API failed: {response.status_code}")

    # Test Oracle API
    print("\nTesting Oracle API...")
    response = requests.get(f"{BASE_URL}/api/oracle/AAPL")
    if response.status_code == 200:
        data = response.json()
        if "score" in data:
            print(f"✓ Oracle API: Score = {data['score']}/12")
        else:
            print(f"✗ Oracle API unexpected format: {list(data.keys())}")
    else:
        print(f"✗ Oracle API failed: {response.status_code}")


if __name__ == "__main__":
    try:
        test_endpoints()
    except requests.exceptions.ConnectionError:
        print("✗ Flask app is not running. Start it with: python3.11 run_flask.py")
