"""tcptest.cn 測試——應用層流程。

兩種模式：

    batch   批量 TCPing（tcptest.cn/batch-tcping）
            data/CDN_IP_list.txt → logs/*.txt → data/tcping_table.xlsx
            同一批目標跑兩輪，HTTP 用 80 埠、HTTPS 用 443 埠。
            量的是端口延遲（1ms／响应超时），不是 HTTP 狀態碼。

    single  單站測速（tcptest.cn/http）
            一個網址 → data/single_<網址>.xlsx
            完整保留網站的所有欄位：狀態、總耗時、解析、連接、響應、重定向。

用法：
    python run_all.py batch
    python run_all.py single www.example.com
    python run_all.py single www.example.com --slow    # 改走「缓慢测试」，節點更多

本流程不碰 Google Sheets。
"""

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR.parent))

from busters import data                             # noqa: E402
from busters import tcptest                          # noqa: E402
from busters.config import AppConfig, load_config    # noqa: E402
from busters.data.records import HTTP, HTTPS         # noqa: E402

EXCEL_NAME = "tcping_table.xlsx"


def banner(text: str) -> None:
    print("\n" + "=" * 56)
    print(text)
    print("=" * 56)


def mode_batch(cfg: AppConfig) -> None:
    ips = data.read_ips(cfg.paths.ip_file)
    print(f"待測目標：{len(ips)} 個")

    if cfg.clear_logs_before_run:
        removed = data.clear_logs(cfg.paths.log_dir)
        if removed:
            print(f"已清除 {removed} 個舊 log")

    batches = data.split_batches(ips, cfg.tcptest.ip_split_count)
    for idx, batch in enumerate(batches, start=1):
        group_name = f"Group {idx}"
        for protocol in (HTTP, HTTPS):
            port = cfg.tcptest.port_for(protocol)
            print(f"\n--- {group_name} - {protocol.upper()}"
                  f"（{len(batch)} 個目標，{port} 埠）---")

            nodes, records = tcptest.run_batch(batch, protocol, cfg.tcptest)
            if not records:
                print("沒有解析到任何結果")
                continue

            print(f"本輪節點：{', '.join(nodes)}")
            path = data.write_log(cfg.paths.log_dir, group_name, protocol, records)
            print(f"已寫入 {len(records)} 筆 → {path.name}")

    records = data.read_logs(cfg.paths.log_dir)
    print(f"\n從 log 讀回 {len(records)} 筆結果")
    if not records:
        print("沒有結果可產出報表")
        return

    output = data.generate_dynamic_report(
        records, ips, cfg.paths.project_dir / "data" / EXCEL_NAME
    )
    print(f"已產出報表: {output}")


def mode_single(cfg: AppConfig, url: str, slow: bool) -> None:
    print(f"測試目標：{url}（{'缓慢' if slow else '快速'}測試）")

    columns, probes = tcptest.run_single(url, cfg.tcptest, slow=slow)
    if not probes:
        print("沒有解析到任何節點結果")
        return

    print(f"取得 {len(probes)} 個節點、{len(columns)} 個欄位")
    print(f"欄位：{', '.join(columns)}")

    output = data.save_site_report(cfg.paths.single_report(url), columns, probes)
    print(f"已產出報表: {output}")

    statuses = [p.values.get("状态", "") for p in probes]
    ok = sum(1 for s in statuses if s.startswith("2") or s.startswith("3"))
    print(f"摘要：{ok}/{len(statuses)} 個節點回應 2xx/3xx")


def main() -> None:
    parser = argparse.ArgumentParser(description="tcptest.cn 測試流程")
    parser.add_argument("mode", choices=["batch", "single"], help="測試模式")
    parser.add_argument("url", nargs="?", help="single 模式要測的網址")
    parser.add_argument("--slow", action="store_true",
                        help="single 模式改走「缓慢测试」，節點更多但較慢")
    args = parser.parse_args()

    if args.mode == "single" and not args.url:
        parser.error("single 模式需要指定網址，例如：python run_all.py single www.example.com")

    cfg = load_config(PROJECT_DIR)

    if args.mode == "batch":
        banner("tcptest 批量 TCPing")
        mode_batch(cfg)
    else:
        banner("tcptest 單站測速")
        mode_single(cfg, args.url, args.slow)

    banner("完成！")


if __name__ == "__main__":
    main()
