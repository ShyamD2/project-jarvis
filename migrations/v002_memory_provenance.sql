-- Migration: v002_memory_provenance.sql
-- Description: Adds memory provenance, confidence decay, sensitivity, and user confirmation tables

CREATE TABLE IF NOT EXISTS memory_items (
    memory_id VARCHAR(64) PRIMARY KEY,
    fact TEXT NOT NULL,
    category VARCHAR(64) DEFAULT 'fact',
    source VARCHAR(64) NOT NULL,
    device_id VARCHAR(64) DEFAULT 'local_node',
    user_id VARCHAR(64) DEFAULT 'operator',
    confidence DOUBLE PRECISION DEFAULT 1.0,
    sensitivity VARCHAR(32) DEFAULT 'INTERNAL',
    expiration DOUBLE PRECISION,
    user_confirmed BOOLEAN DEFAULT FALSE,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_items_category ON memory_items(category);
CREATE INDEX IF NOT EXISTS idx_memory_items_sensitivity ON memory_items(sensitivity);
