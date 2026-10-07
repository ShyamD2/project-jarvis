## Description
Please include a summary of the change, which issue it addresses, and the rationale behind the implementation.

Fixes #(issue)

## Type of Change
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change adding a tool or capability)
- [ ] 🛡 Security hardening or invariant verification
- [ ] ⚡ Performance / Latency optimization (SLA improvement)
- [ ] 📝 Documentation update

## Architectural Invariant Checklist
- [ ] **Authority Compliance**: My change respects the 5 Single Authorities (Permission, Routing, Execution, Ground-Truth, Memory).
- [ ] **False-Success Defense**: Any newly added tool defines a strict verification contract and cannot report success without state corroboration.
- [ ] **Blast Radius Classification**: If this modifies system or cloud state, it is assigned the correct `ActionTier`.
- [ ] **Tests Added / Updated**: Automated pytest tests cover both happy-path execution and fail-closed edge cases.
- [ ] **All Quality Gates Pass**:
  - `pytest tests/ -v` (100% pass)
  - `ruff check services/ shared/ devices/ benchmarks/` (0 errors)
  - `bandit -r services/ shared/ -ll -ii` (0 Medium/High)
