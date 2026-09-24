-- Migration: v003_audit_ledger.sql
-- Description: Cryptographically chained immutable audit ledger storage

CREATE TABLE IF NOT EXISTS audit_ledger_blocks (
    block_index INTEGER PRIMARY KEY,
    timestamp DOUBLE PRECISION NOT NULL,
    prev_hash VARCHAR(64) NOT NULL,
    block_hash VARCHAR(64) NOT NULL,
    intent TEXT NOT NULL,
    tool VARCHAR(128) NOT NULL,
    parameters_json TEXT NOT NULL,
    authorization VARCHAR(128) NOT NULL,
    verified BOOLEAN DEFAULT TRUE,
    result VARCHAR(64) DEFAULT 'SUCCESS',
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_blocks_tool ON audit_ledger_blocks(tool);
CREATE INDEX IF NOT EXISTS idx_audit_blocks_timestamp ON audit_ledger_blocks(timestamp);
