"""報表排版與 Excel 讀寫。

排版知識集中在這裡：哪一欄放 IP、HTTP 結果從哪一欄開始、節點依什麼順序展開。
GOOGLE 模組只收本模組排好的二維陣列，不需要知道欄位怎麼排。
"""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple, Union

import pandas as pd

from ..config import Node, ReportLayout, column_index, column_letter
from .records import HTTP, HTTPS, ResultRecord, SiteProbe

# 節點可以是設定檔來的 Node（itdog），也可以是網站回傳的字串（tcptest）
NodeLike = Union[Node, str]


def node_name(node: NodeLike) -> str:
    """比對用的名稱——必須跟 log 裡寫的節點名一致。"""
    return node if isinstance(node, str) else node.name


def node_label(node: NodeLike) -> str:
    """表頭用的簡稱。tcptest 沒有簡稱，直接用完整節點名。"""
    return node if isinstance(node, str) else node.label


def build_headers(layout: ReportLayout, nodes: Sequence[NodeLike]) -> List[str]:
    """組出表頭。未使用的欄位留空字串。"""
    headers = [""] * layout.width
    headers[layout.ip_index] = "節點IP"
    for i, node in enumerate(nodes):
        label = node_label(node)
        headers[layout.http_index + i] = f"http{label}"
        headers[layout.https_index + i] = f"https{label}"
    return headers


def build_rows(records: Sequence[ResultRecord], ips: Sequence[str],
               layout: ReportLayout, nodes: Sequence[NodeLike]) -> List[List[str]]:
    """把結果紀錄攤平成報表列，順序依照 ips 清單。

    只輸出在 records 中出現過的 IP——沒測到結果的 IP 不佔一列，
    這樣回寫 Sheets 時列號才會對得上原本的 IP 欄。
    """
    node_position = {node_name(node): i for i, node in enumerate(nodes)}

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
                    layout: ReportLayout, nodes: Sequence[NodeLike],
                    output_path) -> Path:
    """records + IP 順序 → Excel 報表。"""
    headers = build_headers(layout, nodes)
    rows = build_rows(records, ips, layout, nodes)
    return save_excel(output_path, headers, rows)


def save_site_report(path, columns: Sequence[str], probes: Sequence[SiteProbe]) -> Path:
    """單站測試的完整報表：一列一個節點，欄位照網站原本的名稱全數保留。

    批量報表是「IP × 節點 → 一格」的矩陣，單站是「節點 × 多欄指標」的明細，
    兩者形狀不同，所以各走各的寫檔路徑。
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = [[p.values.get(col, "") for col in columns] for p in probes]
    df = pd.DataFrame(rows, columns=list(columns))
    df.to_excel(path, index=False)
    return path


def nodes_in(records: Sequence[ResultRecord], protocol: str) -> List[str]:
    """依出現順序取出某個協議用到的節點名稱，去重不排序。"""
    seen = []
    for r in records:
        if r.protocol == protocol and r.node and r.node not in seen:
            seen.append(r.node)
    return seen


def generate_dynamic_report(records: Sequence[ResultRecord], ips: Sequence[str],
                            output_path, ip_column: str = "C",
                            http_start_column: str = "D", gap: int = 3) -> Path:
    """節點清單由結果決定的批量報表。

    tcptest 每次測試的節點是網站隨機分配的，HTTP 那輪和 HTTPS 那輪
    甚至可能拿到不同節點，所以兩個區塊各自算欄位，不能共用一份對稱排版。
    """
    http_nodes = nodes_in(records, HTTP)
    https_nodes = nodes_in(records, HTTPS)

    ip_idx = column_index(ip_column)
    http_idx = column_index(http_start_column)
    https_idx = http_idx + len(http_nodes) + gap
    width = max(ip_idx, http_idx + len(http_nodes) - 1, https_idx + len(https_nodes) - 1) + 1

    headers = [""] * width
    headers[ip_idx] = "節點IP"
    for i, n in enumerate(http_nodes):
        headers[http_idx + i] = f"http {n}"
    for i, n in enumerate(https_nodes):
        headers[https_idx + i] = f"https {n}"

    http_pos = {n: i for i, n in enumerate(http_nodes)}
    https_pos = {n: i for i, n in enumerate(https_nodes)}

    cells: Dict[str, List[str]] = {}
    for r in records:
        base, pos_map = ((https_idx, https_pos) if r.protocol == HTTPS
                         else (http_idx, http_pos))
        pos = pos_map.get(r.node)
        if pos is None:
            continue
        cells.setdefault(r.ip, [""] * width)[base + pos] = r.status

    rows = []
    for ip in ips:
        if ip not in cells:
            continue
        row = cells[ip]
        row[ip_idx] = ip
        rows.append(row)

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
