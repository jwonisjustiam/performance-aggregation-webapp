"""Encrypted workbook handling with a strict password policy."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Iterator

import msoffcrypto

PASSWORDS = ("1234", "0000")
PASSWORD_ERROR = (
    "파일이 암호화되어 있습니다. 기본 비밀번호 1234와 0000으로 열지 못했습니다. "
    "올바른 비밀번호가 필요합니다."
)


def is_encrypted(path: Path) -> bool:
    """Return whether an Office workbook reports encryption."""
    with path.open("rb") as source:
        return bool(msoffcrypto.OfficeFile(source).is_encrypted())


@contextmanager
def readable_workbook(path: Path) -> Iterator[tuple[Path, bool]]:
    """Yield a readable workbook path and remove decrypted temporary data."""
    if not is_encrypted(path):
        yield path, False
        return

    decrypted_path: Path | None = None
    try:
        for password in PASSWORDS:
            try:
                with path.open("rb") as source:
                    office = msoffcrypto.OfficeFile(source)
                    office.load_key(password=password)
                    handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
                    decrypted_path = Path(handle.name)
                    try:
                        office.decrypt(handle)
                    finally:
                        handle.close()
                break
            except Exception:
                if decrypted_path and decrypted_path.exists():
                    decrypted_path.unlink()
                decrypted_path = None
        if decrypted_path is None:
            raise ValueError(PASSWORD_ERROR)
        yield decrypted_path, True
    finally:
        if decrypted_path and decrypted_path.exists():
            decrypted_path.unlink()
