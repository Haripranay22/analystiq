"""
Phase 1 — Seed Script
Generates realistic synthetic fintech data and loads it into PostgreSQL.

What this script teaches:
- How to connect to PostgreSQL using SQLAlchemy
- How to generate realistic fake data with Faker
- How fraud patterns look in real transaction data

Run with: python db/seed.py
"""

import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from faker import Faker
from sqlalchemy import create_engine, text

load_dotenv()

fake = Faker()
random.seed(42)
Faker.seed(42)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")

MERCHANTS = {
    "food":        ["McDonald's", "Chipotle", "Uber Eats", "DoorDash", "Starbucks"],
    "travel":      ["Delta Airlines", "Marriott Hotels", "Airbnb", "Uber", "Lyft"],
    "electronics": ["Apple Store", "Best Buy", "Amazon", "Newegg", "B&H Photo"],
    "retail":      ["Walmart", "Target", "Costco", "Zara", "Nike"],
    "utilities":   ["AT&T", "Comcast", "Texas Electric", "Water Dept", "City Gas"],
    "healthcare":  ["CVS Pharmacy", "Walgreens", "LabCorp", "Urgent Care", "Dental Plus"],
}

FRAUD_RULES = [
    "velocity_check",
    "geo_mismatch",
    "unusual_amount",
    "after_hours_activity",
    "card_not_present",
    "multiple_declines",
]


def random_date(start_days_ago: int = 365, end_days_ago: int = 0) -> datetime:
    start = datetime.now() - timedelta(days=start_days_ago)
    end = datetime.now() - timedelta(days=end_days_ago)
    return start + (end - start) * random.random()


def seed(engine):
    """
    Each phase uses its own connection + commit.
    Cloud DBs (Neon) time out long-held connections — committing per phase
    keeps each transaction short and safe.
    """
    CHUNK = 100

    # ── Phase 1: customers ────────────────────────────────────────────────────
    print("Seeding customers...")
    customer_ids = []
    with engine.begin() as conn:
        for _ in range(200):
            result = conn.execute(
                text("""
                    INSERT INTO customers
                        (full_name, email, country, age, segment, risk_score, credit_score, created_at)
                    VALUES
                        (:full_name, :email, :country, :age, :segment, :risk_score, :credit_score, :created_at)
                    RETURNING id
                """),
                {
                    "full_name":    fake.name(),
                    "email":        fake.unique.email(),
                    "country":      random.choice(["USA", "USA", "USA", "Canada", "UK", "Germany"]),
                    "age":          random.randint(21, 70),
                    "segment":      random.choices(["retail", "premium", "business"], weights=[60, 30, 10])[0],
                    "risk_score":   round(random.uniform(0.5, 9.5), 2),
                    "credit_score": random.randint(300, 850),
                    "created_at":   random_date(730, 365),
                },
            )
            customer_ids.append(result.fetchone()[0])
    print(f"  {len(customer_ids)} customers inserted")

    # ── Phase 2: accounts ─────────────────────────────────────────────────────
    print("Seeding accounts...")
    account_ids = []
    with engine.begin() as conn:
        for cid in customer_ids:
            acc_type = random.choices(
                ["checking", "savings", "credit", "investment"],
                weights=[40, 30, 20, 10],
            )[0]
            for _ in range(random.choices([1, 2, 3], weights=[50, 35, 15])[0]):
                result = conn.execute(
                    text("""
                        INSERT INTO accounts
                            (customer_id, account_type, balance, credit_limit, status, opened_at)
                        VALUES
                            (:customer_id, :account_type, :balance, :credit_limit, :status, :opened_at)
                        RETURNING id
                    """),
                    {
                        "customer_id":  cid,
                        "account_type": acc_type,
                        "balance":      round(random.uniform(100, 50000), 2),
                        "credit_limit": round(random.uniform(1000, 25000), 2) if acc_type == "credit" else None,
                        "status":       random.choices(["active", "frozen", "closed"], weights=[90, 5, 5])[0],
                        "opened_at":    random_date(730, 180),
                    },
                )
                account_ids.append(result.fetchone()[0])
    print(f"  {len(account_ids)} accounts inserted")

    # ── Phase 3: transactions (build in memory, commit per chunk) ─────────────
    print("Seeding transactions...")
    txn_rows = []
    for acc_id in account_ids:
        for _ in range(random.randint(10, 80)):
            category = random.choice(list(MERCHANTS.keys()))
            is_fraud = random.random() < 0.04
            txn_rows.append({
                "account_id": acc_id,
                "amount":     round(random.uniform(1, 5000 if is_fraud else 500), 2),
                "direction":  random.choices(["debit", "credit"], weights=[80, 20])[0],
                "merchant":   random.choice(MERCHANTS[category]),
                "category":   category,
                "channel":    random.choices(["online", "in-store", "atm", "wire"], weights=[40, 40, 15, 5])[0],
                "status":     "completed" if not is_fraud else random.choice(["completed", "failed"]),
                "is_fraud":   is_fraud,
                "created_at": random_date(365, 0),
            })

    for i in range(0, len(txn_rows), CHUNK):
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO transactions
                        (account_id, amount, direction, merchant, category, channel, status, is_fraud, created_at)
                    VALUES
                        (:account_id, :amount, :direction, :merchant, :category, :channel, :status, :is_fraud, :created_at)
                """),
                txn_rows[i:i + CHUNK],
            )
        print(f"  {min(i + CHUNK, len(txn_rows)):,} / {len(txn_rows):,} transactions", end="\r")
    print()

    # ── Phase 4: fraud flags ──────────────────────────────────────────────────
    print("Seeding fraud flags...")
    with engine.connect() as conn:
        fraud_ids = [r[0] for r in conn.execute(
            text("SELECT id FROM transactions WHERE is_fraud = true")
        ).fetchall()]

    flag_rows = [
        {
            "transaction_id":   txn_id,
            "rule_triggered":   random.choice(FRAUD_RULES),
            "confidence_score": round(random.uniform(0.60, 0.99), 3),
            "reviewed_by":      random.choice(["analyst_team", "auto_system", None]),
            "resolution":       random.choices(
                ["confirmed_fraud", "false_positive", "pending"], weights=[60, 25, 15]
            )[0],
            "flagged_at": random_date(30, 0),
        }
        for txn_id in fraud_ids
    ]
    for i in range(0, len(flag_rows), CHUNK):
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO fraud_flags
                        (transaction_id, rule_triggered, confidence_score, reviewed_by, resolution, flagged_at)
                    VALUES
                        (:transaction_id, :rule_triggered, :confidence_score, :reviewed_by, :resolution, :flagged_at)
                """),
                flag_rows[i:i + CHUNK],
            )

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\nDone! Summary:")
    with engine.connect() as conn:
        for table in ["customers", "accounts", "transactions", "fraud_flags"]:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:15s}: {count:,} rows")


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "keepalives": 1,
            "keepalives_idle": 10,
            "keepalives_interval": 5,
            "keepalives_count": 5,
            "connect_timeout": 30,
        },
        pool_pre_ping=True,
    )
    seed(engine)
