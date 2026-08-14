"""GOOGLE 模組——Google Sheets 讀寫。

不含任何測試網站或報表排版的知識，ITDOG 與之後的 TCPTEST 共用。
"""

from .sheets import SCOPES, open_worksheet, read_column, write_grid

__all__ = ["SCOPES", "open_worksheet", "read_column", "write_grid"]
