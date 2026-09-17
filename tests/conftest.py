"""Gemeinsame Test-Einstellungen."""

import os

# Die Oberflaechen-Tests brauchen keinen Bildschirm.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
