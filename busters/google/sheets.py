"""Google Sheets 讀寫。

本模組只認「欄位字母 + 起始列 + 二維陣列」，不知道欄位怎麼排、
也不知道資料是誰產生的——排版由 DATA 模組負責。
"""

from pathlib import Path
from typing import List, Sequence

import gspread
from google.oauth2.service_account import Credentials

from ..config import SheetsConfig, column_index, column_letter

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def open_worksheet(cfg: SheetsConfig):
    """依 gid 開啟工作表。工作表名稱每天變動，所以用 gid 而非名稱識別。"""
    creds_path = Path(cfg.credentials_path)
    if not creds_path.exists():
        raise FileNotFoundError(
            f"找不到 Service Account 金鑰: {creds_path}\n"
            f"請確認 .env 的 GOOGLE_CREDENTIALS 設定正確。"
        )
    if not cfg.sheet_id:
        raise ValueError("未設定 SHEET_ID，請檢查 .env")

    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(cfg.sheet_id)

    for worksheet in spreadsheet.worksheets():
        if worksheet.id == cfg.worksheet_gid:
            return worksheet
    raise ValueError(f"找不到 gid={cfg.worksheet_gid} 的工作表")


def read_column(worksheet, column: str, start_row: int) -> List[str]:
    """讀取單一欄位，從 start_row 開始，略過空白。"""
    values = worksheet.col_values(column_index(column) + 1)
    return [v.strip() for v in values[start_row - 1:] if v.strip()]


def write_grid(worksheet, values: Sequence[Sequence[str]],
               start_column: str, start_row: int) -> str:
    """把二維陣列貼到指定起點，回傳實際寫入的範圍字串。

    空陣列直接跳過，不會清掉工作表上的既有內容。
    """
    values = [list(row) for row in values]
    if not values:
        return ""

    width = max(len(row) for row in values)
    start_idx = column_index(start_column)
    end_column = column_letter(start_idx + width - 1)
    end_row = start_row + len(values) - 1
    range_name = f"{start_column}{start_row}:{end_column}{end_row}"

    worksheet.update(values=values, range_name=range_name)
    return range_name
