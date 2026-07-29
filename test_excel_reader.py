from pathlib import Path

import pandas as pd
import pytest

from services.excel_reader import XLS_ERROR, read_xlsx
from services.file_security import PASSWORDS
from services.validator import missing_columns


@pytest.mark.parametrize("name", ["한글파일.xlsx", "space file.xlsx"])
def test_xlsx_names(tmp_path: Path, name: str) -> None:
    path = tmp_path / name
    pd.DataFrame({"주문번호": ["1"], "결제일": ["2026-01-01"]}).to_excel(path, index=False)
    result = read_xlsx(path)
    assert result.header_row == 1
    assert "결제일시" in result.data


def test_xls_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="xlsx"):
        read_xlsx(tmp_path / "old.xls")
    assert ".xlsx" in XLS_ERROR


def test_password_policy_is_strict() -> None:
    assert PASSWORDS == ("1234", "0000")


def test_missing_required_column() -> None:
    assert missing_columns(pd.DataFrame({"주문번호": []}), ["주문번호", "결제일시"]) == ["결제일시"]

