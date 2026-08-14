"""設定載入。

config.yaml 放結構性常數（節點、欄位、等待秒數），
.env 放部署相關與機密（Sheet ID、gid、憑證路徑）。

各專案（ITDOG-busters / TCPTEST-busters）共用同一份 config.yaml 與 .env，
但 data/ 與 logs/ 各自獨立，由 load_config(project_dir) 決定。
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from dotenv import load_dotenv

# 專案根目錄 = busters/ 的上一層
REPO_ROOT = Path(__file__).resolve().parent.parent

CONFIG_FILE = REPO_ROOT / "config.yaml"
ENV_FILE = REPO_ROOT / ".env"


def column_index(letter: str) -> int:
    """欄位字母轉 0-based 索引：A→0, D→3, L→11, AA→26"""
    idx = 0
    for ch in letter.strip().upper():
        if not ch.isalpha():
            raise ValueError(f"無效的欄位字母: {letter!r}")
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    if idx == 0:
        raise ValueError(f"無效的欄位字母: {letter!r}")
    return idx - 1


def column_letter(index: int) -> str:
    """0-based 索引轉欄位字母：0→A, 3→D, 11→L"""
    if index < 0:
        raise ValueError(f"欄位索引不可為負: {index}")
    letters = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


@dataclass(frozen=True)
class Node:
    """一個測試節點。"""

    id: str      # 網站上的節點 ID
    name: str    # 網站回傳的節點名稱，同時是寫進 log 的名稱
    label: str   # 報表表頭簡稱


@dataclass(frozen=True)
class ItdogConfig:
    """itdog.cn。節點固定，由設定檔指定 ID。"""

    batch_url: str
    single_url: str
    ip_split_count: int
    test_wait_time: int
    headless: bool
    challenge_wait: int
    nodes: Tuple[Node, ...]

    @property
    def node_ids(self) -> List[str]:
        return [n.id for n in self.nodes]

    @property
    def node_names(self) -> List[str]:
        return [n.name for n in self.nodes]


@dataclass(frozen=True)
class TcptestConfig:
    """tcptest.cn。節點由網站隨機分配，只能從結果表頭讀回，故此處無節點清單。"""

    batch_url: str
    single_url: str
    ip_split_count: int
    test_wait_time: int
    headless: bool
    ports: Dict[str, int]

    def port_for(self, protocol: str) -> int:
        return int(self.ports.get(protocol, 80))


@dataclass(frozen=True)
class ReportLayout:
    """Excel 報表的欄位配置。節點依序往右展開。"""

    ip_column: str
    http_start_column: str
    https_start_column: str
    node_count: int

    @property
    def ip_index(self) -> int:
        return column_index(self.ip_column)

    @property
    def http_index(self) -> int:
        return column_index(self.http_start_column)

    @property
    def https_index(self) -> int:
        return column_index(self.https_start_column)

    @property
    def width(self) -> int:
        """報表總欄數（含中間留白欄）。"""
        return max(
            self.ip_index,
            self.http_index + self.node_count - 1,
            self.https_index + self.node_count - 1,
        ) + 1


@dataclass(frozen=True)
class SheetsConfig:
    sheet_id: str
    worksheet_gid: int
    credentials_path: Path
    ip_column: str
    start_row: int
    http_start_column: str
    https_start_column: str


@dataclass(frozen=True)
class Paths:
    """單一專案的資料檔位置。"""

    project_dir: Path
    ip_file: Path
    log_dir: Path
    excel_file: Path

    def single_report(self, target: str) -> Path:
        """單站測試的獨立報表路徑。網址中不能當檔名的字元一律換成底線。"""
        safe = "".join(c if c.isalnum() or c in "-._" else "_" for c in target)
        return self.project_dir / "data" / f"single_{safe}.xlsx"


@dataclass(frozen=True)
class AppConfig:
    itdog: ItdogConfig
    tcptest: TcptestConfig
    layout: ReportLayout
    clear_logs_before_run: bool
    sheets: SheetsConfig
    paths: Paths


def load_config(project_dir) -> AppConfig:
    """載入 config.yaml + .env，組出指定專案的完整設定。

    project_dir: 應用層專案目錄（例如 ITDOG-busters/），data/ 與 logs/ 位於其下。
    """
    project_dir = Path(project_dir).resolve()

    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"找不到設定檔: {CONFIG_FILE}")

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    load_dotenv(ENV_FILE)

    itdog_raw = raw.get("itdog", {})
    nodes = tuple(
        Node(id=str(n["id"]), name=n["name"], label=n["label"])
        for n in itdog_raw.get("nodes", [])
    )
    if not nodes:
        raise ValueError("config.yaml 的 itdog.nodes 是空的")

    itdog = ItdogConfig(
        batch_url=itdog_raw.get("batch_url", "https://www.itdog.cn/batch_http/"),
        single_url=itdog_raw.get("single_url", "https://www.itdog.cn/http/"),
        ip_split_count=int(itdog_raw.get("ip_split_count", 250)),
        test_wait_time=int(itdog_raw.get("test_wait_time", 60)),
        headless=bool(itdog_raw.get("headless", False)),
        challenge_wait=int(itdog_raw.get("challenge_wait", 180)),
        nodes=nodes,
    )

    tcptest_raw = raw.get("tcptest", {})
    tcptest = TcptestConfig(
        batch_url=tcptest_raw.get("batch_url", "https://www.tcptest.cn/batch-tcping"),
        single_url=tcptest_raw.get("single_url", "https://www.tcptest.cn/http"),
        ip_split_count=int(tcptest_raw.get("ip_split_count", 256)),
        test_wait_time=int(tcptest_raw.get("test_wait_time", 120)),
        headless=bool(tcptest_raw.get("headless", False)),
        ports={k: int(v) for k, v in (tcptest_raw.get("ports") or {"http": 80, "https": 443}).items()},
    )

    data_raw = raw.get("data", {})
    report_raw = data_raw.get("report", {})
    layout = ReportLayout(
        ip_column=report_raw.get("ip_column", "C"),
        http_start_column=report_raw.get("http_start_column", "D"),
        https_start_column=report_raw.get("https_start_column", "L"),
        node_count=len(nodes),
    )

    google_raw = raw.get("google", {})
    sheet_id = os.getenv("SHEET_ID", "")
    gid = os.getenv("WORKSHEET_GID", "")
    creds = os.getenv("GOOGLE_CREDENTIALS", "service_account.json")
    creds_path = Path(creds)
    if not creds_path.is_absolute():
        creds_path = REPO_ROOT / creds_path

    sheets = SheetsConfig(
        sheet_id=sheet_id,
        worksheet_gid=int(gid) if gid else 0,
        credentials_path=creds_path,
        ip_column=google_raw.get("ip_column", "C"),
        start_row=int(google_raw.get("start_row", 4)),
        http_start_column=google_raw.get("http_start_column", "D"),
        https_start_column=google_raw.get("https_start_column", "L"),
    )

    paths = Paths(
        project_dir=project_dir,
        ip_file=project_dir / "data" / "CDN_IP_list.txt",
        log_dir=project_dir / "logs",
        excel_file=project_dir / "data" / "inaccessible_table.xlsx",
    )

    return AppConfig(
        itdog=itdog,
        tcptest=tcptest,
        layout=layout,
        clear_logs_before_run=bool(data_raw.get("clear_logs_before_run", True)),
        sheets=sheets,
        paths=paths,
    )
