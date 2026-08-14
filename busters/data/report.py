"""報表排版與 Excel 讀寫。

排版知識集中在這裡：哪一欄放 IP、HTTP 結果從哪一欄開始、節點依什麼順序展開。
GOOGLE 模組只收本模組排好的二維陣列，不需要知道欄位怎麼排。
"""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd

from ..config import Node, ReportLayout
from .records import HTTPS, ResultRecord


def build_headers(layout: ReportLayout, nodes: Sequence[Node]) -> List[str]:
    """組出表頭。未使用的欄位留空字串。"""
    headers = [""] * layout.width
    headers[layout.ip_index] = "節點IP"
    for i, node in enumerate(nodes):
        headers[layout.http_index + i] = f"http{node.label}"
        headers[layout.https_index + i] = f"https{node.label}"
    return headers


def build_rows(records: Sequence[ResultRecord], ips: Sequence[str],
               layout: ReportLayout, nodes: Sequence[Node]) -> List[List[str]]:
    """把結果紀錄攤平成報表列，順序依照 ips 清單。

    只輸出在 records 中出現過的 IP——沒測到結果的 IP 不佔一列，
    這樣回寫 Sheets 時列號才會對得上原本的 IP 欄。
    """
    node_position = {node.name: i for i, node in enumerate(nodes)}

    cells: Dict[str, List[str]] = {}
    for r in records:
        pos = node_position.get(r.node)
        if pos is None:
            continue  # 節點不在設定裡，忽略
        row = cells.setdefault(r.ip, [""] * layout.width)
        base = layout.https_index if r.protocol == HTTPS else layout.http_index
        row[base + pos] = r.status

    rows: List[List[str]] = []
    for ip in ips:
        if ip not in cells:
            continue
        row = cells[ip]
        row[layout.ip_index] = ip
        rows.append(row)
    return rows


def save_excel(path, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> Path:
    """寫出 Excel 報表。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(list(rows), columns=list(headers))
    df.to_excel(path, index=False)
    return path


def generate_report(records: Sequence[ResultRecord], ips: Sequence[str],
                    layout: ReportLayout, nodes: Sequence[Node],
                    output_path) -> Path:
    """records + IP 順序 → Excel 報表。"""
    headers = build_headers(layout, nodes)
    rows = build_rows(records, ips, layout, nodes)
    return save_excel(output_path, headers, rows)


def load_result_grids(excel_path, layout: ReportLayout
                      ) -> Tuple[List[List[str]], List[List[str]]]:
    """從 Excel 讀出 (HTTP 區塊, HTTPS 區塊) 兩個二維陣列，供 GOOGLE 模組直接貼上。

    空值一律轉成空字串——gspread 不接受 NaN。
    """
    excel_path = Path(excel_path)
    if not excel_path.exists():
        raise FileNotFoundError(f"找不到報表: {excel_path}")

    df = pd.read_excel(excel_path)
    n = layout.node_count

    def block(start: int) -> List[List[str]]:
        sliced = df.iloc[:, start:start + n].values.tolist()
        return [["" if pd.isna(c) else str(c) for c in row] for row in sliced]

    return block(layout.http_index), block(layout.https_index)
