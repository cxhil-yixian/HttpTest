"""解析 tcptest.cn 的結果表。

純函式，不碰瀏覽器——存一份 page_source 下來就能離線驗證。

批量（tcping）結果表：
    表頭 = 序号 | 检测目标：端口 | <節點1> | <節點2> | …
    每格 = <div>1ms 或 响应超时</div><div>响应IP：…</div><div>位置：…</div>
    節點名稱每次測試由網站隨機分配，所以從表頭讀，不從設定讀。

單站結果表：
    表頭 = 检测点 | 响应IP | IP位置 | 状态 | 总耗时 | 解析 | 连接 | 响应 | 重定向 | Head | 赞助商
"""

from typing import List, Optional, Sequence, Tuple

from bs4 import BeautifulSoup

from ..data.records import ResultRecord, SiteProbe, bare_ip

TIMEOUT = "响应超时"

# 這兩欄不是量測資料：赞助商是廣告，Head 是一顆「查看」按鈕
SINGLE_DROP_COLUMNS = ("赞助商", "Head")

_RESP_IP_PREFIX = "响应IP："
_LOCATION_PREFIX = "位置："


def _tables(soup) -> List:
    return soup.find_all("table")


def _headers(table) -> List[str]:
    head = table.find("thead")
    if not head:
        return []
    return [th.get_text(strip=True) for th in head.find_all(["th", "td"])]


def _find_table(soup, required: Sequence[str]) -> Optional[Tuple[List[str], object]]:
    """找出表頭包含所有指定字串的表。"""
    for table in _tables(soup):
        headers = _headers(table)
        joined = "".join(headers)
        if all(r in joined for r in required):
            return headers, table
    return None


def _body_rows(table) -> List:
    body = table.find("tbody")
    return body.find_all("tr") if body else []


# ---------- 批量（tcping） ----------

def parse_batch(html: str, protocol: str) -> Tuple[List[str], List[ResultRecord]]:
    """回傳 (節點名稱清單, 結果紀錄)。節點順序即表頭順序。"""
    soup = BeautifulSoup(html, "html.parser")
    found = _find_table(soup, ("序号", "检测目标"))
    if not found:
        return [], []

    headers, table = found
    nodes = [h for h in headers[2:] if h]

    records: List[ResultRecord] = []
    for row in _body_rows(table):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue

        target = _target_of(cells[1])
        if not target:
            continue

        for idx, cell in enumerate(cells[2:]):
            if idx >= len(nodes):
                break
            status, resp_ip, location = _cell_of(cell)
            records.append(ResultRecord(
                ip=bare_ip(target),   # 去掉端口才能跟 IP 清單比對
                node=nodes[idx],
                status=status,
                protocol=protocol,
                target=target,
                response_ip=resp_ip,
                location=location,
            ))
    return nodes, records


def _target_of(cell) -> str:
    """目標欄裡除了文字還有一顆快捷操作按鈕，取第一個 span 的文字即可。"""
    span = cell.find("span")
    text = span.get_text(strip=True) if span else cell.get_text(strip=True)
    return text.strip()


def _cell_of(cell) -> Tuple[str, str, str]:
    """一格拆成 (狀態, 回應IP, 位置)。狀態是延遲如 1ms，或「响应超时」。"""
    divs = cell.find_all("div")
    if not divs:
        return cell.get_text(strip=True), "", ""

    status = divs[0].get_text(strip=True)
    resp_ip = ""
    location = ""
    for d in divs[1:]:
        text = d.get_text(strip=True)
        if text.startswith(_RESP_IP_PREFIX):
            resp_ip = text[len(_RESP_IP_PREFIX):]
        elif text.startswith(_LOCATION_PREFIX):
            location = text[len(_LOCATION_PREFIX):]
    return status, resp_ip, location


# ---------- 單站 ----------

def parse_single(html: str, target: str) -> Tuple[List[str], List[SiteProbe]]:
    """回傳 (欄位名稱清單, 每個節點一筆的量測)。"""
    soup = BeautifulSoup(html, "html.parser")
    found = _find_table(soup, ("检测点", "状态", "总耗时"))
    if not found:
        return [], []

    headers, table = found
    keep = [(i, h) for i, h in enumerate(headers) if h and h not in SINGLE_DROP_COLUMNS]
    columns = [h for _, h in keep]

    probes: List[SiteProbe] = []
    for row in _body_rows(table):
        cells = row.find_all("td")
        if len(cells) < len(headers) - len(SINGLE_DROP_COLUMNS):
            continue

        values = {}
        for i, name in keep:
            if i >= len(cells):
                continue
            values[name] = (_node_of(cells[i]) if name == "检测点"
                            else cells[i].get_text(strip=True))

        node = values.get("检测点", "")
        if not node:
            continue
        probes.append(SiteProbe(target=target, node=node, values=values))

    return columns, probes


def _node_of(cell) -> str:
    """检测点是「運營商徽章 + 地點」兩個 span，中間補一個空格才讀得出來。"""
    spans = cell.find_all("span")
    parts = [s.get_text(strip=True) for s in spans if s.get_text(strip=True)]
    if parts:
        return " ".join(parts)
    return cell.get_text(strip=True)
