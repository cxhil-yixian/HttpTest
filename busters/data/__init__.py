"""DATA 模組——檔案通道、報表排版、Excel 讀寫。

不含任何測試網站的知識，itdog 與 tcptest 共用。
"""

from .records import (
    HTTP,
    HTTPS,
    ResultRecord,
    SiteProbe,
    bare_ip,
    strip_port,
    strip_scheme,
)
from .ip_list import read_ips, write_ips, split_batches
from .logs import clear_logs, log_filename, protocol_of, read_logs, write_log
from .report import (
    build_headers,
    build_rows,
    generate_dynamic_report,
    generate_report,
    load_result_grids,
    node_label,
    node_name,
    nodes_in,
    save_excel,
    save_site_report,
)

__all__ = [
    "HTTP",
    "HTTPS",
    "ResultRecord",
    "SiteProbe",
    "bare_ip",
    "strip_port",
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
    "generate_dynamic_report",
    "generate_report",
    "load_result_grids",
    "node_label",
    "node_name",
    "nodes_in",
    "save_excel",
    "save_site_report",
]
