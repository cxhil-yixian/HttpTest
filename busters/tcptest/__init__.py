"""TCPTEST 模組——tcptest.cn 測試採集。

兩種模式：
    batch  — 批量 TCPing（端口延遲），tcptest.cn/batch-tcping
    single — 單站測速（多欄指標），tcptest.cn/http

與 busters/itdog/ 介面一致，DATA 與 GOOGLE 兩個模組不需為此改動。

與 itdog 的兩個實質差異：
1. 節點由網站隨機分配，名稱只能從結果表頭讀回，不寫在設定檔裡。
2. 批量模式量的是 TCP 延遲（1ms／响应超时），不是 HTTP 狀態碼。
"""

from .batch import build_targets, run_batch
from .parser import parse_batch, parse_single
from .single import run_single

__all__ = ["build_targets", "run_batch", "run_single", "parse_batch", "parse_single"]
