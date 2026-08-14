"""解析 itdog.cn 測試結果頁面。

純函式，不碰瀏覽器——想驗證解析邏輯，存一份 page_source 下來丟進來即可。
"""

from typing import List, Sequence

from bs4 import BeautifulSoup

from ..config import Node
from ..data.records import ResultRecord

UNREACHABLE = "无法访问"
UNKNOWN = "未知"


def parse_results(html: str, nodes: Sequence[Node], protocol: str) -> List[ResultRecord]:
    """從結果頁 HTML 抽出所有 (target, 節點, 狀態)。

    節點欄位在表格中的出現順序，對應 config.yaml 的 itdog.nodes 順序。
    """
    soup = BeautifulSoup(html, "html.parser")
    tbody = soup.find("tbody", attrs={"aria-live": "polite", "aria-relevant": "all"})
    if not tbody:
        return []

    records: List[ResultRecord] = []
    for row in tbody.find_all("tr", class_="node_tr"):
        target = _extract_target(row)
        for idx, cell in enumerate(row.find_all("td", class_="node_result")):
            node_name = nodes[idx].name if idx < len(nodes) else UNKNOWN
            records.append(ResultRecord.from_target(
                target=target,
                node=node_name,
                status=_extract_status(cell),
                protocol=protocol,
            ))
    return records


def _extract_target(row) -> str:
    """目標位址藏在 address-hidden 欄的 span title 裡。"""
    td = row.find("td", class_="address-hidden")
    if td:
        span = td.find("span")
        if span:
            return span.get("title", "Unknown")
    return "Unknown"


def _extract_status(cell) -> str:
    """「无法访问」是純文字，成功時狀態碼包在 badge 裡。"""
    if UNREACHABLE in cell.text:
        return UNREACHABLE
    badge = cell.find("span", class_="badge")
    return badge.text.strip() if badge else UNKNOWN
