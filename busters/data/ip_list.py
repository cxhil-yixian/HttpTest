"""IP 清單檔的讀寫（data/CDN_IP_list.txt）。"""

from pathlib import Path
from typing import Iterable, List


def read_ips(path) -> List[str]:
    """讀取 IP 清單，一行一個，略過空行。

    用 utf-8-sig 開檔：記事本、Excel、PowerShell 的 Out-File 都會在檔頭寫 BOM，
    照 utf-8 讀會讓第一個 IP 變成 '﻿1.2.3.4'，送到測試網站直接失效。
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"找不到 IP 清單: {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        return [line.strip() for line in f if line.strip()]


def write_ips(path, ips: Iterable[str]) -> int:
    """覆寫 IP 清單，回傳寫入筆數。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ips = list(ips)
    with open(path, "w", encoding="utf-8") as f:
        for ip in ips:
            f.write(ip + "\n")
    return len(ips)


def split_batches(ips: List[str], size: int) -> List[List[str]]:
    """把 IP 清單切成每組 size 個。"""
    if size <= 0:
        raise ValueError(f"批次大小必須為正數: {size}")
    return [ips[i:i + size] for i in range(0, len(ips), size)]
