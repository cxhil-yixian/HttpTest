"""測試日誌檔的讀寫（logs/Group N - HTTP.txt）。

檔案是資料流的唯一通道：採集模組只負責寫 log，報表模組只負責讀 log。
格式為每行「target 節點名 狀態」，以空白分隔；HTTPS 的 target 帶 https:// 前綴。
"""

from pathlib import Path
from typing import Iterable, List

from .records import HTTP, HTTPS, ResultRecord, bare_ip


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
        with open(path, "r", encoding="utf-8-sig") as f:
            for line in f:
                parsed = parse_line(line, protocol)
                if parsed:
                    records.append(parsed)
    return records


def parse_line(line: str, protocol: str):
    """解析一行 log：第一段是 target，最後一段是 status，中間全是節點名。

    不能直接 split(' ')[1] 當節點——tcptest 的節點名帶空格（「湖北襄阳 电信」），
    那樣會把節點切一半、把運營商當成狀態。itdog 的單字節點名結果不變。
    """
    line = line.strip()
    if not line:
        return None

    target, sep, rest = line.partition(" ")
    if not sep:
        return None

    node, sep2, status = rest.rpartition(" ")
    if not sep2 or not node or not status:
        return None

    return ResultRecord(
        ip=bare_ip(target),
        node=node,
        status=status,
        protocol=protocol,
        target=target,
    )
