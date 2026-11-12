#!/usr/bin/env python3
"""Create private, local Docker environment without exposing credentials."""

import os
import secrets
from pathlib import Path


def setup(root):
    output = root / ".env.wonders"
    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(f"SECRET_KEY_BASE={secrets.token_hex(64)}\n")
        stream.write(f"POSTGRES_PASSWORD={secrets.token_hex(32)}\n")
    return True


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    created = setup(root)
    print("Lokální prostředí připravené." if created else "Existující prostředí ponecháno beze změny.")
