"""測試結果的資料形狀。

兩種模式產出兩種形狀：
    ResultRecord — 批量模式：一個目標 × 一個節點 → 一格狀態
    SiteProbe    — 單站模式：一個網址 × 一個節點 → 多欄指標
"""

from dataclasses import dataclass, field
from typing import Dict

HTTP = "http"
HTTPS = "https"


def strip_scheme(target: str) -> str:
    """把 https://1.2.3.4 還原成 1.2.3.4"""
    for prefix in ("https://", "http://"):
        if target.startswith(prefix):
            return target[len(prefix):]
    return target


def strip_port(target: str) -> str:
    """把 1.2.3.4:443 還原成 1.2.3.4。IPv6 或無端口的字串原樣回傳。"""
    head, sep, tail = target.rpartition(":")
    if sep and head and tail.isdigit() and ":" not in head:
        return head
    return target


def bare_ip(target: str) -> str:
    """去掉 scheme 與端口，只留可以跟 IP 清單比對的部分。"""
    return strip_port(strip_scheme(target))


@dataclass(frozen=True)
class ResultRecord:
    """單一 IP 在單一節點上、單一協議的測試結果。

    ip       : 純 IP，不含 scheme——報表比對一律用這個
    node     : 節點名稱，需與 config.yaml 的 itdog.nodes[].name 一致
    status   : HTTP 狀態碼字串，或「无法访问」等網站原文
    protocol : HTTP 或 HTTPS
    target   : 送進測試網站、也寫回 log 的原始字串（HTTPS 時帶 https:// 前綴）。
               保留它是為了讓 log 檔格式與模組化之前完全一致。
    """

    ip: str
    node: str
    status: str
    protocol: str
    target: str = ""
    response_ip: str = ""   # tcping 才有：實際回應的 IP:port
    location: str = ""      # tcping 才有：回應 IP 的地理位置

    @classmethod
    def from_target(cls, target: str, node: str, status: str, protocol: str,
                    response_ip: str = "", location: str = ""):
        """由網站回傳的原始 target 建立紀錄。"""
        return cls(
            ip=strip_scheme(target),
            node=node,
            status=status,
            protocol=protocol,
            target=target,
            response_ip=response_ip,
            location=location,
        )

    @property
    def log_target(self) -> str:
        return self.target or self.ip


@dataclass(frozen=True)
class SiteProbe:
    """單站測試中，一個節點對一個網址的一次完整量測。

    values 直接保留網站原本的欄位名稱與值（检测点、响应IP、状态、总耗时…），
    不做正規化——單站模式的價值就在於完整的原始指標。
    """

    target: str
    node: str
    values: Dict[str, str] = field(default_factory=dict)
