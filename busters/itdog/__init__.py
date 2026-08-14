"""ITDOG 模組——itdog.cn 批量測試採集。

網站專屬邏輯全部收在這裡：Selenium 操作（collector）與 HTML 解析（parser）。
對外只暴露「一批 IP + 協議 → ResultRecord 清單」。
"""

from .challenge import require_form, wait_for_form
from .collector import build_targets, run_batch
from .parser import parse_results

__all__ = ["build_targets", "run_batch", "parse_results",
           "require_form", "wait_for_form"]
