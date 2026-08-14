"""測試日誌檔的讀寫（logs/Group N - HTTP.txt）。

檔案是資料流的唯一通道：採集模組只負責寫 log，報表模組只負責讀 log。
格式為每行「target 節點名 狀態」，以空白分隔；HTTPS 的 target 帶 https:// 前綴。
"""

from pathlib import Path
from typing import Iterable, List

from .records import HTTP, HTTPS, ResultRecord, strip_scheme


def log_filename(group_name: str, protocol: str) -> str:
    """logs/ 內的檔名慣例。protocol 需為 http 或 https。"""
    return f"{group_name} - {protocol.upper()}.txt"


def protocol_of(filename: str) -> str:
    """從檔名判斷協議。判斷順序不可顛倒——HTTPS 必須先比對。"""
    upper = filename.upper()
    if "HTTPS" in upper:
        return HTTPS
    if "HTTP" in upper:
        return HTTP
    return ""


def clear_logs(log_dir) -> int:
    """刪除 logs/ 內既有的 *.txt，回傳刪除數量。

    不清的話，上一輪殘留的 log（例如上次 IP 較多、這次少了一組）
    會被算進這次的報表。
    """
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return 0
    removed = 0
    for f in log_dir.glob("*.txt"):
        f.unlink()
        removed += 1
    return removed


def write_log(log_dir, group_name: str, protocol: str,
              records: Iterable[ResultRecord]) -> Path:
    """把一組測試結果寫成一個 log 檔，回傳檔案路徑。"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / log_filename(group_name, protocol)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(f"{r.log_target} {r.node} {r.status}\n")
    return path


def read_logs(log_dir) -> List[ResultRecord]:
    """讀回 logs/ 內所有 *.txt，合併成一份結果清單。"""
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return []

    records: List[ResultRecord] = []
    for path in sorted(log_dir.glob("*.txt")):
        protocol = protocol_of(path.name)
        if not protocol:
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(" ")
                if len(parts) < 3:
                    continue
                records.append(ResultRecord(
                    ip=strip_scheme(parts[0]),
                    node=parts[1],
                    status=parts[2],
                    protocol=protocol,
                    target=parts[0],
                ))
    return records
