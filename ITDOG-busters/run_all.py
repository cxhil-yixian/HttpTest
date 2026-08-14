"""ITDOG 批量測試——應用層流程。

三個步驟，各自以檔案為交接點，可以單獨重跑：

    fetch  : Google Sheets            → data/CDN_IP_list.txt
    test   : data/CDN_IP_list.txt     → logs/*.txt → data/inaccessible_table.xlsx
    upload : data/inaccessible_table.xlsx → Google Sheets

用法：
    python run_all.py                # 跑完整流程
    python run_all.py fetch          # 只同步 IP 清單
    python run_all.py test           # 只跑測試並產出 Excel
    python run_all.py upload         # 只回寫 Sheets
    python run_all.py test upload    # 跑指定的幾步

fetch 與 upload 受 config.yaml 的 google.enabled 控制。關閉時（目前預設）
不跑完整流程會自動跳過這兩步，只做 test；明確點名要跑則會直接報錯說明原因。
"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR.parent))  # 讓 busters 套件可被匯入

from busters import data                            # noqa: E402
from busters.config import AppConfig, load_config   # noqa: E402
from busters.data.records import HTTP, HTTPS        # noqa: E402
from busters.itdog import run_batch                 # noqa: E402


def banner(text: str) -> None:
    print("\n" + "=" * 50)
    print(text)
    print("=" * 50)


def step_fetch(cfg: AppConfig) -> None:
    """Google Sheets → data/CDN_IP_list.txt"""
    from busters import google   # 延後匯入：關閉時連 gspread 都不必載入

    worksheet = google.open_worksheet(cfg.sheets)
    print(f"已連接工作表: {worksheet.title}")

    ips = google.read_column(worksheet, cfg.sheets.ip_column, cfg.sheets.start_row)
    if not ips:
        raise RuntimeError("Sheets 上沒有讀到任何 IP，中止以免覆蓋既有清單")

    count = data.write_ips(cfg.paths.ip_file, ips)
    print(f"讀取到 {count} 個 IP，已更新 {cfg.paths.ip_file}")


def step_test(cfg: AppConfig) -> None:
    """data/CDN_IP_list.txt → logs/*.txt → Excel 報表"""
    ips = data.read_ips(cfg.paths.ip_file)
    print(f"待測 IP：{len(ips)} 個")

    if cfg.clear_logs_before_run:
        removed = data.clear_logs(cfg.paths.log_dir)
        if removed:
            print(f"已清除 {removed} 個舊 log")

    batches = data.split_batches(ips, cfg.itdog.ip_split_count)
    for idx, batch in enumerate(batches, start=1):
        group_name = f"Group {idx}"
        for protocol in (HTTP, HTTPS):
            print(f"\n--- {group_name} - {protocol.upper()}（{len(batch)} 個 IP）---")
            records = run_batch(batch, protocol, cfg.itdog)
            if not records:
                print("沒有解析到任何結果")
                continue
            path = data.write_log(cfg.paths.log_dir, group_name, protocol, records)
            print(f"已寫入 {len(records)} 筆 → {path.name}")

    records = data.read_logs(cfg.paths.log_dir)
    print(f"\n從 log 讀回 {len(records)} 筆結果")

    output = data.generate_report(
        records, ips, cfg.layout, cfg.itdog.nodes, cfg.paths.excel_file
    )
    print(f"已產出報表: {output}")


def step_upload(cfg: AppConfig) -> None:
    """Excel 報表 → Google Sheets"""
    from busters import google   # 延後匯入：關閉時連 gspread 都不必載入

    http_grid, https_grid = data.load_result_grids(cfg.paths.excel_file, cfg.layout)
    print(f"讀取到 HTTP {len(http_grid)} 行、HTTPS {len(https_grid)} 行")

    worksheet = google.open_worksheet(cfg.sheets)
    print(f"已連接工作表: {worksheet.title}")

    for label, grid, start_col in (
        ("HTTP", http_grid, cfg.sheets.http_start_column),
        ("HTTPS", https_grid, cfg.sheets.https_start_column),
    ):
        written = google.write_grid(worksheet, grid, start_col, cfg.sheets.start_row)
        if written:
            print(f"已寫入 {label} 資料到 {written}")


# needs_google=True 的步驟受 config.yaml 的 google.enabled 控制
STEPS = {
    "fetch": ("1. 從 Google Sheets 讀取 IP", step_fetch, True),
    "test": ("2. 執行 ITDOG 批量測試", step_test, False),
    "upload": ("3. 上傳結果到 Google Sheets", step_upload, True),
}

GOOGLE_OFF_HINT = ("Google Sheets 目前是關閉的"
                   "（config.yaml 的 google.enabled: false）")


def main() -> None:
    parser = argparse.ArgumentParser(description="ITDOG 批量測試流程")
    parser.add_argument(
        "steps", nargs="*", choices=list(STEPS), metavar="STEP",
        help=f"要執行的步驟（可多選）：{', '.join(STEPS)}；不指定則全部執行",
    )
    args = parser.parse_args()

    explicit = bool(args.steps)
    selected = args.steps or list(STEPS)
    cfg = load_config(PROJECT_DIR)

    if not cfg.sheets.enabled:
        blocked = [s for s in selected if STEPS[s][2]]
        if blocked and explicit:
            # 明確點名要跑的步驟就不要默默跳過，講清楚為什麼沒跑
            parser.error(
                f"{GOOGLE_OFF_HINT}，無法執行 {', '.join(blocked)}。\n"
                f"要接回 Google Sheets 請把 google.enabled 改成 true。"
            )
        selected = [s for s in selected if not STEPS[s][2]]
        if blocked:
            print(f"\n※ {GOOGLE_OFF_HINT}，跳過：{', '.join(blocked)}")

    if not selected:
        print("沒有可執行的步驟")
        return

    for name in selected:
        title, func, _ = STEPS[name]
        banner(title)
        func(cfg)

    banner("全部完成！")


if __name__ == "__main__":
    main()
