"""Seed a demo "grader" account in Ghostfolio with 5 years of purchase history.

Usage:
    GHOSTFOLIO_URL=http://localhost:3333 python scripts/seed_grader.py

This script:
1. Creates a new Ghostfolio user via POST /api/v1/user
2. Creates a brokerage account
3. Seeds ~60 buy orders spread across 5 years for a diversified portfolio
4. Prints the security token for the new user

The security token is needed for the GRADER_TOKEN env variable.
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timedelta

import httpx

GHOSTFOLIO_URL = os.getenv("GHOSTFOLIO_URL", "http://localhost:3333")

# Diversified portfolio: mix of stocks, ETFs, bonds
SYMBOLS = [
    # Large-cap tech
    {"symbol": "AAPL", "name": "Apple Inc.", "type": "STOCK"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "type": "STOCK"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "type": "STOCK"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "STOCK"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "type": "STOCK"},
    # Other sectors
    {"symbol": "JPM", "name": "JPMorgan Chase", "type": "STOCK"},
    {"symbol": "JNJ", "name": "Johnson & Johnson", "type": "STOCK"},
    {"symbol": "PG", "name": "Procter & Gamble", "type": "STOCK"},
    {"symbol": "XOM", "name": "Exxon Mobil", "type": "STOCK"},
    {"symbol": "DIS", "name": "Walt Disney", "type": "STOCK"},
    # ETFs
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "type": "STOCK"},
    {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "type": "STOCK"},
    {"symbol": "VEA", "name": "Vanguard FTSE Developed Markets ETF", "type": "STOCK"},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "type": "STOCK"},
    {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "type": "STOCK"},
]


def create_user(client: httpx.Client) -> dict:
    """Create a new anonymous Ghostfolio user."""
    res = client.post(f"{GHOSTFOLIO_URL}/api/v1/user", timeout=30.0)
    if res.status_code not in (200, 201):
        print(f"Failed to create user: {res.status_code} {res.text}")
        sys.exit(1)
    data = res.json()
    print(f"Created user: {data.get('id', 'unknown')}")
    return data


def login(client: httpx.Client, security_token: str) -> str:
    """Login and get auth JWT."""
    res = client.post(
        f"{GHOSTFOLIO_URL}/api/v1/auth/anonymous",
        json={"accessToken": security_token},
        timeout=15.0,
    )
    if res.status_code != 201:
        print(f"Login failed: {res.status_code} {res.text}")
        sys.exit(1)
    return res.json()["authToken"]


def create_account(client: httpx.Client, auth_token: str) -> str:
    """Create a brokerage account and return its ID."""
    res = client.post(
        f"{GHOSTFOLIO_URL}/api/v1/account",
        json={
            "balance": 0,
            "currency": "USD",
            "isExcluded": False,
            "name": "Demo Brokerage",
            "platformId": None,
        },
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=15.0,
    )
    if res.status_code not in (200, 201):
        print(f"Failed to create account: {res.status_code} {res.text}")
        sys.exit(1)
    account_id = res.json()["id"]
    print(f"Created account: {account_id}")
    return account_id


def generate_orders(account_id: str) -> list[dict]:
    """Generate ~60 buy orders spread across 5 years."""
    orders = []
    now = datetime.now()
    start = now - timedelta(days=5 * 365)

    random.seed(42)  # Reproducible

    # Monthly investing pattern: pick 1-2 symbols each month
    current = start
    while current < now:
        # Each month, buy 1-2 different positions
        month_picks = random.sample(SYMBOLS, k=random.randint(1, 2))
        for pick in month_picks:
            # Vary quantity by asset type
            if pick["symbol"] in ("BND", "VTI", "VOO", "VEA", "VNQ"):
                quantity = round(random.uniform(5, 20), 2)
            else:
                quantity = round(random.uniform(1, 10), 2)

            # Use a rough historical price estimate (doesn't need to be exact;
            # Ghostfolio will resolve actual prices from market data)
            unit_price = round(random.uniform(50, 500), 2)
            fee = round(random.uniform(0, 9.99), 2)

            order_date = current + timedelta(days=random.randint(1, 28))
            if order_date > now:
                continue

            orders.append(
                {
                    "accountId": account_id,
                    "currency": "USD",
                    "dataSource": "YAHOO",
                    "date": order_date.strftime("%Y-%m-%dT00:00:00.000Z"),
                    "fee": fee,
                    "quantity": quantity,
                    "symbol": pick["symbol"],
                    "type": "BUY",
                    "unitPrice": unit_price,
                }
            )

        current += timedelta(days=30)

    # Add a few SELL orders for realism (sell partial positions)
    sell_candidates = random.sample(orders[: len(orders) // 2], k=min(5, len(orders) // 4))
    for buy_order in sell_candidates:
        sell_date = datetime.strptime(buy_order["date"][:10], "%Y-%m-%d") + timedelta(days=random.randint(60, 365))
        if sell_date > now:
            continue
        orders.append(
            {
                "accountId": account_id,
                "currency": "USD",
                "dataSource": "YAHOO",
                "date": sell_date.strftime("%Y-%m-%dT00:00:00.000Z"),
                "fee": round(random.uniform(0, 9.99), 2),
                "quantity": round(buy_order["quantity"] * random.uniform(0.3, 0.7), 2),
                "symbol": buy_order["symbol"],
                "type": "SELL",
                "unitPrice": round(buy_order["unitPrice"] * random.uniform(0.9, 1.5), 2),
            }
        )

    orders.sort(key=lambda o: o["date"])
    return orders


def seed_orders(client: httpx.Client, auth_token: str, orders: list[dict]) -> int:
    """Submit orders to Ghostfolio. Returns count of successful orders."""
    success = 0
    for i, order in enumerate(orders):
        res = client.post(
            f"{GHOSTFOLIO_URL}/api/v1/order",
            json=order,
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=15.0,
        )
        if res.status_code in (200, 201):
            success += 1
        else:
            print(f"  Order {i + 1} failed ({order['symbol']} {order['type']}): {res.status_code}")
        if (i + 1) % 10 == 0:
            print(f"  Submitted {i + 1}/{len(orders)} orders...")
    return success


def main():
    global GHOSTFOLIO_URL
    parser = argparse.ArgumentParser(description="Seed a grader demo account in Ghostfolio")
    parser.add_argument("--url", default=GHOSTFOLIO_URL, help="Ghostfolio base URL")
    args = parser.parse_args()

    GHOSTFOLIO_URL = args.url

    print(f"Ghostfolio URL: {GHOSTFOLIO_URL}")
    print("=" * 50)

    client = httpx.Client()

    # Step 1: Create user
    print("\n1. Creating new user...")
    user_data = create_user(client)
    security_token = user_data.get("accessToken") or user_data.get("authToken")
    if not security_token:
        # The response might be structured differently; print and inspect
        print(f"   Full response: {json.dumps(user_data, indent=2)}")
        print("   Could not find security token in response. Check manually.")
        sys.exit(1)
    print(f"   Security token: {security_token}")

    # Step 2: Login to get JWT
    print("\n2. Logging in...")
    auth_token = login(client, security_token)
    print(f"   Got auth JWT (len={len(auth_token)})")

    # Step 3: Create account
    print("\n3. Creating brokerage account...")
    account_id = create_account(client, auth_token)

    # Step 4: Generate and submit orders
    print("\n4. Generating orders...")
    orders = generate_orders(account_id)
    print(f"   Generated {len(orders)} orders across {len(set(o['symbol'] for o in orders))} symbols")

    print("\n5. Submitting orders...")
    success = seed_orders(client, auth_token, orders)
    print(f"\n   Done! {success}/{len(orders)} orders submitted successfully")

    # Summary
    print("\n" + "=" * 50)
    print("GRADER ACCOUNT SETUP COMPLETE")
    print(f"  Security Token: {security_token}")
    print(f"  Account ID:     {account_id}")
    print(f"  Orders:         {success}")
    print("\nSet this in your environment:")
    print(f"  GRADER_TOKEN={security_token}")


if __name__ == "__main__":
    main()
