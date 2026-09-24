# Disaster Recovery & Database Migrations

## Overview
Project J.A.R.V.I.S. provides enterprise-grade disaster recovery, versioned database schema migrations, and cryptographic backup verification to guarantee zero data loss.

---

## 🗄 Versioned Database Migrations

Database schemas are managed via sequential SQL migration scripts in `migrations/`:
- `v001_initial_schema.sql`: Foundational tables (`schema_migrations`, `episodic_memory`, `audit_ledger`, `device_nodes`, `configuration_store`).
- `v002_memory_provenance.sql`: Memory provenance metadata (`source`, `confidence`, `sensitivity`, `user_confirmed`, `expiration`).
- `v003_audit_ledger.sql`: Cryptographic chained audit ledger index and integrity constraints.

### Migration CLI Runner
The migration runner (`migrations/migrate.py`) tracks applied migrations idempotently in the `schema_migrations` table:

```powershell
# Run pending migrations
python migrations/migrate.py --db data/jarvis.db

# Output:
# [INFO] Applying migration v001_initial_schema.sql...
# [INFO] Applying migration v002_memory_provenance.sql...
# [INFO] Applying migration v003_audit_ledger.sql...
# [INFO] All migrations applied successfully. Database is at version 3.
```

---

## 💾 Cryptographic Disaster Recovery CLI (`scripts/backup.py`)

The disaster recovery utility packages critical database files, configuration states, and audit ledgers into a compressed, SHA-256 verified archive (`.tar.gz`).

### 1. Creating a Verified Backup
```powershell
python scripts/backup.py backup --output backups/jarvis_backup.tar.gz
```
- Collects `data/`, configuration stores, and migration ledgers.
- Computes SHA-256 digests for every file.
- Writes an embedded `manifest.json` inside the archive containing:
  - Timestamp (ISO 8601)
  - Normalized forward-slash member paths
  - Exact SHA-256 checksums

### 2. Verifying Backup Integrity
```powershell
python scripts/backup.py verify backups/jarvis_backup.tar.gz
```
- Reads `manifest.json` from the archive.
- Re-hashes every member file.
- Confirms 100% cryptographic integrity before restore operations.

### 3. Restoring from Backup
```powershell
python scripts/backup.py restore backups/jarvis_backup.tar.gz --target-dir data/
```
- Validates the manifest SHA-256 checksums.
- Safely extracts files to the designated target directory.
- Refuses to overwrite corrupt or tampered files.
