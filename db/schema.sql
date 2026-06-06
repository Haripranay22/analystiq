-- AnalystIQ: Fintech Database Schema
-- Phase 1 - Database Layer
--
-- Run with: psql -U postgres -d analystiq -f schema.sql

-- Drop tables if rebuilding from scratch
DROP TABLE IF EXISTS fraud_flags CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- Customers: who holds accounts
CREATE TABLE customers (
    id              SERIAL PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150) UNIQUE NOT NULL,
    country         VARCHAR(60)  NOT NULL,
    age             INT,
    segment         VARCHAR(30)  CHECK (segment IN ('retail', 'premium', 'business')),
    risk_score      NUMERIC(4,2) CHECK (risk_score BETWEEN 0 AND 10),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Accounts: a customer can have multiple accounts
CREATE TABLE accounts (
    id              SERIAL PRIMARY KEY,
    customer_id     INT REFERENCES customers(id) ON DELETE CASCADE,
    account_type    VARCHAR(30) CHECK (account_type IN ('checking', 'savings', 'credit', 'investment')),
    balance         NUMERIC(15,2) DEFAULT 0.00,
    credit_limit    NUMERIC(15,2),          -- only relevant for credit accounts
    status          VARCHAR(20) CHECK (status IN ('active', 'frozen', 'closed')) DEFAULT 'active',
    opened_at       TIMESTAMP DEFAULT NOW()
);

-- Transactions: every payment, transfer, or withdrawal
CREATE TABLE transactions (
    id              SERIAL PRIMARY KEY,
    account_id      INT REFERENCES accounts(id) ON DELETE CASCADE,
    amount          NUMERIC(12,2) NOT NULL,
    direction       VARCHAR(10) CHECK (direction IN ('debit', 'credit')),
    merchant        VARCHAR(120),
    category        VARCHAR(60),            -- e.g. 'food', 'travel', 'electronics'
    channel         VARCHAR(30) CHECK (channel IN ('online', 'in-store', 'atm', 'wire')),
    status          VARCHAR(20) CHECK (status IN ('completed', 'pending', 'failed', 'reversed')),
    is_fraud        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Fraud flags: which rule triggered on a suspicious transaction
CREATE TABLE fraud_flags (
    id              SERIAL PRIMARY KEY,
    transaction_id  INT REFERENCES transactions(id) ON DELETE CASCADE,
    rule_triggered  VARCHAR(100),           -- e.g. 'velocity_check', 'geo_mismatch'
    confidence_score NUMERIC(4,3)  CHECK (confidence_score BETWEEN 0 AND 1),
    reviewed_by     VARCHAR(80),            -- analyst who reviewed it
    resolution      VARCHAR(30) CHECK (resolution IN ('confirmed_fraud', 'false_positive', 'pending')),
    flagged_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes for common analyst query patterns
CREATE INDEX idx_transactions_account   ON transactions(account_id);
CREATE INDEX idx_transactions_created   ON transactions(created_at);
CREATE INDEX idx_transactions_is_fraud  ON transactions(is_fraud);
CREATE INDEX idx_transactions_category  ON transactions(category);
CREATE INDEX idx_accounts_customer      ON accounts(customer_id);
CREATE INDEX idx_fraud_flags_txn        ON fraud_flags(transaction_id);
