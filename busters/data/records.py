"""測試結果的資料形狀。"""

from dataclasses import dataclass

HTTP = "http"
HTTPS = "https"


def strip_scheme(target: str) -> str:
    """把 https://1.2.3.4 還原成 1.2.3.4"""
    for prefix in ("https://", "http://"):
        if target.startswith(prefix):
            return target[len(prefix):]
    return target


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

    @classmethod
    def from_target(cls, target: str, node: str, status: str, protocol: str):
        """由網站回傳的原始 target 建立紀錄。"""
        return cls(
            ip=strip_scheme(target),
            node=node,
            status=status,
            protocol=protocol,
            target=target,
        )

    @property
    def log_target(self) -> str:
        return self.target or self.ip
