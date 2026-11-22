-- ==========================================================
-- 008_wallet_mpesa.sql
-- M-Pesa-backed betting wallet deposits + withdrawals.
--
-- Deposits (STK push, money IN) and withdrawals (B2C, money OUT) share one
-- table because they're the same kind of thing from the ledger's point of
-- view: a pending external M-Pesa request that resolves to completed or
-- failed, carrying the gross/tax/net split required by every deposit and
-- withdrawal (config/betting_finance.py).
--
-- Purely additive - safe to re-run.
-- ==========================================================

CREATE TABLE IF NOT EXISTS wallet_mpesa_requests (
    id                       SERIAL PRIMARY KEY,
    user_id                  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    direction                VARCHAR(10) NOT NULL CHECK (direction IN ('DEPOSIT', 'WITHDRAWAL')),
    status                   VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'COMPLETED', 'FAILED')
    ),

    phone                    VARCHAR(15) NOT NULL,

    -- What the user typed/asked for. For a deposit, this is what M-Pesa
    -- actually charges them. For a withdrawal, this is what their wallet
    -- is debited (see database/wallet_mpesa_repository.py — the gross
    -- amount leaves the wallet immediately on request, not on completion).
    gross_amount             NUMERIC(14, 2) NOT NULL,
    tax_amount               NUMERIC(14, 2) NOT NULL,
    -- Deposit: what actually lands in the wallet once M-Pesa confirms.
    -- Withdrawal: what actually gets sent to the user's phone via B2C.
    net_amount               NUMERIC(14, 2) NOT NULL,

    -- STK push (deposit) correlation IDs.
    checkout_request_id      VARCHAR(100),
    merchant_request_id      VARCHAR(100),

    -- B2C (withdrawal) correlation IDs. Daraja's two different products
    -- use two different ID schemes; a betting_mpesa_requests row is never
    -- looked up by both at once, so storing all four nullable columns on
    -- one table (rather than two separate tables) keeps the callback
    -- handlers in api/mpesa.py simple without ever mixing them up.
    conversation_id            VARCHAR(100),
    originator_conversation_id VARCHAR(100),

    mpesa_receipt            VARCHAR(100),
    failure_reason           TEXT,

    created_at               TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wallet_mpesa_requests_user
    ON wallet_mpesa_requests (user_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_wallet_mpesa_checkout_request_id
    ON wallet_mpesa_requests (checkout_request_id)
    WHERE checkout_request_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_wallet_mpesa_conversation_id
    ON wallet_mpesa_requests (conversation_id)
    WHERE conversation_id IS NOT NULL;

-- A withdrawal that fails/times out after the wallet was already debited
-- (at request time — see wallet_mpesa_repository.create_withdrawal_request)
-- needs to refund that debit. 'WITHDRAWAL_REVERSAL' makes that refund's
-- type self-explanatory in the transaction history, rather than reusing
-- 'DEPOSIT' for money that was never actually deposited.
--
-- IMPORTANT - READ BEFORE RELYING ON THIS: Postgres auto-names a CHECK
-- constraint unless it was named explicitly. 005_betting.sql's
-- wallet_transactions.type CHECK was NOT given an explicit name, so this
-- migration cannot know its real name without your live schema. Run:
--
--     \d wallet_transactions
--
-- in psql and look at the "Check constraints" section for the constraint
-- covering the "type" column (commonly named wallet_transactions_type_check
-- by Postgres's default convention, but confirm against your own output).
-- If the name below is wrong for your database, this ALTER will error with
-- "constraint ... does not exist" — harmless, just re-run it with the
-- correct name substituted.

DO $$
BEGIN
    ALTER TABLE wallet_transactions DROP CONSTRAINT wallet_transactions_type_check;
EXCEPTION
    WHEN undefined_object THEN
        RAISE NOTICE 'wallet_transactions_type_check did not exist under that name — see the comment above this block.';
END $$;

ALTER TABLE wallet_transactions ADD CONSTRAINT wallet_transactions_type_check
    CHECK (
        type IN (
            'DEPOSIT',
            'WITHDRAWAL',
            'WITHDRAWAL_REVERSAL',
            'BET_STAKE',
            'BET_PAYOUT',
            'BET_REFUND',
            'JACKPOT_STAKE',
            'JACKPOT_PAYOUT'
        )
    );
