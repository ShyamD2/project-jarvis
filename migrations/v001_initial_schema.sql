-- Migration: v001_initial_schema.sql
-- Description: Core schema for J.A.R.V.I.S. database persistence

CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(64) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS episodic_memories (
    id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    timestamp DOUBLE PRECISION NOT NULL,
    user_query TEXT NOT NULL,
    jarvis_response TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'SUCCESS',
    latency_ms DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_leases (
    lease_id VARCHAR(64) PRIMARY KEY,
    action_name VARCHAR(128) NOT NULL,
    parameters_hash VARCHAR(64) NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    issued_by VARCHAR(64) NOT NULL,
    issued_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    consumed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
