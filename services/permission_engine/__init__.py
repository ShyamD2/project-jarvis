"""
Re-export shim for services/permission-engine
Allows standard Python module import: `import services.permission_engine`
"""

import sys
import os

_PERM_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../permission-engine"))
if _PERM_DIR not in sys.path:
    sys.path.insert(0, _PERM_DIR)

from engine import permission_engine, PermissionEngine, PermissionDecision
from risk_classifier import classifier, RiskClassifier
from policy import policy, PolicyEngine

__all__ = [
    "permission_engine",
    "PermissionEngine",
    "PermissionDecision",
    "classifier",
    "RiskClassifier",
    "policy",
    "PolicyEngine",
]
