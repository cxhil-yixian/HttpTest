"""DATA 模組——檔案通道、報表排版、Excel 讀寫。

不含任何測試網站的知識，ITDOG 與之後的 TCPTEST 共用。
"""

from .records import HTTP, HTTPS, ResultRecord, strip_scheme
from .ip_list import read_ips, write_ips, split_batches
from .logs import clear_logs, log_filename, protocol_of, read_logs, write_log
from .report import (
    build_headers,
    build_rows,
    generate_report,
    load_result_grids,
    save_excel,
)

__all__ = [
    "HTTP",
    "HTTPS",
    "ResultRecord",
    "strip_scheme",
    "read_ips",
    "write_ips",
    "split_batches",
    "clear_logs",
    "log_filename",
    "protocol_of",
    "read_logs",
    "write_log",
    "build_headers",
    "build_rows",
    "generate_report",
    "load_result_grids",
    "save_excel",
]
