# PySide6 UI 改版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 wxPython 介面改寫成 PySide6 的現代化桌面 App，提供 跟隨系統 / 淺色 / 深色 主題切換，並把邏輯抽成可測試的核心層。

**Architecture:** `src/core/` 放純邏輯（`ConnectionStore` 讀寫 `connections.profile`、`SoapService` 包裝 suds 呼叫與 XML 排版），不依賴 UI。`src/ui/` 以程式碼建構 PySide6 介面：`ThemeManager` 用色票 + QSS 樣板產生主題，`MainWindow` 組合左側 `ConnectionList` 與右側工作區，WebService 呼叫透過 `QThreadPool` 在背景執行。舊的 wx 介面保留到最後一個 Task 才移除，過程中舊版程式一直可以執行。

**Tech Stack:** Python 3.14、PySide6-Essentials 6.11、suds 1.2、lxml 6.1、loguru、pytest、PyInstaller 6.22、uv

**Spec:** `docs/superpowers/specs/2026-09-25-pyside6-ui-redesign-design.md`

## Global Constraints

- Python `>=3.14`；以 `uv` 管理依賴，所有指令以 `uv run` 執行
- Qt 只能依賴 `pyside6-essentials`（不可加入完整的 `pyside6` 或 GPL 的 Fluent 元件庫）；專案維持 MIT 授權
- `src/app_data/connections.profile` 的 JSON 格式不可變：`{"connections": [{"uuid", "name", "url", "method": [...]}]}`
- 不可修改 repo 內的 `src/app_data/connections.profile`（測試一律使用 `tmp_path` 或複製後的檔案）
- **含中文的檔案一律用 Write / Edit 工具建立或修改**，不可用 bash heredoc、`echo`、`printf`（這台 Windows 的 Git Bash 會寫出非 UTF-8 的內容）
- **Commit 訊息用繁體中文**：先用 Write 工具把訊息寫到 `C:\Users\game\AppData\Local\Temp\commit_msg.txt`，再執行 `git commit -F "C:/Users/game/AppData/Local/Temp/commit_msg.txt"`，完成後刪除該檔。每則訊息最後一行必須是 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（前面空一行）
- 新檔案開頭格式：`# -*- coding: utf-8 -*-` + 一段中文模組 docstring
- UI 文字、訊息內容必須與本計畫程式碼中的字串完全一致（測試會比對）
- 在 Task 10 之前不可移除 `wxpython` 依賴與舊 wx 程式碼
- 工作分支：`feat/pyside6-ui`

## File Structure

| 檔案 | 動作 | 職責 |
|---|---|---|
| `pyproject.toml` | 修改 | 新增依賴、pytest 設定；Task 10 移除 wxpython |
| `src/core/__init__.py` | 新增 | 核心邏輯套件 |
| `src/core/connection_store.py` | 新增 | `Connection`、`ConnectionStore` |
| `src/core/soap_service.py` | 新增 | `SoapService`、`CallResult`、`ParamCountMismatch`、`split_params`、`format_xml` |
| `src/ui/__init__.py` | 修改 | 移除對舊 wx 模組的匯入 |
| `src/ui/theme.py` | 新增 | 色票、QSS、`ThemeManager`、`repolish` |
| `src/ui/xml_editor.py` | 新增 | `XmlEditor`、`XmlHighlighter` |
| `src/ui/workers.py` | 新增 | `run_in_background` |
| `src/ui/notification_bar.py` | 新增 | `NotificationBar` |
| `src/ui/connection_list.py` | 新增 | `ConnectionList` 與清單項目元件 |
| `src/ui/main_window.py` | 新增 | `MainWindow`、`AboutInfo`、`format_size` |
| `src/ws_tool.py` | 修改 | Task 3 調整舊匯入；Task 10 改寫為 PySide6 進入點 |
| `src/app_data/ws_tool.yaml` | 修改 | 版本 `v2.0.0` |
| `tests/__init__.py`、`tests/conftest.py`、`tests/helpers.py` | 新增 | 測試環境 |
| `tests/fixtures/sample.wsdl` | 新增 | 本機 WSDL 測試檔 |
| `tests/test_*.py` | 新增 | 各模組測試 |
| `src/ui/main/`、`src/utils/darkmode.py`、`src/utils/toaster.py`、`src/utils/balloontip.py`、`fbp/` | 刪除（Task 10） | 舊 wx 介面 |
| `README.md` | 修改（Task 10） | 技術說明、開發與檢測工具用法 |

---

### Task 1: 依賴、測試環境與 ConnectionStore

**Files:**
- Modify: `pyproject.toml`
- Create: `src/core/__init__.py`, `src/core/connection_store.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_connection_store.py`

**Interfaces:**
- Consumes: `src.utils.uuidutil.get_uuid() -> uuid.UUID`（既有）
- Produces:
  - `Connection(uuid: str, name: str = "", url: str = "", methods: list[str] = [])`（dataclass，可比較相等）
  - `ConnectionStore(path: str | Path)`，屬性 `path: Path`、`backup_path: Path`、`recovered_from_corruption: bool`
  - `ConnectionStore.all() -> list[Connection]`、`get(uuid) -> Connection | None`、`add() -> Connection`、`remove(uuid)`、`rename(uuid, name)`、`set_url(uuid, url)`、`set_methods(uuid, methods)`；未知 uuid 丟 `KeyError`；回傳值都是副本
  - `tests/conftest.py` 的 session fixture `qapp`（offscreen `QApplication`）

- [ ] **Step 1: 加入依賴**

```bash
uv add pyside6-essentials
uv add --dev pytest pyqtinspect
```

Expected: `pyproject.toml` 的 `dependencies` 多了 `pyside6-essentials>=6.11.2`，`[dependency-groups] dev` 多了 `pytest`、`pyqtinspect`。

- [ ] **Step 2: 加入 pytest 設定**

在 `pyproject.toml` 檔尾加入：

```toml

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 3: 建立測試環境檔案**

`tests/__init__.py`：空檔案。

`tests/conftest.py`：

```python
# -*- coding: utf-8 -*-
"""
pytest 共用設定：所有 Qt 測試都在 offscreen 平台執行
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 4: 寫 ConnectionStore 的失敗測試**

`tests/test_connection_store.py`：

```python
# -*- coding: utf-8 -*-
import json
import shutil
from pathlib import Path

import pytest

from src.core.connection_store import Connection, ConnectionStore

REPO_PROFILE = Path(__file__).resolve().parents[1] / "src" / "app_data" / "connections.profile"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_missing_file_creates_empty_profile(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    assert store.all() == []
    assert read_json(path) == {"connections": []}
    assert store.recovered_from_corruption is False


def test_add_persists_blank_connection(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    conn = store.add()
    assert (conn.name, conn.url, conn.methods) == ("", "", [])
    assert len(conn.uuid) == 36
    assert read_json(path) == {"connections": [{"uuid": conn.uuid, "name": "", "url": "", "method": []}]}


def test_updates_persist_and_reload(tmp_path):
    path = tmp_path / "connections.profile"
    store = ConnectionStore(path)
    uuid = store.add().uuid
    store.rename(uuid, "TIPTOP 正式區")
    store.set_url(uuid, "http://host/ws?WSDL")
    store.set_methods(uuid, ["GetPOData", "AddTwo"])
    reloaded = ConnectionStore(path)
    assert reloaded.all() == [Connection(uuid, "TIPTOP 正式區", "http://host/ws?WSDL", ["GetPOData", "AddTwo"])]
    assert "TIPTOP 正式區" in path.read_text(encoding="utf-8")


def test_remove(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    first = store.add().uuid
    second = store.add().uuid
    store.remove(first)
    assert [conn.uuid for conn in store.all()] == [second]


def test_get_returns_none_for_unknown_uuid(tmp_path):
    assert ConnectionStore(tmp_path / "c.profile").get("nope") is None


@pytest.mark.parametrize("action", [
    lambda store: store.remove("nope"),
    lambda store: store.rename("nope", "x"),
    lambda store: store.set_url("nope", "x"),
    lambda store: store.set_methods("nope", []),
])
def test_unknown_uuid_raises_key_error(tmp_path, action):
    with pytest.raises(KeyError):
        action(ConnectionStore(tmp_path / "c.profile"))


def test_returned_connections_are_copies(tmp_path):
    store = ConnectionStore(tmp_path / "c.profile")
    uuid = store.add().uuid
    store.get(uuid).methods.append("Injected")
    store.all()[0].name = "changed"
    assert store.get(uuid) == Connection(uuid, "", "", [])


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text("{ not json", encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == []
    assert store.backup_path == tmp_path / "connections.profile.bak"
    assert store.backup_path.read_text(encoding="utf-8") == "{ not json"
    assert read_json(path) == {"connections": []}


def test_wrong_structure_is_treated_as_corrupt(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is True
    assert store.all() == []


def test_reads_legacy_profile(tmp_path):
    path = tmp_path / "connections.profile"
    legacy = {"connections": [{
        "uuid": "3151eae3-ffd2-4d24-9e11-2744aa103521",
        "name": "TIPTOP_TOPTEST",
        "url": "http://172.20.3.22/web/ws/r/aws_ttsrv2_toptest?WSDL",
        "method": ["CRMGetCustomerData", "GetPOData"],
    }]}
    path.write_text(json.dumps(legacy, indent=4), encoding="utf-8")
    store = ConnectionStore(path)
    assert store.all() == [Connection(
        "3151eae3-ffd2-4d24-9e11-2744aa103521",
        "TIPTOP_TOPTEST",
        "http://172.20.3.22/web/ws/r/aws_ttsrv2_toptest?WSDL",
        ["CRMGetCustomerData", "GetPOData"],
    )]
    assert store.recovered_from_corruption is False


def test_reads_repo_profile_copy(tmp_path):
    path = tmp_path / "connections.profile"
    shutil.copy(REPO_PROFILE, path)
    store = ConnectionStore(path)
    assert store.recovered_from_corruption is False
    assert store.all()
    assert all(conn.uuid for conn in store.all())


def test_blank_uuid_gets_generated(tmp_path):
    path = tmp_path / "connections.profile"
    path.write_text(json.dumps({"connections": [{"uuid": "", "name": "a", "url": "u", "method": []}]}), encoding="utf-8")
    store = ConnectionStore(path)
    uuid = store.all()[0].uuid
    assert len(uuid) == 36
    assert read_json(path)["connections"][0]["uuid"] == uuid
```

- [ ] **Step 5: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_store.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.core'`

- [ ] **Step 6: 實作 ConnectionStore**

`src/core/__init__.py`：

```python
# -*- coding: utf-8 -*-
"""
核心邏輯模組（不依賴 UI 框架）
"""
```

`src/core/connection_store.py`：

```python
# -*- coding: utf-8 -*-
"""
連線配置存取：讀寫 connections.profile
"""
import json
import os
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from loguru import logger

from src.utils import uuidutil


@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)


def _copy(conn: Connection) -> Connection:
    return replace(conn, methods=list(conn.methods))


def _new_uuid() -> str:
    return str(uuidutil.get_uuid())


class ConnectionStore:
    """連線配置的新增、刪除、修改，每次修改立即寫回檔案"""

    def __init__(self, path):
        self._path = Path(path)
        self._connections: list[Connection] = []
        self.recovered_from_corruption = False
        self._load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def backup_path(self) -> Path:
        return self._path.with_name(self._path.name + ".bak")

    def all(self) -> list[Connection]:
        return [_copy(conn) for conn in self._connections]

    def get(self, uuid: str) -> Connection | None:
        for conn in self._connections:
            if conn.uuid == uuid:
                return _copy(conn)
        return None

    def add(self) -> Connection:
        conn = Connection(uuid=_new_uuid())
        self._connections.append(conn)
        self._save()
        return _copy(conn)

    def remove(self, uuid: str) -> None:
        self._connections.remove(self._find(uuid))
        self._save()

    def rename(self, uuid: str, name: str) -> None:
        self._find(uuid).name = name
        self._save()

    def set_url(self, uuid: str, url: str) -> None:
        self._find(uuid).url = url
        self._save()

    def set_methods(self, uuid: str, methods: list[str]) -> None:
        self._find(uuid).methods = list(methods)
        self._save()

    def _find(self, uuid: str) -> Connection:
        for conn in self._connections:
            if conn.uuid == uuid:
                return conn
        raise KeyError(uuid)

    def _load(self) -> None:
        if not self._path.exists():
            self._save()
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._connections = [
                Connection(
                    uuid=item.get("uuid") or "",
                    name=item.get("name") or "",
                    url=item.get("url") or "",
                    methods=list(item.get("method") or []),
                )
                for item in data["connections"]
            ]
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            # JSONDecodeError、UnicodeDecodeError 都是 ValueError 的子類別
            logger.warning("連線設定檔無法讀取，備份為 {}: {}", self.backup_path, err)
            os.replace(self._path, self.backup_path)
            self._connections = []
            self.recovered_from_corruption = True
            self._save()
            return
        missing = [conn for conn in self._connections if not conn.uuid]
        for conn in missing:
            conn.uuid = _new_uuid()
        if missing:
            self._save()

    def _save(self) -> None:
        data = {"connections": [
            {"uuid": conn.uuid, "name": conn.name, "url": conn.url, "method": conn.methods}
            for conn in self._connections
        ]}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # 先寫暫存檔再取代，寫到一半當掉也不會毀損原檔
        fd, tmp_name = tempfile.mkstemp(prefix=self._path.name + ".", suffix=".tmp", dir=self._path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
```

- [ ] **Step 7: 執行測試確認通過**

Run: `uv run pytest tests/test_connection_store.py -v`
Expected: 全部 PASS（15 個測試）

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock src/core tests/__init__.py tests/conftest.py tests/test_connection_store.py
```

訊息：

```
新增 ConnectionStore 與 PySide6 / pytest 依賴

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 2: SoapService

**Files:**
- Create: `src/core/soap_service.py`
- Create: `tests/fixtures/sample.wsdl`
- Test: `tests/test_soap_service.py`

**Interfaces:**
- Produces:
  - `PARAM_SEPARATOR = "#~#"`
  - `CallResult(text: str, elapsed: float, size: int)`
  - `ParamCountMismatch(expected: int, actual: int)`（Exception，屬性 `expected`、`actual`；`str()` 為「此方法需要 {expected} 個參數，目前輸入 {actual} 個（多個參數請用 #~# 隔開）」）
  - `split_params(raw: str) -> list[str]`
  - `format_xml(text: str) -> str`（不合法丟 `ValueError`）
  - `SoapService(client_factory=...)`；`load_methods(url, timeout) -> list[str]`；`call(url, method, raw_params, timeout) -> CallResult`；未知方法丟 `ValueError`
  - `client_factory` 簽名：`(url: str, timeout: int) -> suds.client.Client`

- [ ] **Step 1: 建立 WSDL 測試檔**

`tests/fixtures/sample.wsdl`（純 ASCII，可用 Write 工具建立）：

```xml
<?xml version="1.0" encoding="utf-8"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema"
             xmlns:tns="http://example.com/ws"
             targetNamespace="http://example.com/ws">
  <types>
    <xsd:schema targetNamespace="http://example.com/ws" elementFormDefault="qualified">
      <xsd:element name="GetPODataRequest">
        <xsd:complexType><xsd:sequence>
          <xsd:element name="request" type="xsd:string"/>
        </xsd:sequence></xsd:complexType>
      </xsd:element>
      <xsd:element name="GetPODataResponse">
        <xsd:complexType><xsd:sequence>
          <xsd:element name="response" type="xsd:string"/>
        </xsd:sequence></xsd:complexType>
      </xsd:element>
      <xsd:element name="AddTwoRequest">
        <xsd:complexType><xsd:sequence>
          <xsd:element name="first" type="xsd:string"/>
          <xsd:element name="second" type="xsd:string"/>
        </xsd:sequence></xsd:complexType>
      </xsd:element>
      <xsd:element name="AddTwoResponse">
        <xsd:complexType><xsd:sequence>
          <xsd:element name="response" type="xsd:string"/>
        </xsd:sequence></xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </types>
  <message name="GetPODataIn"><part name="parameters" element="tns:GetPODataRequest"/></message>
  <message name="GetPODataOut"><part name="parameters" element="tns:GetPODataResponse"/></message>
  <message name="AddTwoIn"><part name="parameters" element="tns:AddTwoRequest"/></message>
  <message name="AddTwoOut"><part name="parameters" element="tns:AddTwoResponse"/></message>
  <portType name="SamplePortType">
    <operation name="GetPOData"><input message="tns:GetPODataIn"/><output message="tns:GetPODataOut"/></operation>
    <operation name="AddTwo"><input message="tns:AddTwoIn"/><output message="tns:AddTwoOut"/></operation>
  </portType>
  <binding name="SampleBinding" type="tns:SamplePortType">
    <soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetPOData">
      <soap:operation soapAction="GetPOData"/>
      <input><soap:body use="literal"/></input><output><soap:body use="literal"/></output>
    </operation>
    <operation name="AddTwo">
      <soap:operation soapAction="AddTwo"/>
      <input><soap:body use="literal"/></input><output><soap:body use="literal"/></output>
    </operation>
  </binding>
  <service name="SampleService">
    <port name="SamplePort" binding="tns:SampleBinding">
      <soap:address location="http://127.0.0.1:9/ws"/>
    </port>
  </service>
</definitions>
```

- [ ] **Step 2: 寫失敗測試**

`tests/test_soap_service.py`：

```python
# -*- coding: utf-8 -*-
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from suds.client import Client
from suds.transport import Reply
from suds.transport.http import HttpTransport

from src.core.soap_service import ParamCountMismatch, SoapService, format_xml, split_params

WSDL_URL = (Path(__file__).parent / "fixtures" / "sample.wsdl").resolve().as_uri()


class FakeTransport(HttpTransport):
    """WSDL 照常從檔案讀取；送出的 SOAP 請求改為回傳預先準備的回應"""

    def __init__(self, body, sent):
        super().__init__()
        self._body = body
        self._sent = sent

    def send(self, request):
        self._sent.append(request.message)
        return Reply(200, {"Content-Type": "text/xml; charset=utf-8"}, self._body)


class FakeClientFactory:
    """每次建立 Client 都配一個新的 transport（suds 的 transport 不能給多個 Client 共用）"""

    def __init__(self, response_element="GetPODataResponse", response_text="<ok/>"):
        self._body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<{response_element} xmlns="http://example.com/ws">'
            f'<response>{escape(response_text)}</response>'
            f'</{response_element}>'
            '</soap:Body></soap:Envelope>'
        ).encode("utf-8")
        self.sent = []
        self.clients = []

    def __call__(self, url, timeout):
        client = Client(url, timeout=timeout, cache=None, transport=FakeTransport(self._body, self.sent))
        self.clients.append(client)
        return client


def test_split_params_single():
    assert split_params("<a/>") == ["<a/>"]


def test_split_params_multiple_and_strips_newlines():
    assert split_params("<a>\r\n  1</a>#~#\n<b/>") == ["<a>  1</a>", "<b/>"]


def test_format_xml_indents_and_keeps_declaration():
    raw = '<?xml version="1.0" encoding="utf-8"?><Request><Access user="a"/></Request>'
    assert format_xml(raw) == (
        '<?xml version="1.0" encoding="utf-8"?>\n<Request>\n  <Access user="a"/>\n</Request>\n'
    )


def test_format_xml_reindents_existing_whitespace():
    assert format_xml("<a>\n      <b/>\n</a>") == "<a>\n  <b/>\n</a>\n"


def test_format_xml_keeps_non_utf8_declaration():
    assert format_xml('<?xml version="1.0" encoding="big5"?><r>中文</r>') == (
        '<?xml version="1.0" encoding="big5"?>\n<r>中文</r>\n'
    )


@pytest.mark.parametrize("bad", ["", "   ", "<a>", "not xml", "3"])
def test_format_xml_rejects_invalid(bad):
    with pytest.raises(ValueError):
        format_xml(bad)


def test_param_count_mismatch_message():
    err = ParamCountMismatch(expected=2, actual=1)
    assert (err.expected, err.actual) == (2, 1)
    assert str(err) == "此方法需要 2 個參數，目前輸入 1 個（多個參數請用 #~# 隔開）"


def test_load_methods_returns_sorted_names():
    service = SoapService(client_factory=FakeClientFactory())
    assert service.load_methods(WSDL_URL, 5) == ["AddTwo", "GetPOData"]


def test_load_methods_always_rebuilds_client():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.load_methods(WSDL_URL, 5)
    service.load_methods(WSDL_URL, 5)
    assert len(factory.clients) == 2


def test_call_maps_param_and_formats_response():
    factory = FakeClientFactory("GetPODataResponse", '<Response><Status code="0"/></Response>')
    service = SoapService(client_factory=factory)
    result = service.call(WSDL_URL, "GetPOData", "<Request/>", 5)
    assert result.text == '<Response>\n  <Status code="0"/>\n</Response>\n'
    assert result.size == len('<Response><Status code="0"/></Response>'.encode("utf-8"))
    assert result.elapsed >= 0
    assert b"&lt;Request/&gt;" in factory.sent[0]


def test_call_with_multiple_params_returns_raw_non_xml():
    factory = FakeClientFactory("AddTwoResponse", "3")
    service = SoapService(client_factory=factory)
    result = service.call(WSDL_URL, "AddTwo", "1#~#2", 5)
    assert result.text == "3"
    assert result.size == 1
    assert b">1</" in factory.sent[0] and b">2</" in factory.sent[0]


def test_call_raises_on_param_count_mismatch():
    service = SoapService(client_factory=FakeClientFactory("AddTwoResponse", "3"))
    with pytest.raises(ParamCountMismatch) as info:
        service.call(WSDL_URL, "AddTwo", "only-one", 5)
    assert (info.value.expected, info.value.actual) == (2, 1)


def test_call_unknown_method_raises_value_error():
    service = SoapService(client_factory=FakeClientFactory())
    with pytest.raises(ValueError, match="NoSuchMethod"):
        service.call(WSDL_URL, "NoSuchMethod", "<r/>", 5)


def test_call_reuses_client_from_load_methods():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.load_methods(WSDL_URL, 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    assert len(factory.clients) == 1


def test_call_updates_timeout_on_cached_client():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 30)
    assert len(factory.clients) == 1
    assert factory.clients[0].options.timeout == 30
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `uv run pytest tests/test_soap_service.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.core.soap_service'`

- [ ] **Step 4: 實作 SoapService**

`src/core/soap_service.py`：

```python
# -*- coding: utf-8 -*-
"""
WebService 呼叫：讀取 WSDL 方法、依參數呼叫方法、XML 排版
"""
import re
import threading
import time
from dataclasses import dataclass

from lxml import etree
from suds.client import Client

PARAM_SEPARATOR = "#~#"
_DECLARATION = re.compile(r"^\s*(<\?xml[^>]*\?>)\s*")


@dataclass
class CallResult:
    text: str
    elapsed: float
    size: int


class ParamCountMismatch(Exception):
    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"此方法需要 {expected} 個參數，目前輸入 {actual} 個（多個參數請用 {PARAM_SEPARATOR} 隔開）"
        )
        self.expected = expected
        self.actual = actual


def split_params(raw: str) -> list[str]:
    """移除換行後以 #~# 切分參數（沿用舊版規則）"""
    return raw.replace("\r", "").replace("\n", "").split(PARAM_SEPARATOR)


def format_xml(text: str) -> str:
    """重新縮排 XML；保留原本的 <?xml ?> 宣告。不是合法 XML 時丟出 ValueError"""
    match = _DECLARATION.match(text)
    declaration = match.group(1) if match else ""
    body = text[match.end():] if match else text
    parser = etree.XMLParser(remove_blank_text=True)
    try:
        root = etree.fromstring(body.strip(), parser)
    except etree.XMLSyntaxError as err:
        raise ValueError(f"不是合法的 XML：{err}") from err
    pretty = etree.tostring(root, encoding="unicode", pretty_print=True)
    return f"{declaration}\n{pretty}" if declaration else pretty


def _default_client_factory(url: str, timeout: int) -> Client:
    # cache=None：每次「讀取 WSDL」都重新下載，不使用 suds 預設一天的磁碟快取
    return Client(url, timeout=timeout, cache=None)


def _port_methods(client: Client):
    return client.wsdl.services[0].ports[0].methods


def _param_names(client: Client, method: str) -> list[str]:
    methods = _port_methods(client)
    if method not in methods:
        raise ValueError(f"WSDL 中找不到方法 {method}")
    definition = methods[method]
    return [str(param[0]) for param in definition.binding.input.param_defs(definition)]


class SoapService:
    def __init__(self, client_factory=_default_client_factory):
        self._client_factory = client_factory
        self._clients: dict[str, Client] = {}
        self._lock = threading.Lock()

    def load_methods(self, url: str, timeout: int) -> list[str]:
        client = self._client_factory(url, timeout)
        with self._lock:
            self._clients[url] = client
        return sorted(str(name) for name in _port_methods(client))

    def call(self, url: str, method: str, raw_params: str, timeout: int) -> CallResult:
        client = self._client_for(url, timeout)
        names = _param_names(client, method)
        values = split_params(raw_params)
        if len(values) != len(names):
            raise ParamCountMismatch(expected=len(names), actual=len(values))
        started = time.perf_counter()
        result = getattr(client.service, method)(**dict(zip(names, values)))
        elapsed = time.perf_counter() - started
        raw = "" if result is None else str(result)
        try:
            text = format_xml(raw)
        except ValueError:
            text = raw
        return CallResult(text=text, elapsed=elapsed, size=len(raw.encode("utf-8")))

    def _client_for(self, url: str, timeout: int) -> Client:
        with self._lock:
            client = self._clients.get(url)
        if client is None:
            client = self._client_factory(url, timeout)
            with self._lock:
                self._clients[url] = client
        else:
            # 取消後的舊請求可能仍在使用同一個 client；suds 1.2 的 clone() 會 RecursionError，
            # 所以直接共用，只更新逾時設定
            client.set_options(timeout=timeout)
        return client
```

- [ ] **Step 5: 執行測試確認通過**

Run: `uv run pytest tests/test_soap_service.py -v`
Expected: 全部 PASS（19 個測試）

- [ ] **Step 6: Commit**

```bash
git add src/core/soap_service.py tests/fixtures/sample.wsdl tests/test_soap_service.py
```

訊息：

```
新增 SoapService：WSDL 方法讀取、參數對應與 XML 排版

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 3: 主題系統

**Files:**
- Modify: `src/ui/__init__.py`, `src/ws_tool.py:11`
- Create: `src/ui/theme.py`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces:
  - `ThemeMode`（`StrEnum`：`SYSTEM="system"`、`LIGHT="light"`、`DARK="dark"`）
  - `XmlColors(tag, attr_name, attr_value, comment, declaration)`（frozen dataclass，值為 `#RRGGBB` 大寫字串）
  - `ThemePalette(name, bg, surface, surface_hover, border, text, text_muted, accent, accent_hover, accent_text, success, warning, danger, xml: XmlColors)`（frozen）
  - 常數 `LIGHT`、`DARK: ThemePalette`
  - `build_stylesheet(palette) -> str`、`build_qpalette(palette) -> QPalette`、`repolish(widget) -> None`
  - `ThemeManager(app: QApplication, settings: QSettings)`：屬性 `mode: ThemeMode`、`palette: ThemePalette`；方法 `apply()`、`set_mode(mode)`；訊號 `themeChanged(object)`（參數是 `ThemePalette`）
  - QSS 使用的 objectName：`Sidebar`、`AppTitle`、`SectionTitle`、`Hint`、`FieldLabel`、`Card`、`NameEdit`、`ConnectionList`、`ItemTitle`、`ItemSubtitle`、`NotificationBar`、`StatusState`、`StatusDetail`；動態屬性：按鈕 `variant`（`primary` / `subtle`）、`NotificationBar` 的 `level`、`StatusState` 的 `state`（`success` / `error` / `busy`）

- [ ] **Step 1: 讓 `src.ui` 套件不再自動匯入舊的 wx 模組**

新的 `src/ui/*.py` 被匯入時，Python 會先執行 `src/ui/__init__.py`，目前它會載入整個 wx 介面。

`src/ui/__init__.py` 改為：

```python
"""
ui模块
"""
```

`src/ws_tool.py` 第 11 行 `from src.ui import main` 改為：

```python
from src.ui.main import main
```

驗證舊版仍可匯入：

Run: `uv run python -c "import sys; sys.argv=['x']; from src.ui.main import main; print(main.Main)"`
Expected: 印出 `<class 'src.ui.main.main.Main'>`

- [ ] **Step 2: 寫失敗測試**

`tests/test_theme.py`：

```python
# -*- coding: utf-8 -*-
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QPalette

from src.ui.theme import DARK, LIGHT, ThemeManager, ThemeMode, build_qpalette, build_stylesheet


@pytest.fixture
def settings(tmp_path):
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.mark.parametrize("palette", [LIGHT, DARK])
def test_stylesheet_substitutes_all_tokens(palette):
    qss = build_stylesheet(palette)
    assert "$" not in qss
    for color in (palette.bg, palette.surface, palette.accent, palette.accent_hover, palette.danger):
        assert color in qss


def test_qpalette_uses_palette_colors():
    pal = build_qpalette(DARK)
    assert pal.color(QPalette.ColorRole.Window).name().upper() == DARK.bg
    assert pal.color(QPalette.ColorRole.Base).name().upper() == DARK.surface
    assert pal.color(QPalette.ColorRole.Highlight).name().upper() == DARK.accent
    assert pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name().upper() == DARK.text_muted


def test_defaults_to_system_mode(qapp, settings):
    assert ThemeManager(qapp, settings).mode is ThemeMode.SYSTEM


def test_system_mode_with_unknown_scheme_uses_light(qapp, settings):
    # offscreen 平台回報 ColorScheme.Unknown，應視為淺色
    manager = ThemeManager(qapp, settings)
    manager.apply()
    assert manager.palette == LIGHT
    assert qapp.style().name().lower() == "fusion"


def test_set_mode_applies_persists_and_emits(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    received = []
    manager.themeChanged.connect(received.append)
    manager.set_mode(ThemeMode.DARK)
    assert manager.mode is ThemeMode.DARK
    assert manager.palette == DARK
    assert received == [DARK]
    assert DARK.bg in qapp.styleSheet()
    assert settings.value("ui/theme") == "dark"
    assert ThemeManager(qapp, settings).mode is ThemeMode.DARK


def test_set_same_mode_does_not_emit(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    received = []
    manager.themeChanged.connect(received.append)
    manager.set_mode(ThemeMode.SYSTEM)
    assert received == []


def test_switch_back_to_light(qapp, settings):
    manager = ThemeManager(qapp, settings)
    manager.apply()
    manager.set_mode(ThemeMode.DARK)
    manager.set_mode(ThemeMode.LIGHT)
    assert manager.palette == LIGHT
    assert LIGHT.bg in qapp.styleSheet()


def test_invalid_stored_mode_falls_back_to_system(qapp, settings):
    settings.setValue("ui/theme", "purple")
    assert ThemeManager(qapp, settings).mode is ThemeMode.SYSTEM
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `uv run pytest tests/test_theme.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.theme'`

- [ ] **Step 4: 實作 theme.py**

`src/ui/theme.py`：

```python
# -*- coding: utf-8 -*-
"""
主題：Light / Dark 色票、QSS 樣板與切換管理
"""
from dataclasses import dataclass, fields
from enum import StrEnum
from string import Template

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget

SETTINGS_KEY = "ui/theme"
UI_FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI"]
UI_FONT_SIZE = 10


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class XmlColors:
    tag: str
    attr_name: str
    attr_value: str
    comment: str
    declaration: str


@dataclass(frozen=True)
class ThemePalette:
    name: str
    bg: str
    surface: str
    surface_hover: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    success: str
    warning: str
    danger: str
    xml: XmlColors


LIGHT = ThemePalette(
    name="light",
    bg="#F3F3F3",
    surface="#FFFFFF",
    surface_hover="#EAEAEA",
    border="#E0E0E0",
    text="#1B1B1B",
    text_muted="#616161",
    accent="#0067C0",
    accent_hover="#1975C5",
    accent_text="#FFFFFF",
    success="#0F7B0F",
    warning="#9D5D00",
    danger="#C42B1C",
    xml=XmlColors(tag="#800000", attr_name="#E50000", attr_value="#0000FF", comment="#008000", declaration="#808080"),
)

DARK = ThemePalette(
    name="dark",
    bg="#202020",
    surface="#2B2B2B",
    surface_hover="#383838",
    border="#3A3A3A",
    text="#FFFFFF",
    text_muted="#A0A0A0",
    accent="#4CC2FF",
    accent_hover="#47B1E8",
    accent_text="#000000",
    success="#6CCB5F",
    warning="#FCE100",
    danger="#FF99A4",
    xml=XmlColors(tag="#569CD6", attr_name="#9CDCFE", attr_value="#CE9178", comment="#6A9955", declaration="#808080"),
)

_QSS = Template("""
QWidget { color: $text; }
QMainWindow, QDialog { background: $bg; }
QFrame#Sidebar { background: $bg; border-right: 1px solid $border; }
QLabel#AppTitle { font-size: 13pt; font-weight: 600; padding: 0 4px 4px 4px; }
QLabel#SectionTitle { font-weight: 600; }
QLabel#Hint { color: $warning; }
QLabel#FieldLabel, QLabel#ItemSubtitle, QLabel#StatusDetail { color: $text_muted; }
QLabel#ItemTitle { font-weight: 600; }
QFrame#Card { background: $surface; border: 1px solid $border; border-radius: 8px; }

QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QPlainTextEdit { padding: 4px; }
QLineEdit#NameEdit { font-size: 12pt; font-weight: 600; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus { border: 1px solid $accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { color: $text_muted; background: $bg; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    selection-background-color: $surface_hover;
    selection-color: $text;
    outline: 0;
}

QPushButton {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background: $surface_hover; }
QPushButton:pressed { background: $border; }
QPushButton:disabled { color: $text_muted; }
QPushButton[variant="primary"] { background: $accent; color: $accent_text; border: 1px solid $accent; font-weight: 600; }
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:disabled { background: $border; border-color: $border; color: $text_muted; }
QPushButton[variant="subtle"] { background: transparent; border: 1px solid transparent; padding: 4px 8px; }
QPushButton[variant="subtle"]:hover { background: $surface_hover; }
QPushButton::menu-indicator { width: 0; }

QListWidget#ConnectionList { background: transparent; border: none; outline: 0; }
QListWidget#ConnectionList::item { border-radius: 6px; margin: 1px 0; border-left: 3px solid transparent; }
QListWidget#ConnectionList::item:hover { background: $surface_hover; }
QListWidget#ConnectionList::item:selected { background: $surface_hover; border-left: 3px solid $accent; }

QFrame#NotificationBar { background: $surface; border: 1px solid $border; border-left: 4px solid $accent; border-radius: 8px; }
QFrame#NotificationBar[level="success"] { border-left-color: $success; }
QFrame#NotificationBar[level="warning"] { border-left-color: $warning; }
QFrame#NotificationBar[level="error"] { border-left-color: $danger; }

QStatusBar { background: $bg; border-top: 1px solid $border; }
QStatusBar::item { border: none; }
QLabel#StatusState[state="success"] { color: $success; font-weight: 600; }
QLabel#StatusState[state="error"] { color: $danger; font-weight: 600; }
QLabel#StatusState[state="busy"] { color: $accent; font-weight: 600; }

QSplitter::handle { background: transparent; }
QMenu { background: $surface; color: $text; border: 1px solid $border; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 4px; }
QMenu::item:selected { background: $surface_hover; }
QToolTip { background: $surface; color: $text; border: 1px solid $border; padding: 4px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border; border-radius: 3px; min-height: 24px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 3px; min-width: 24px; }
QScrollBar::handle:hover { background: $text_muted; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
""")


def build_stylesheet(palette: ThemePalette) -> str:
    values = {f.name: getattr(palette, f.name) for f in fields(palette) if isinstance(getattr(palette, f.name), str)}
    return _QSS.substitute(values)


def build_qpalette(palette: ThemePalette) -> QPalette:
    """QSS 管不到的地方（右鍵選單底色、捲軸等）由 QPalette 補上"""
    role = QPalette.ColorRole
    qpalette = QPalette()
    for color_role, color in {
        role.Window: palette.bg,
        role.WindowText: palette.text,
        role.Base: palette.surface,
        role.AlternateBase: palette.surface_hover,
        role.Text: palette.text,
        role.Button: palette.surface,
        role.ButtonText: palette.text,
        role.Highlight: palette.accent,
        role.HighlightedText: palette.accent_text,
        role.ToolTipBase: palette.surface,
        role.ToolTipText: palette.text,
        role.PlaceholderText: palette.text_muted,
        role.Link: palette.accent,
    }.items():
        qpalette.setColor(color_role, QColor(color))
    for color_role in (role.WindowText, role.Text, role.ButtonText):
        qpalette.setColor(QPalette.ColorGroup.Disabled, color_role, QColor(palette.text_muted))
    return qpalette


def repolish(widget: QWidget) -> None:
    """動態屬性改變後重新套用 QSS"""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ThemeManager(QObject):
    themeChanged = Signal(object)

    def __init__(self, app: QApplication, settings: QSettings):
        super().__init__(app)
        self._app = app
        self._settings = settings
        try:
            self._mode = ThemeMode(str(settings.value(SETTINGS_KEY, ThemeMode.SYSTEM.value)))
        except ValueError:
            self._mode = ThemeMode.SYSTEM
        self._palette = LIGHT
        self._hints = QGuiApplication.styleHints()
        self._hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def palette(self) -> ThemePalette:
        return self._palette

    def apply(self) -> None:
        """啟動時呼叫一次：設定 Fusion 樣式、字型並套用目前模式"""
        self._app.setStyle("Fusion")
        font = QFont()
        font.setFamilies(UI_FONT_FAMILIES)
        font.setPointSize(UI_FONT_SIZE)
        self._app.setFont(font)
        self._apply_scheme_override()
        self._refresh()

    def set_mode(self, mode: ThemeMode) -> None:
        if mode is self._mode:
            return
        self._mode = mode
        self._settings.setValue(SETTINGS_KEY, mode.value)
        self._settings.sync()
        self._apply_scheme_override()
        self._refresh()

    def _apply_scheme_override(self) -> None:
        # 手動模式時覆寫系統配色，讓 Windows 標題列也跟著變
        if self._mode is ThemeMode.LIGHT:
            self._hints.setColorScheme(Qt.ColorScheme.Light)
        elif self._mode is ThemeMode.DARK:
            self._hints.setColorScheme(Qt.ColorScheme.Dark)
        else:
            self._hints.unsetColorScheme()

    def _on_system_scheme_changed(self, _scheme) -> None:
        if self._mode is ThemeMode.SYSTEM:
            self._refresh()

    def _effective_palette(self) -> ThemePalette:
        if self._mode is ThemeMode.LIGHT:
            return LIGHT
        if self._mode is ThemeMode.DARK:
            return DARK
        return DARK if self._hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT

    def _refresh(self) -> None:
        palette = self._effective_palette()
        self._palette = palette
        self._app.setPalette(build_qpalette(palette))
        self._app.setStyleSheet(build_stylesheet(palette))
        self.themeChanged.emit(palette)
```

- [ ] **Step 5: 執行測試確認通過**

Run: `uv run pytest tests/test_theme.py -v`
Expected: 全部 PASS（9 個測試）

- [ ] **Step 6: 執行全部測試**

Run: `uv run pytest -v`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add src/ui/__init__.py src/ws_tool.py src/ui/theme.py tests/test_theme.py
```

訊息：

```
新增主題系統：Light/Dark 色票、QSS 樣板與 ThemeManager

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 4: XML 編輯器與語法上色

**Files:**
- Create: `src/ui/xml_editor.py`
- Test: `tests/test_xml_editor.py`

**Interfaces:**
- Consumes: `XmlColors`、`LIGHT`、`DARK`（Task 3）
- Produces:
  - `XmlEditor(colors: XmlColors, read_only: bool = False, parent=None)`（`QPlainTextEdit` 子類別，objectName `XmlEditor`）；屬性 `colors: XmlColors`；方法 `set_colors(colors)`
  - `XmlHighlighter(document, colors)`；屬性 `colors`；方法 `set_colors(colors)`

- [ ] **Step 1: 寫失敗測試**

`tests/test_xml_editor.py`：

```python
# -*- coding: utf-8 -*-
from src.ui.theme import DARK, LIGHT
from src.ui.xml_editor import XmlEditor


def formats_of(editor, block_number=0):
    block = editor.document().findBlockByNumber(block_number)
    return [
        (fmt.start, fmt.length, fmt.format.foreground().color().name().upper())
        for fmt in block.layout().formats()
    ]


def test_highlights_tag_attribute_and_value(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText('<Field name="pmm01"/>')
    formats = formats_of(editor)
    assert (1, 5, LIGHT.xml.tag) in formats
    assert (7, 4, LIGHT.xml.attr_name) in formats
    assert (12, 7, LIGHT.xml.attr_value) in formats


def test_highlights_closing_tag(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText("</Record>")
    assert (2, 6, LIGHT.xml.tag) in formats_of(editor)


def test_highlights_declaration_and_multiline_comment(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText('<?xml version="1.0"?>\n<!-- a\nb -->\n<c/>')
    assert (0, 21, LIGHT.xml.declaration) in formats_of(editor, 0)
    assert (0, 6, LIGHT.xml.comment) in formats_of(editor, 1)
    assert (0, 5, LIGHT.xml.comment) in formats_of(editor, 2)
    assert (1, 1, LIGHT.xml.tag) in formats_of(editor, 3)


def test_set_colors_rehighlights(qapp):
    editor = XmlEditor(LIGHT.xml)
    editor.setPlainText("<a/>")
    editor.set_colors(DARK.xml)
    assert editor.colors == DARK.xml
    assert (1, 1, DARK.xml.tag) in formats_of(editor)


def test_read_only_flag(qapp):
    assert XmlEditor(LIGHT.xml, read_only=True).isReadOnly()
    assert not XmlEditor(LIGHT.xml).isReadOnly()


def test_uses_monospace_font(qapp):
    families = XmlEditor(LIGHT.xml).font().families()
    assert families[:2] == ["Cascadia Mono", "Consolas"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_xml_editor.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.xml_editor'`

- [ ] **Step 3: 實作**

`src/ui/xml_editor.py`：

```python
# -*- coding: utf-8 -*-
"""
XML 編輯器：等寬字型 + 語法上色（顏色跟著主題）
"""
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit

from src.ui.theme import XmlColors

EDITOR_FONT_FAMILIES = ["Cascadia Mono", "Consolas"]
EDITOR_FONT_SIZE = 10
_IN_COMMENT = 1


def _char_format(color: str) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    return fmt


class XmlHighlighter(QSyntaxHighlighter):
    _TAG = QRegularExpression(r"</?([A-Za-z_][\w.:-]*)")
    _ATTRIBUTE = QRegularExpression(r"([A-Za-z_][\w.:-]*)\s*=\s*(\"[^\"]*\"|'[^']*')")
    _DECLARATION = QRegularExpression(r"<\?.*?\?>")

    def __init__(self, document, colors: XmlColors):
        super().__init__(document)
        self._colors = colors
        self._formats = self._build_formats(colors)

    @property
    def colors(self) -> XmlColors:
        return self._colors

    def set_colors(self, colors: XmlColors) -> None:
        self._colors = colors
        self._formats = self._build_formats(colors)
        self.rehighlight()

    @staticmethod
    def _build_formats(colors: XmlColors) -> dict[str, QTextCharFormat]:
        return {
            "tag": _char_format(colors.tag),
            "attr_name": _char_format(colors.attr_name),
            "attr_value": _char_format(colors.attr_value),
            "comment": _char_format(colors.comment),
            "declaration": _char_format(colors.declaration),
        }

    def highlightBlock(self, text: str) -> None:
        # 後套用的會覆蓋先套用的：宣告蓋過屬性，註解蓋過全部
        self._apply(self._TAG, text, {1: "tag"})
        self._apply(self._ATTRIBUTE, text, {1: "attr_name", 2: "attr_value"})
        self._apply(self._DECLARATION, text, {0: "declaration"})
        self._highlight_comments(text)

    def _apply(self, pattern: QRegularExpression, text: str, groups: dict[int, str]) -> None:
        matches = pattern.globalMatch(text)
        while matches.hasNext():
            match = matches.next()
            for group, key in groups.items():
                self.setFormat(match.capturedStart(group), match.capturedLength(group), self._formats[key])

    def _highlight_comments(self, text: str) -> None:
        self.setCurrentBlockState(0)
        start = 0 if self.previousBlockState() == _IN_COMMENT else text.find("<!--")
        while start >= 0:
            end = text.find("-->", start)
            if end < 0:
                self.setCurrentBlockState(_IN_COMMENT)
                length = len(text) - start
            else:
                length = end - start + 3
            self.setFormat(start, length, self._formats["comment"])
            start = text.find("<!--", start + length)


class XmlEditor(QPlainTextEdit):
    def __init__(self, colors: XmlColors, read_only: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("XmlEditor")
        font = QFont()
        font.setFamilies(EDITOR_FONT_FAMILIES)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(EDITOR_FONT_SIZE)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.setReadOnly(read_only)
        self._highlighter = XmlHighlighter(self.document(), colors)

    @property
    def colors(self) -> XmlColors:
        return self._highlighter.colors

    def set_colors(self, colors: XmlColors) -> None:
        self._highlighter.set_colors(colors)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_xml_editor.py -v`
Expected: 全部 PASS（6 個測試）

- [ ] **Step 5: Commit**

```bash
git add src/ui/xml_editor.py tests/test_xml_editor.py
```

訊息：

```
新增 XML 編輯器與語法上色

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 5: 背景工作

**Files:**
- Create: `src/ui/workers.py`
- Create: `tests/helpers.py`
- Test: `tests/test_workers.py`

**Interfaces:**
- Produces:
  - `run_in_background(tag, fn, *args, on_success, on_failure, **kwargs) -> Task`：在 `QThreadPool.globalInstance()` 執行 `fn(*args, **kwargs)`；成功時以 `on_success(tag, value)`、例外時以 `on_failure(tag, error)` 在**主執行緒**回呼。呼叫端必須保留回傳的 `Task` 參照直到收到回呼
  - `tests.helpers.wait_until(predicate, timeout=5.0)`：處理 Qt 事件直到條件成立，逾時則 `AssertionError`

- [ ] **Step 1: 建立測試工具**

`tests/helpers.py`：

```python
# -*- coding: utf-8 -*-
"""
測試共用工具
"""
import time

from PySide6.QtCore import QCoreApplication


def wait_until(predicate, timeout=5.0):
    """持續處理 Qt 事件直到 predicate() 為真，逾時則測試失敗"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("等待條件逾時")
```

- [ ] **Step 2: 寫失敗測試**

`tests/test_workers.py`：

```python
# -*- coding: utf-8 -*-
import threading

from PySide6.QtCore import QObject, Slot

from src.ui.workers import run_in_background
from tests.helpers import wait_until


class Receiver(QObject):
    def __init__(self):
        super().__init__()
        self.successes = []
        self.failures = []
        self.threads = []

    @Slot(object, object)
    def on_success(self, tag, value):
        self.successes.append((tag, value))
        self.threads.append(threading.get_ident())

    @Slot(object, object)
    def on_failure(self, tag, error):
        self.failures.append((tag, error))
        self.threads.append(threading.get_ident())


def test_success_is_delivered_on_main_thread(qapp):
    receiver = Receiver()
    task = run_in_background(("run", 1), lambda a, b: a + b, 2, 3,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes == [(("run", 1), 5)]
    assert receiver.failures == []
    assert receiver.threads == [threading.get_ident()]
    assert task is not None


def test_function_runs_off_main_thread(qapp):
    receiver = Receiver()
    task = run_in_background("tag", threading.get_ident,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes[0][1] != threading.get_ident()
    assert task is not None


def test_exception_is_delivered_as_failure(qapp):
    def boom():
        raise RuntimeError("壞了")

    receiver = Receiver()
    task = run_in_background(("load", 7), boom, on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.failures)
    tag, error = receiver.failures[0]
    assert tag == ("load", 7)
    assert isinstance(error, RuntimeError) and str(error) == "壞了"
    assert receiver.successes == []
    assert receiver.threads == [threading.get_ident()]
    assert task is not None


def test_keyword_arguments_are_forwarded(qapp):
    receiver = Receiver()
    task = run_in_background("kw", lambda *, x: x * 2, x=21,
                             on_success=receiver.on_success, on_failure=receiver.on_failure)
    wait_until(lambda: receiver.successes)
    assert receiver.successes == [("kw", 42)]
    assert task is not None
```

- [ ] **Step 3: 執行測試確認失敗**

Run: `uv run pytest tests/test_workers.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.workers'`

- [ ] **Step 4: 實作**

`src/ui/workers.py`：

```python
# -*- coding: utf-8 -*-
"""
背景工作：在執行緒池執行函式，結果以訊號送回主執行緒
"""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class TaskSignals(QObject):
    succeeded = Signal(object, object)  # tag, 回傳值
    failed = Signal(object, object)  # tag, 例外


class Task(QRunnable):
    def __init__(self, tag, fn, args, kwargs):
        super().__init__()
        self.signals = TaskSignals()
        self._tag = tag
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as err:  # 所有錯誤都交給 UI 顯示
            self.signals.failed.emit(self._tag, err)
            return
        self.signals.succeeded.emit(self._tag, result)


def run_in_background(tag, fn, *args, on_success, on_failure, **kwargs) -> Task:
    """呼叫端需保留回傳的 Task 參照，直到收到成功或失敗回呼"""
    task = Task(tag, fn, args, kwargs)
    task.signals.succeeded.connect(on_success)
    task.signals.failed.connect(on_failure)
    QThreadPool.globalInstance().start(task)
    return task
```

- [ ] **Step 5: 執行測試確認通過**

Run: `uv run pytest tests/test_workers.py -v`
Expected: 全部 PASS（4 個測試）

- [ ] **Step 6: Commit**

```bash
git add src/ui/workers.py tests/helpers.py tests/test_workers.py
```

訊息：

```
新增背景工作執行器

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 6: 通知橫幅

**Files:**
- Create: `src/ui/notification_bar.py`
- Test: `tests/test_notification_bar.py`

**Interfaces:**
- Consumes: `repolish`（Task 3）、`wait_until`（Task 5）
- Produces:
  - `NotificationBar(parent=None)`（`QFrame`，objectName `NotificationBar`，初始隱藏）
  - 屬性 `level: str`、`text: str`、`close_button: QPushButton`、`auto_hide_ms: int`（預設 3000）
  - 方法 `show_message(level: str, text: str)`（level 為 `info` / `success` / `warning` / `error`；前兩者自動隱藏）、`dismiss()`

- [ ] **Step 1: 寫失敗測試**

`tests/test_notification_bar.py`：

```python
# -*- coding: utf-8 -*-
from PySide6.QtTest import QTest

from src.ui.notification_bar import NotificationBar
from tests.helpers import wait_until


def test_hidden_initially(qapp):
    assert NotificationBar().isHidden()


def test_warning_stays_until_closed(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 10
    bar.show_message("warning", "注意")
    assert not bar.isHidden()
    assert (bar.level, bar.text) == ("warning", "注意")
    QTest.qWait(60)
    assert not bar.isHidden()
    bar.close_button.click()
    assert bar.isHidden()


def test_success_auto_hides(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 10
    bar.show_message("success", "完成")
    assert not bar.isHidden()
    wait_until(bar.isHidden, timeout=2)


def test_error_replaces_success_and_stops_auto_hide(qapp):
    bar = NotificationBar()
    bar.auto_hide_ms = 30
    bar.show_message("success", "完成")
    bar.show_message("error", "失敗了")
    QTest.qWait(80)
    assert not bar.isHidden()
    assert (bar.level, bar.text) == ("error", "失敗了")
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_notification_bar.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.notification_bar'`

- [ ] **Step 3: 實作**

`src/ui/notification_bar.py`：

```python
# -*- coding: utf-8 -*-
"""
通知橫幅：顯示 info / success / warning / error 訊息
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.ui.theme import repolish

AUTO_HIDE_LEVELS = ("info", "success")


class NotificationBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("NotificationBar")
        self.setProperty("level", "info")
        self.auto_hide_ms = 3000

        self._message = QLabel()
        self._message.setWordWrap(True)
        self.close_button = QPushButton("✕")
        self.close_button.setProperty("variant", "subtle")
        self.close_button.setToolTip("關閉")
        self.close_button.clicked.connect(self.dismiss)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 6, 6)
        layout.addWidget(self._message, 1)
        layout.addWidget(self.close_button)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self.hide()

    @property
    def level(self) -> str:
        return self.property("level")

    @property
    def text(self) -> str:
        return self._message.text()

    def show_message(self, level: str, text: str) -> None:
        self.setProperty("level", level)
        repolish(self)
        self._message.setText(text)
        self.show()
        if level in AUTO_HIDE_LEVELS:
            self._timer.start(self.auto_hide_ms)
        else:
            self._timer.stop()

    def dismiss(self) -> None:
        self._timer.stop()
        self.hide()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_notification_bar.py -v`
Expected: 全部 PASS（4 個測試）

- [ ] **Step 5: Commit**

```bash
git add src/ui/notification_bar.py tests/test_notification_bar.py
```

訊息：

```
新增通知橫幅元件

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 7: 左側連線清單

**Files:**
- Create: `src/ui/connection_list.py`
- Test: `tests/test_connection_list.py`

**Interfaces:**
- Consumes: `Connection`（Task 1）
- Produces:
  - 常數 `UNNAMED = "未命名"`、`NO_URL = "尚未設定網址"`
  - `ConnectionList(parent=None)`：訊號 `selectionChanged(str)`（uuid，沒有選取時為 `""`）、`addRequested()`、`deleteRequested(str)`
  - 屬性 `search_edit: QLineEdit`、`list_view: QListWidget`（objectName `ConnectionList`）、`add_button: QPushButton`
  - 方法 `set_connections(connections: list[Connection], select_uuid: str | None = None)`（重建清單並選取指定項目或第一筆，會發出 `selectionChanged`）、`update_connection(conn)`、`select(uuid)`、`current_uuid() -> str | None`、`item_widget(uuid) -> ConnectionItemWidget | None`、`visible_uuids() -> list[str]`、`set_busy(busy: bool)`
  - `ConnectionItemWidget` 屬性 `title`、`subtitle`（`ElidedLabel`，`text()` 回傳完整文字）

- [ ] **Step 1: 寫失敗測試**

`tests/test_connection_list.py`：

```python
# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.core.connection_store import Connection
from src.ui.connection_list import NO_URL, UNNAMED, ConnectionList

CONNECTIONS = [
    Connection("u1", "正式區", "http://prod/ws?WSDL", []),
    Connection("u2", "測試區", "http://test/ws?WSDL", []),
    Connection("u3", "", "", []),
]


def make_list(select=None):
    widget = ConnectionList()
    received = []
    widget.selectionChanged.connect(received.append)
    widget.set_connections(CONNECTIONS, select_uuid=select)
    return widget, received


def test_selects_first_by_default(qapp):
    widget, received = make_list()
    assert widget.current_uuid() == "u1"
    assert received == ["u1"]


def test_selects_requested_connection(qapp):
    widget, received = make_list("u2")
    assert widget.current_uuid() == "u2"
    assert received == ["u2"]


def test_blank_connection_shows_placeholders(qapp):
    widget, _ = make_list()
    item = widget.item_widget("u3")
    assert item.title.text() == UNNAMED
    assert item.subtitle.text() == NO_URL
    assert not item.grab().isNull()  # 觸發 ElidedLabel.paintEvent


def test_filter_matches_name_or_url_case_insensitive(qapp):
    widget, _ = make_list()
    widget.search_edit.setText("PROD")
    assert widget.visible_uuids() == ["u1"]
    widget.search_edit.setText("測試")
    assert widget.visible_uuids() == ["u2"]
    widget.search_edit.setText("")
    assert widget.visible_uuids() == ["u1", "u2", "u3"]


def test_update_connection_refreshes_labels(qapp):
    widget, _ = make_list()
    widget.update_connection(Connection("u3", "新名稱", "http://x/ws?WSDL", []))
    assert widget.item_widget("u3").title.text() == "新名稱"
    assert widget.item_widget("u3").subtitle.text() == "http://x/ws?WSDL"


def test_select_emits_selection_changed(qapp):
    widget, received = make_list()
    widget.select("u3")
    assert received == ["u1", "u3"]


def test_delete_key_requests_delete_of_current(qapp):
    widget, _ = make_list("u2")
    requested = []
    widget.deleteRequested.connect(requested.append)
    QTest.keyClick(widget.list_view, Qt.Key.Key_Delete)
    assert requested == ["u2"]


def test_add_button_emits_add_requested(qapp):
    widget, _ = make_list()
    requested = []
    widget.addRequested.connect(lambda: requested.append(True))
    widget.add_button.click()
    assert requested == [True]


def test_set_busy_disables_interaction(qapp):
    widget, _ = make_list()
    widget.set_busy(True)
    assert not widget.list_view.isEnabled() and not widget.add_button.isEnabled()
    widget.set_busy(False)
    assert widget.list_view.isEnabled() and widget.add_button.isEnabled()


def test_set_connections_empty(qapp):
    widget, _ = make_list()
    widget.set_connections([])
    assert widget.current_uuid() is None
    assert widget.visible_uuids() == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_connection_list.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.connection_list'`

- [ ] **Step 3: 實作**

`src/ui/connection_list.py`：

```python
# -*- coding: utf-8 -*-
"""
左側連線清單：搜尋、選取、新增、刪除
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection

UNNAMED = "未命名"
NO_URL = "尚未設定網址"
_UUID_ROLE = Qt.ItemDataRole.UserRole


class ElidedLabel(QLabel):
    """單行標籤，文字過長時以 … 省略"""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.contentsRect()
        elided = self.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, rect.width())
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)


class ConnectionItemWidget(QWidget):
    def __init__(self, conn: Connection, parent=None):
        super().__init__(parent)
        self.title = ElidedLabel()
        self.title.setObjectName("ItemTitle")
        self.subtitle = ElidedLabel()
        self.subtitle.setObjectName("ItemSubtitle")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(2)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        self.set_connection(conn)

    def set_connection(self, conn: Connection) -> None:
        self.title.setText(conn.name or UNNAMED)
        self.subtitle.setText(conn.url or NO_URL)
        self.setToolTip(conn.url)


class _ListView(QListWidget):
    deletePressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deletePressed.emit()
            return
        super().keyPressEvent(event)


class ConnectionList(QWidget):
    selectionChanged = Signal(str)
    addRequested = Signal()
    deleteRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋連線")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)

        self.list_view = _ListView()
        self.list_view.setObjectName("ConnectionList")
        self.list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self._show_context_menu)
        self.list_view.currentItemChanged.connect(self._on_current_changed)
        self.list_view.deletePressed.connect(self._request_delete_current)

        self.add_button = QPushButton("+ 新增連線")
        self.add_button.setToolTip("新增連線 (F1)")
        self.add_button.clicked.connect(lambda: self.addRequested.emit())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.list_view, 1)
        layout.addWidget(self.add_button)

    def set_connections(self, connections: list[Connection], select_uuid: str | None = None) -> None:
        self.list_view.blockSignals(True)
        self.list_view.clear()
        for conn in connections:
            item = QListWidgetItem()
            item.setData(_UUID_ROLE, conn.uuid)
            widget = ConnectionItemWidget(conn)
            item.setSizeHint(QSize(0, widget.sizeHint().height()))
            self.list_view.addItem(item)
            self.list_view.setItemWidget(item, widget)
        self.list_view.blockSignals(False)
        self._apply_filter(self.search_edit.text())
        target = select_uuid or (connections[0].uuid if connections else None)
        if target:
            self.select(target)

    def update_connection(self, conn: Connection) -> None:
        item = self._item_for(conn.uuid)
        if item is None:
            return
        self.list_view.itemWidget(item).set_connection(conn)
        self._apply_filter(self.search_edit.text())

    def select(self, uuid: str) -> None:
        item = self._item_for(uuid)
        if item is not None:
            self.list_view.setCurrentItem(item)

    def current_uuid(self) -> str | None:
        item = self.list_view.currentItem()
        return item.data(_UUID_ROLE) if item is not None else None

    def item_widget(self, uuid: str) -> ConnectionItemWidget | None:
        item = self._item_for(uuid)
        return self.list_view.itemWidget(item) if item is not None else None

    def visible_uuids(self) -> list[str]:
        return [
            self.list_view.item(row).data(_UUID_ROLE)
            for row in range(self.list_view.count())
            if not self.list_view.item(row).isHidden()
        ]

    def set_busy(self, busy: bool) -> None:
        self.list_view.setEnabled(not busy)
        self.add_button.setEnabled(not busy)

    def _item_for(self, uuid: str) -> QListWidgetItem | None:
        for row in range(self.list_view.count()):
            item = self.list_view.item(row)
            if item.data(_UUID_ROLE) == uuid:
                return item
        return None

    def _apply_filter(self, text: str) -> None:
        keyword = text.strip().lower()
        for row in range(self.list_view.count()):
            item = self.list_view.item(row)
            widget = self.list_view.itemWidget(item)
            haystack = f"{widget.title.text()}\n{widget.subtitle.text()}".lower()
            item.setHidden(bool(keyword) and keyword not in haystack)

    def _on_current_changed(self, current, _previous) -> None:
        self.selectionChanged.emit(current.data(_UUID_ROLE) if current is not None else "")

    def _request_delete_current(self) -> None:
        uuid = self.current_uuid()
        if uuid:
            self.deleteRequested.emit(uuid)

    def _show_context_menu(self, pos) -> None:
        item = self.list_view.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction("刪除")
        if menu.exec(self.list_view.viewport().mapToGlobal(pos)) is delete_action:
            self.deleteRequested.emit(item.data(_UUID_ROLE))
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_connection_list.py -v`
Expected: 全部 PASS（10 個測試）

- [ ] **Step 5: Commit**

```bash
git add src/ui/connection_list.py tests/test_connection_list.py
```

訊息：

```
新增左側連線清單元件

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 8: 主視窗（版面、連線編輯、主題、工具按鈕）

這個 Task 建立完整的主視窗版面與所有**同步**操作。「讀取 WSDL」與「執行」按鈕先建立但不接上處理函式，Task 9 再加上背景執行。

**Files:**
- Create: `src/ui/main_window.py`
- Test: `tests/test_main_window.py`

**Interfaces:**
- Consumes: `ConnectionStore`、`Connection`（Task 1）；`format_xml`（Task 2）；`ThemeManager`、`ThemeMode`、`repolish`（Task 3）；`XmlEditor`（Task 4）；`NotificationBar`（Task 6）；`ConnectionList`、`UNNAMED`（Task 7）
- Produces:
  - `AboutInfo(name, version, copyright, website)`（frozen dataclass）
  - `format_size(size: int) -> str`
  - 常數 `XML_DECLARATION`、`LOAD_LABEL = "讀取 WSDL"`、`RUN_LABEL = "▶ 執行"`、`CANCEL_LABEL = "取消"`
  - `MainWindow(store, service, theme, about, default_timeout, parent=None)`，`service` 需有 `load_methods(url, timeout)` 與 `call(url, method, raw_params, timeout)`
  - 公開元件屬性：`connection_list`、`name_edit`、`url_edit`、`url_hint`、`load_button`、`method_combo`、`timeout_spin`、`run_button`、`clear_button`、`request_editor`、`response_editor`、`format_button`、`copy_button`、`notification`、`status_state`、`status_detail`、`theme_button`、`theme_actions: dict[ThemeMode, QAction]`、`about_button`
  - 可覆寫的 `_confirm(title: str, text: str) -> bool`（測試以 lambda 取代，避免彈出對話框）

- [ ] **Step 1: 寫失敗測試**

`tests/test_main_window.py`：

```python
# -*- coding: utf-8 -*-
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QGuiApplication

from src.core.connection_store import ConnectionStore
from src.core.soap_service import CallResult
from src.ui.main_window import AboutInfo, MainWindow, format_size
from src.ui.theme import DARK, ThemeManager, ThemeMode

ABOUT = AboutInfo("WebService 測試工具", "v2.0.0", "Copyright", "https://example.com")


class FakeService:
    """取代 SoapService：可設定回傳值、錯誤，或用 gate 讓呼叫停住"""

    def __init__(self):
        self.methods = ["AddTwo", "GetPOData"]
        self.result = CallResult(text="<ok/>\n", elapsed=0.123, size=5)
        self.error = None
        self.gate = None
        self.calls = []

    def _block_or_fail(self):
        if self.gate is not None:
            self.gate.wait(5)
        if self.error is not None:
            raise self.error

    def load_methods(self, url, timeout):
        self.calls.append(("load", url, timeout))
        self._block_or_fail()
        return list(self.methods)

    def call(self, url, method, raw_params, timeout):
        self.calls.append(("call", url, method, raw_params, timeout))
        self._block_or_fail()
        return self.result


@pytest.fixture
def env(qapp, tmp_path):
    service = FakeService()
    theme = ThemeManager(qapp, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    theme.apply()
    ctx = SimpleNamespace(store=ConnectionStore(tmp_path / "connections.profile"), service=service, theme=theme)
    windows = []

    def make(store=None):
        window = MainWindow(store or ctx.store, service, theme, ABOUT, default_timeout=30)
        window._confirm = lambda title, text: True
        windows.append(window)
        return window

    ctx.make = make
    yield ctx
    if service.gate is not None:
        service.gate.set()
    for window in windows:
        window._confirm = lambda title, text: True
        window.close()
        window.deleteLater()


def seed(store, name="正式區", url="http://prod/ws?WSDL", methods=("GetPOData",)):
    uuid = store.add().uuid
    store.rename(uuid, name)
    store.set_url(uuid, url)
    store.set_methods(uuid, list(methods))
    return uuid


def combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_format_size():
    assert format_size(5) == "5 B"
    assert format_size(3174) == "3.1 KB"
    assert format_size(3 * 1024 * 1024) == "3.0 MB"


def test_empty_store_gets_blank_connection(env):
    window = env.make()
    connections = env.store.all()
    assert len(connections) == 1
    assert window.connection_list.current_uuid() == connections[0].uuid
    assert window.notification.level == "info"
    assert window.windowTitle() == "WebService 測試工具"


def test_corrupt_profile_shows_warning(env, tmp_path):
    path = tmp_path / "broken.profile"
    path.write_text("{ not json", encoding="utf-8")
    window = env.make(ConnectionStore(path))
    assert window.notification.level == "warning"
    assert "broken.profile.bak" in window.notification.text


def test_selecting_connection_fills_fields(env):
    seed(env.store)
    window = env.make()
    assert window.name_edit.text() == "正式區"
    assert window.url_edit.text() == "http://prod/ws?WSDL"
    assert combo_items(window.method_combo) == ["GetPOData"]
    assert window.method_combo.currentText() == "GetPOData"
    assert window.timeout_spin.value() == 30
    assert window.status_state.text() == "就緒"


def test_name_and_url_saved_on_editing_finished(env):
    uuid = seed(env.store)
    window = env.make()
    window.name_edit.setText("新名稱")
    window.name_edit.editingFinished.emit()
    window.url_edit.setText("http://new/ws?WSDL")
    window.url_edit.editingFinished.emit()
    reloaded = ConnectionStore(env.store.path).get(uuid)
    assert (reloaded.name, reloaded.url) == ("新名稱", "http://new/ws?WSDL")
    assert window.connection_list.item_widget(uuid).title.text() == "新名稱"


def test_switching_connection_commits_pending_edits(env):
    first = seed(env.store, "A")
    second = seed(env.store, "B")
    window = env.make()
    window.name_edit.setText("A2")  # 尚未觸發 editingFinished
    window.connection_list.select(second)
    assert env.store.get(first).name == "A2"
    assert window.name_edit.text() == "B"


def test_url_hint_when_missing_wsdl_suffix(env):
    seed(env.store)
    window = env.make()
    assert window.url_hint.isHidden()
    window.url_edit.setText("http://prod/ws")
    assert not window.url_hint.isHidden()
    window.url_edit.setText("http://prod/ws?wsdl")
    assert window.url_hint.isHidden()


def test_add_creates_and_selects(env):
    seed(env.store)
    window = env.make()
    window.connection_list.add_button.click()
    connections = env.store.all()
    assert len(connections) == 2
    assert window.connection_list.current_uuid() == connections[1].uuid
    assert window.name_edit.text() == ""


def test_delete_confirmed_removes_and_keeps_other_selected(env):
    first = seed(env.store, "A")
    second = seed(env.store, "B")
    window = env.make()
    window.connection_list.deleteRequested.emit(second)
    assert [conn.uuid for conn in env.store.all()] == [first]
    assert window.connection_list.current_uuid() == first
    assert window.notification.level == "success"


def test_delete_cancelled_keeps_connection(env):
    uuid = seed(env.store)
    window = env.make()
    window._confirm = lambda title, text: False
    window.connection_list.deleteRequested.emit(uuid)
    assert env.store.get(uuid) is not None


def test_deleting_last_connection_creates_blank(env):
    uuid = seed(env.store)
    window = env.make()
    window.connection_list.deleteRequested.emit(uuid)
    remaining = env.store.all()
    assert len(remaining) == 1
    assert remaining[0].uuid != uuid and remaining[0].name == ""
    assert window.name_edit.text() == ""


def test_clear_empties_editors_but_keeps_methods(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<r/>")
    window.response_editor.setPlainText("<ok/>")
    window.clear_button.click()
    assert window.request_editor.toPlainText() == ""
    assert window.response_editor.toPlainText() == ""
    assert combo_items(window.method_combo) == ["GetPOData"]


def test_format_request(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<a><b/></a>")
    window.format_button.click()
    assert window.request_editor.toPlainText() == "<a>\n  <b/>\n</a>\n"


def test_format_invalid_request_warns(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<a>")
    window.format_button.click()
    assert window.request_editor.toPlainText() == "<a>"
    assert window.notification.level == "warning"
    assert window.notification.text == "請求內容不是合法的 XML，無法格式化"


def test_copy_response(env):
    seed(env.store)
    window = env.make()
    window.response_editor.setPlainText("<ok/>")
    window.copy_button.click()
    assert QGuiApplication.clipboard().text() == "<ok/>"
    assert window.notification.text == "已複製回應結果"


def test_copy_empty_response_informs(env):
    seed(env.store)
    window = env.make()
    window.copy_button.click()
    assert window.notification.text == "沒有可複製的回應內容"


def test_theme_change_recolors_editors_and_menu(env):
    window = env.make()
    env.theme.set_mode(ThemeMode.DARK)
    assert window.request_editor.colors == DARK.xml
    assert window.response_editor.colors == DARK.xml
    assert window.theme_actions[ThemeMode.DARK].isChecked()


def test_theme_menu_action_sets_mode(env):
    window = env.make()
    window.theme_actions[ThemeMode.LIGHT].trigger()
    assert env.theme.mode is ThemeMode.LIGHT
    assert window.theme_actions[ThemeMode.LIGHT].isChecked()


def test_close_requires_confirmation(env):
    uuid = seed(env.store)
    window = env.make()
    window.name_edit.setText("關閉前修改")
    window._confirm = lambda title, text: False
    assert window.close() is False
    window._confirm = lambda title, text: True
    assert window.close() is True
    assert env.store.get(uuid).name == "關閉前修改"
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_main_window.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'src.ui.main_window'`

- [ ] **Step 3: 實作**

`src/ui/main_window.py`：

```python
# -*- coding: utf-8 -*-
"""
主視窗：左側連線清單 + 右側工作區
"""
from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QActionGroup, QGuiApplication, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.connection_store import Connection, ConnectionStore
from src.core.soap_service import format_xml
from src.ui.connection_list import UNNAMED, ConnectionList
from src.ui.notification_bar import NotificationBar
from src.ui.theme import ThemeManager, ThemeMode, ThemePalette, repolish
from src.ui.xml_editor import XmlEditor

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'
TIMEOUT_MIN = 5
TIMEOUT_MAX = 120
LOAD_LABEL = "讀取 WSDL"
RUN_LABEL = "▶ 執行"
CANCEL_LABEL = "取消"
THEME_LABELS = {ThemeMode.SYSTEM: "跟隨系統", ThemeMode.LIGHT: "淺色", ThemeMode.DARK: "深色"}


@dataclass(frozen=True)
class AboutInfo:
    name: str
    version: str
    copyright: str
    website: str


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def _button(text: str, variant: str | None = None, tooltip: str = "") -> QPushButton:
    button = QPushButton(text)
    if variant:
        button.setProperty("variant", variant)
    if tooltip:
        button.setToolTip(tooltip)
    return button


class MainWindow(QMainWindow):
    def __init__(self, store: ConnectionStore, service, theme: ThemeManager, about: AboutInfo,
                 default_timeout: int, parent=None):
        super().__init__(parent)
        self._store = store
        self._service = service
        self._theme = theme
        self._about = about
        self._current_uuid: str | None = None
        self._methods: list[str] = []
        self._pending = None  # 進行中工作的 tag：(kind, seq, uuid)

        self.setWindowTitle(about.name)
        self.resize(1100, 700)
        self.setMinimumSize(900, 560)
        self._build_ui(default_timeout)
        self._build_shortcuts()
        self._connect_signals()
        self._theme.themeChanged.connect(self._on_theme_changed)
        self._reset_status()
        self._load_initial_connections()

    # ---------- 版面 ----------

    def _build_ui(self, default_timeout: int) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_workspace(default_timeout), 1)
        self.setCentralWidget(central)

        self.status_state = QLabel()
        self.status_state.setObjectName("StatusState")
        self.status_detail = QLabel()
        self.status_detail.setObjectName("StatusDetail")
        self.statusBar().addWidget(self.status_state)
        self.statusBar().addWidget(self.status_detail, 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        title = QLabel(self._about.name)
        title.setObjectName("AppTitle")
        title.setWordWrap(True)
        self.connection_list = ConnectionList()

        self.theme_button = _button("◐ 主題", "subtle", "切換淺色 / 深色主題")
        self.theme_button.setMenu(self._build_theme_menu())
        self.about_button = _button("ⓘ 關於", "subtle")
        footer = QHBoxLayout()
        footer.setSpacing(4)
        footer.addWidget(self.theme_button)
        footer.addWidget(self.about_button)
        footer.addStretch(1)

        layout.addWidget(title)
        layout.addWidget(self.connection_list, 1)
        layout.addLayout(footer)
        return sidebar

    def _build_theme_menu(self) -> QMenu:
        menu = QMenu(self)
        group = QActionGroup(menu)
        group.setExclusive(True)
        self.theme_actions: dict[ThemeMode, QAction] = {}
        for mode, label in THEME_LABELS.items():
            action = QAction(label, menu)
            action.setCheckable(True)
            action.setChecked(mode is self._theme.mode)
            action.triggered.connect(lambda _checked=False, m=mode: self._theme.set_mode(m))
            group.addAction(action)
            menu.addAction(action)
            self.theme_actions[mode] = action
        return menu

    def _build_workspace(self, default_timeout: int) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(12)

        layout.addWidget(self._build_request_card(default_timeout))
        self.notification = NotificationBar()
        layout.addWidget(self.notification)

        self.request_editor = XmlEditor(self._theme.palette.xml)
        self.response_editor = XmlEditor(self._theme.palette.xml, read_only=True)
        self.format_button = _button("格式化", "subtle", "格式化請求 XML (Ctrl+Shift+F)")
        self.copy_button = _button("複製", "subtle", "複製回應結果")
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.addWidget(self._editor_panel("請求參數（多個用 #~# 隔開）", self.format_button, self.request_editor))
        splitter.addWidget(self._editor_panel("回應結果", self.copy_button, self.response_editor))
        splitter.setSizes([1, 1])
        layout.addWidget(splitter, 1)
        return workspace

    def _build_request_card(self, default_timeout: int) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("NameEdit")
        self.name_edit.setPlaceholderText("請輸入配置名稱")
        self.name_edit.setMaxLength(100)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("http://host/path?WSDL")
        self.load_button = _button(LOAD_LABEL, tooltip="讀取 WSDL 的服務方法 (F3)")
        url_row = QHBoxLayout()
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(self.load_button)

        self.url_hint = QLabel("結尾請加上 ?WSDL")
        self.url_hint.setObjectName("Hint")
        self.url_hint.hide()

        self.method_combo = QComboBox()
        self.method_combo.setEditable(True)
        self.method_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.method_combo.lineEdit().setPlaceholderText("選擇或搜尋服務方法")
        completer = QCompleter(self.method_combo.model(), self.method_combo)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.method_combo.setCompleter(completer)

        timeout_label = QLabel("逾時")
        timeout_label.setObjectName("FieldLabel")
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(TIMEOUT_MIN, TIMEOUT_MAX)
        self.timeout_spin.setSuffix(" 秒")
        self.timeout_spin.setValue(min(max(default_timeout, TIMEOUT_MIN), TIMEOUT_MAX))
        self.run_button = _button(RUN_LABEL, "primary", "執行請求 (F5)")
        self.clear_button = _button("清空", tooltip="清空請求與回應 (F6)")
        method_row = QHBoxLayout()
        method_row.addWidget(self.method_combo, 1)
        method_row.addWidget(timeout_label)
        method_row.addWidget(self.timeout_spin)
        method_row.addWidget(self.run_button)
        method_row.addWidget(self.clear_button)

        layout.addWidget(self.name_edit)
        layout.addLayout(url_row)
        layout.addWidget(self.url_hint)
        layout.addLayout(method_row)
        return card

    @staticmethod
    def _editor_panel(title: str, button: QPushButton, editor: XmlEditor) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        header.addWidget(label)
        header.addStretch(1)
        header.addWidget(button)
        layout.addLayout(header)
        layout.addWidget(editor, 1)
        return panel

    def _build_shortcuts(self) -> None:
        for key, handler in (
            ("F1", self._on_add_requested),
            ("F2", self._on_delete_current),
            ("F3", self.load_button.click),
            ("F5", self.run_button.click),
            ("F6", self._on_clear),
            ("Ctrl+Shift+F", self._on_format),
            ("Esc", self.close),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)

    def _connect_signals(self) -> None:
        self.connection_list.selectionChanged.connect(self._on_selection_changed)
        self.connection_list.addRequested.connect(self._on_add_requested)
        self.connection_list.deleteRequested.connect(self._on_delete_requested)
        self.name_edit.editingFinished.connect(self._commit_name)
        self.url_edit.editingFinished.connect(self._commit_url)
        self.url_edit.textChanged.connect(self._update_url_hint)
        self.clear_button.clicked.connect(self._on_clear)
        self.format_button.clicked.connect(self._on_format)
        self.copy_button.clicked.connect(self._on_copy)
        self.about_button.clicked.connect(self._show_about)

    # ---------- 連線資料 ----------

    def _load_initial_connections(self) -> None:
        if self._store.recovered_from_corruption:
            self._notify("warning", f"連線設定檔無法讀取，已備份為 {self._store.backup_path.name} 並重新建立")
        if not self._store.all():
            self._store.add()
            if not self._store.recovered_from_corruption:
                self._notify("info", "請輸入配置名稱與 WSDL 網址（結尾加上 ?WSDL），再按「讀取 WSDL」")
        self.connection_list.set_connections(self._store.all())

    def _current_connection(self) -> Connection | None:
        return self._store.get(self._current_uuid) if self._current_uuid else None

    @Slot(str)
    def _on_selection_changed(self, uuid: str) -> None:
        if self._current_uuid and self._current_uuid != uuid:
            self._commit_fields()  # 切換前先保存上一筆尚未確認的編輯
        self._current_uuid = uuid or None
        conn = self._current_connection()
        self.name_edit.setText(conn.name if conn else "")
        self.url_edit.setText(conn.url if conn else "")
        self._set_methods(conn.methods if conn else [])

    def _commit_fields(self) -> None:
        self._commit_name()
        self._commit_url()

    def _commit_name(self) -> None:
        conn = self._current_connection()
        name = self.name_edit.text().strip()
        if conn is not None and name != conn.name:
            self._store.rename(conn.uuid, name)
            self.connection_list.update_connection(self._store.get(conn.uuid))

    def _commit_url(self) -> None:
        conn = self._current_connection()
        url = self.url_edit.text().strip()
        if conn is not None and url != conn.url:
            self._store.set_url(conn.uuid, url)
            self.connection_list.update_connection(self._store.get(conn.uuid))

    def _set_methods(self, methods: list[str]) -> None:
        self._methods = list(methods)
        self.method_combo.clear()
        self.method_combo.addItems(self._methods)
        if self._methods:
            self.method_combo.setCurrentIndex(0)

    def _update_url_hint(self, text: str) -> None:
        url = text.strip()
        self.url_hint.setVisible(bool(url) and not url.lower().endswith("?wsdl"))

    def _on_add_requested(self) -> None:
        if self._pending:
            return
        self._commit_fields()
        conn = self._store.add()
        self.connection_list.set_connections(self._store.all(), select_uuid=conn.uuid)
        self.name_edit.setFocus()

    def _on_delete_current(self) -> None:
        if self._current_uuid:
            self._on_delete_requested(self._current_uuid)

    @Slot(str)
    def _on_delete_requested(self, uuid: str) -> None:
        if self._pending:
            return
        conn = self._store.get(uuid)
        if conn is None or not self._confirm("刪除連線", f"確定要刪除「{conn.name or UNNAMED}」嗎？"):
            return
        if uuid != self._current_uuid:
            self._commit_fields()
        keep = self._current_uuid if self._current_uuid != uuid else None
        self._current_uuid = None  # 避免把欄位內容寫回即將刪除的連線
        self._store.remove(uuid)
        if not self._store.all():
            self._store.add()
        self.connection_list.set_connections(self._store.all(), select_uuid=keep)
        self._notify("success", "已刪除連線")

    # ---------- 編輯器工具 ----------

    def _on_clear(self) -> None:
        if self._pending:
            return
        self.request_editor.clear()
        self.response_editor.clear()
        self._reset_status()

    def _on_format(self) -> None:
        text = self.request_editor.toPlainText()
        if not text.strip():
            return
        try:
            formatted = format_xml(text)
        except ValueError:
            self._notify("warning", "請求內容不是合法的 XML，無法格式化")
            return
        cursor = self.request_editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(formatted)  # 用游標取代，保留復原紀錄

    def _on_copy(self) -> None:
        text = self.response_editor.toPlainText()
        if not text:
            self._notify("info", "沒有可複製的回應內容")
            return
        QGuiApplication.clipboard().setText(text)
        self._notify("success", "已複製回應結果")

    # ---------- 狀態、通知、主題 ----------

    def _set_status(self, state: str, label: str, detail: str = "") -> None:
        self.status_state.setProperty("state", state)
        repolish(self.status_state)
        self.status_state.setText(label)
        self.status_detail.setText(detail)

    def _reset_status(self) -> None:
        self._set_status("", "就緒")

    def _notify(self, level: str, text: str) -> None:
        self.notification.show_message(level, text)

    @Slot(object)
    def _on_theme_changed(self, palette: ThemePalette) -> None:
        self.request_editor.set_colors(palette.xml)
        self.response_editor.set_colors(palette.xml)
        for mode, action in self.theme_actions.items():
            action.setChecked(mode is self._theme.mode)

    def _show_about(self) -> None:
        about = self._about
        QMessageBox.about(
            self,
            f"關於 {about.name}",
            f"<h3>{about.name}</h3>"
            f"<p>版本 {about.version}</p>"
            "<p>這是一款針對 WebService 設計的開源工具，簡單好用、配置靈活。</p>"
            f"<p><a href='{about.website}'>{about.website}</a></p>"
            "<p>原創：Tiger Tseng</p>"
            f"<p>{about.copyright}</p>",
        )

    def _confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self, title, text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:
        if not self._confirm("離開程式", "確定要離開嗎？"):
            event.ignore()
            return
        self._commit_fields()
        self._pending = None
        event.accept()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_main_window.py -v`
Expected: 全部 PASS（19 個測試）

- [ ] **Step 5: 執行全部測試**

Run: `uv run pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui/main_window.py tests/test_main_window.py
```

訊息：

```
新增主視窗版面、連線編輯與主題切換

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 9: 主視窗背景讀取、執行與取消

**Files:**
- Modify: `src/ui/main_window.py`
- Test: `tests/test_main_window.py`（附加測試）

**Interfaces:**
- Consumes: `run_in_background`（Task 5）、`ParamCountMismatch`、`CallResult`（Task 2）、Task 8 的 `MainWindow`
- Produces: 讀取 / 執行按鈕的完整行為；進行中時按鈕文字為 `CANCEL_LABEL`

- [ ] **Step 1: 附加失敗測試**

在 `tests/test_main_window.py` 最上方的 import 區塊加入：

```python
import threading

from PySide6.QtCore import QCoreApplication, QThreadPool

from src.core.soap_service import ParamCountMismatch
from src.ui.main_window import CANCEL_LABEL, LOAD_LABEL, RUN_LABEL
from tests.helpers import wait_until
```

在檔案最後附加：

```python
def test_load_success_saves_methods(env):
    uuid = seed(env.store, methods=())
    window = env.make()
    window.load_button.click()
    wait_until(lambda: env.store.get(uuid).methods)
    assert env.store.get(uuid).methods == ["AddTwo", "GetPOData"]
    assert combo_items(window.method_combo) == ["AddTwo", "GetPOData"]
    assert window.request_editor.toPlainText() == '<?xml version="1.0" encoding="utf-8"?>'
    assert (window.status_state.text(), window.status_detail.text()) == ("● 成功", "讀取完成 · 2 個方法")
    assert window.load_button.text() == LOAD_LABEL
    assert env.service.calls == [("load", "http://prod/ws?WSDL", 30)]


def test_load_keeps_existing_request(env):
    seed(env.store, methods=())
    window = env.make()
    window.request_editor.setPlainText("<Request/>")
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.request_editor.toPlainText() == "<Request/>"


def test_load_uses_unsaved_url(env):
    uuid = seed(env.store)
    window = env.make()
    window.url_edit.setText("http://typed/ws?WSDL")  # 尚未觸發 editingFinished
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert env.service.calls == [("load", "http://typed/ws?WSDL", 30)]
    assert env.store.get(uuid).url == "http://typed/ws?WSDL"


def test_load_without_url_warns(env):
    seed(env.store, url="")
    window = env.make()
    window.load_button.click()
    assert window.notification.level == "warning"
    assert window.notification.text == "請填寫 WSDL 網址"
    assert env.service.calls == []


def test_load_failure_shows_error(env):
    seed(env.store)
    env.service.error = ConnectionError("連不上")
    window = env.make()
    window.load_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "error"
    assert window.notification.text == "讀取 WSDL 失敗：連不上"
    assert window.load_button.isEnabled() and window.run_button.isEnabled()


def test_run_success_shows_response_and_stats(env):
    seed(env.store)
    window = env.make()
    window.request_editor.setPlainText("<Request/>")
    window.timeout_spin.setValue(45)
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.response_editor.toPlainText() == "<ok/>\n"
    assert window.status_detail.text() == "0.12 s · 5 B"
    assert window.run_button.text() == RUN_LABEL
    assert env.service.calls == [("call", "http://prod/ws?WSDL", "GetPOData", "<Request/>", 45)]


def test_run_requires_known_method(env):
    seed(env.store, methods=())
    window = env.make()
    window.run_button.click()
    assert window.notification.level == "warning"
    assert window.notification.text == "請選擇服務方法（可先按「讀取 WSDL」取得清單）"
    assert env.service.calls == []


def test_run_param_mismatch_shows_warning(env):
    seed(env.store)
    env.service.error = ParamCountMismatch(2, 1)
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "warning"
    assert window.notification.text == str(ParamCountMismatch(2, 1))
    assert window.status_detail.text() == "參數數量不符"


def test_run_failure_shows_error(env):
    seed(env.store)
    env.service.error = TimeoutError("timed out")
    window = env.make()
    window.run_button.click()
    wait_until(lambda: window.status_state.text() == "● 失敗")
    assert window.notification.level == "error"
    assert window.notification.text == "請求失敗：timed out"


def test_busy_state_disables_other_actions(env):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make()
    window.run_button.click()
    assert window.run_button.text() == CANCEL_LABEL and window.run_button.isEnabled()
    assert not window.load_button.isEnabled()
    assert not window.clear_button.isEnabled()
    assert not window.url_edit.isEnabled()
    assert not window.connection_list.list_view.isEnabled()
    assert window.status_state.text() == "執行中…"
    env.service.gate.set()
    wait_until(lambda: window.status_state.text() == "● 成功")
    assert window.load_button.isEnabled() and window.connection_list.list_view.isEnabled()


def test_cancel_ignores_late_result(env):
    seed(env.store)
    env.service.gate = threading.Event()
    window = env.make()
    window.run_button.click()
    window.run_button.click()  # 取消
    assert window.run_button.text() == RUN_LABEL
    assert window.load_button.isEnabled()
    assert window.status_state.text() == "已取消"
    env.service.gate.set()
    QThreadPool.globalInstance().waitForDone(3000)
    QCoreApplication.processEvents()
    assert window.response_editor.toPlainText() == ""
    assert window.status_state.text() == "已取消"


def test_cancel_load(env):
    uuid = seed(env.store, methods=())
    env.service.gate = threading.Event()
    window = env.make()
    window.load_button.click()
    assert window.load_button.text() == CANCEL_LABEL
    window.load_button.click()
    env.service.gate.set()
    QThreadPool.globalInstance().waitForDone(3000)
    QCoreApplication.processEvents()
    assert env.store.get(uuid).methods == []
    assert window.load_button.text() == LOAD_LABEL
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_main_window.py -v`
Expected: 新增的 12 個測試 FAIL（例如 `test_load_success_saves_methods` 因 `wait_until` 逾時而 `AssertionError: 等待條件逾時`，`test_load_without_url_warns` 因沒有通知而失敗）；Task 8 的 19 個測試仍 PASS

- [ ] **Step 3: 實作背景讀取與執行**

在 `src/ui/main_window.py` 的 import 區塊加入：

```python
from loguru import logger
```

並把 `from src.core.soap_service import format_xml` 改為：

```python
from src.core.soap_service import CallResult, ParamCountMismatch, format_xml
```

並加入：

```python
from src.ui.workers import run_in_background
```

在 `__init__` 的 `self._pending = None ...` 下一行加入：

```python
        self._seq = 0
        self._tasks = {}  # tag -> Task，保留參照直到收到回呼
```

在 `_connect_signals` 的 `self.clear_button.clicked.connect(self._on_clear)` 前加入：

```python
        self.load_button.clicked.connect(self._on_load_clicked)
        self.run_button.clicked.connect(self._on_run_clicked)
```

在 `# ---------- 編輯器工具 ----------` 區塊之前加入新區塊：

```python
    # ---------- 背景讀取與執行 ----------

    def _on_load_clicked(self) -> None:
        if self._pending:
            if self._pending[0] == "load":
                self._cancel()
            return
        self._commit_fields()
        url = self.url_edit.text().strip()
        if not url:
            self._notify("warning", "請填寫 WSDL 網址")
            return
        self._start("load", self._service.load_methods, url, self.timeout_spin.value())

    def _on_run_clicked(self) -> None:
        if self._pending:
            if self._pending[0] == "run":
                self._cancel()
            return
        self._commit_fields()
        url = self.url_edit.text().strip()
        method = self.method_combo.currentText().strip()
        if not url:
            self._notify("warning", "請填寫 WSDL 網址")
            return
        if method not in self._methods:
            self._notify("warning", "請選擇服務方法（可先按「讀取 WSDL」取得清單）")
            return
        self.response_editor.clear()
        self._start("run", self._service.call, url, method,
                    self.request_editor.toPlainText(), self.timeout_spin.value())

    def _start(self, kind: str, fn, *args) -> None:
        self._seq += 1
        tag = (kind, self._seq, self._current_uuid)
        self._pending = tag
        self._set_busy(kind)
        self._set_status("busy", "讀取中…" if kind == "load" else "執行中…")
        self._tasks[tag] = run_in_background(
            tag, fn, *args, on_success=self._on_task_succeeded, on_failure=self._on_task_failed
        )

    def _cancel(self) -> None:
        self._finish()
        self._set_status("", "已取消")
        self._notify("info", "已取消。背景請求會在逾時後自動結束")

    def _finish(self) -> None:
        self._pending = None
        self._set_busy(None)

    def _set_busy(self, kind: str | None) -> None:
        busy = kind is not None
        self.load_button.setText(CANCEL_LABEL if kind == "load" else LOAD_LABEL)
        self.run_button.setText(CANCEL_LABEL if kind == "run" else RUN_LABEL)
        self.load_button.setEnabled(kind in (None, "load"))
        self.run_button.setEnabled(kind in (None, "run"))
        for widget in (self.clear_button, self.name_edit, self.url_edit, self.method_combo, self.timeout_spin):
            widget.setEnabled(not busy)
        self.connection_list.set_busy(busy)

    @Slot(object, object)
    def _on_task_succeeded(self, tag, value) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return  # 已取消或被新的請求取代
        self._finish()
        kind, _seq, uuid = tag
        if kind == "load":
            self._on_methods_loaded(uuid, value)
        else:
            self._on_call_finished(value)

    @Slot(object, object)
    def _on_task_failed(self, tag, error) -> None:
        self._tasks.pop(tag, None)
        if tag != self._pending:
            return
        self._finish()
        if isinstance(error, ParamCountMismatch):
            self._notify("warning", str(error))
            self._set_status("error", "● 失敗", "參數數量不符")
            return
        action = "讀取 WSDL 失敗" if tag[0] == "load" else "請求失敗"
        logger.opt(exception=error).error(action)
        self._notify("error", f"{action}：{error}")
        self._set_status("error", "● 失敗", action)

    def _on_methods_loaded(self, uuid: str, methods: list[str]) -> None:
        self._store.set_methods(uuid, methods)
        self.connection_list.update_connection(self._store.get(uuid))
        if uuid == self._current_uuid:
            self._set_methods(methods)
        if not self.request_editor.toPlainText().strip():
            self.request_editor.setPlainText(XML_DECLARATION)
        self._set_status("success", "● 成功", f"讀取完成 · {len(methods)} 個方法")
        self._notify("success", f"已讀取 {len(methods)} 個服務方法")

    def _on_call_finished(self, result: CallResult) -> None:
        self.response_editor.setPlainText(result.text)
        self._set_status("success", "● 成功", f"{result.elapsed:.2f} s · {format_size(result.size)}")
```

- [ ] **Step 4: 執行測試確認通過**

Run: `uv run pytest tests/test_main_window.py -v`
Expected: 全部 PASS（31 個測試）

- [ ] **Step 5: 執行全部測試**

Run: `uv run pytest -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui/main_window.py tests/test_main_window.py
```

訊息：

```
主視窗加入背景讀取 WSDL、執行請求與取消

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

---

### Task 10: 新進入點、移除 wxPython、版本與文件、打包驗證

**Files:**
- Modify: `src/ws_tool.py`（整個改寫）
- Modify: `src/app_data/ws_tool.yaml:5`
- Modify: `pyproject.toml`（移除 wxpython）
- Modify: `README.md`
- Delete: `src/ui/main/`、`src/utils/darkmode.py`、`src/utils/toaster.py`、`src/utils/balloontip.py`、`fbp/`
- Test: `tests/test_entry_point.py`

**Interfaces:**
- Consumes: 全部前面 Task 的產出；`WebServiceConfig`（既有，`src/config/web_service_config.py`）；`pathutil.resource_abspath` / `resource_path`（既有）
- Produces: `src/ws_tool.py` 的 `main()`；直接執行 `python src/ws_tool.py`、`python -m src.ws_tool`、PyInstaller exe 都能啟動

- [ ] **Step 1: 寫失敗測試**

`tests/test_entry_point.py`：

```python
# -*- coding: utf-8 -*-
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_entry_point_imports_when_run_as_script():
    """用 --file 方式執行（PyQtInspect、IDE）時，src 套件必須能被匯入"""
    # 移除目前目錄，模擬 IDE / PyQtInspect 以腳本方式執行時 sys.path 不含專案根目錄的情況
    code = (
        "import os, runpy, sys; "
        "sys.path[:] = [p for p in sys.path if p not in ('', os.getcwd())]; "
        "ns = runpy.run_path('src/ws_tool.py', run_name='not_main'); "
        "print(callable(ns.get('main')))"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


def test_no_wx_imports_left():
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "src").rglob("*.py")
        if "import wx" in path.read_text(encoding="utf-8") or "from wx" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `uv run pytest tests/test_entry_point.py -v`
Expected: 2 個 FAIL（`test_entry_point_imports_when_run_as_script` 的子程序因 `ModuleNotFoundError: No module named 'src'` 以非 0 結束；`test_no_wx_imports_left` 列出多個 wx 檔案）

- [ ] **Step 3: 改寫進入點**

`src/ws_tool.py` 全部改為：

```python
# -*- coding: utf-8 -*-
"""
啟動
"""
import sys
from pathlib import Path

if not getattr(sys, "frozen", False) and __package__ in (None, ""):
    # 以腳本方式執行（IDE、PyQtInspect --file）時，讓 src 套件可以被匯入
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import os  # noqa: E402

from loguru import logger  # noqa: E402
from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from src.config.web_service_config import WebServiceConfig  # noqa: E402
from src.core.connection_store import ConnectionStore  # noqa: E402
from src.core.soap_service import SoapService  # noqa: E402
from src.ui.main_window import AboutInfo, MainWindow  # noqa: E402
from src.ui.theme import ThemeManager  # noqa: E402
from src.utils import pathutil  # noqa: E402

GITHUB_URL = "https://github.com/m121752332/webservice-py-tool"


def _install_excepthook() -> None:
    """未預期的例外寫入記錄檔並顯示對話框，避免打包後的 exe 直接閃退"""

    def hook(exc_type, exc, tb):
        logger.opt(exception=(exc_type, exc, tb)).error("未預期的錯誤")
        if QApplication.instance() is not None:
            QMessageBox.critical(None, "發生錯誤", f"{exc_type.__name__}: {exc}\n\n詳細內容已寫入記錄檔。")

    sys.excepthook = hook


def main() -> int:
    config = WebServiceConfig()
    logger.add(
        os.path.join(pathutil.resource_abspath(config.get_app_log_path()), "run.log"),
        retention=config.get_app_log_retention(),
        level=str(config.get_app_log_level()).upper(),
    )

    app = QApplication(sys.argv)
    app.setApplicationName(config.get_app_name())
    app.setWindowIcon(QIcon(pathutil.resource_path(config.get_app_img_path())))
    _install_excepthook()

    data_dir = pathutil.resource_abspath(config.get_app_connection_path())
    settings = QSettings(os.path.join(data_dir, "settings.ini"), QSettings.Format.IniFormat)
    theme = ThemeManager(app, settings)
    theme.apply()

    store = ConnectionStore(os.path.join(data_dir, config.get_app_connection_profile()))
    about = AboutInfo(
        name=config.get_app_name(),
        version=config.get_app_version(),
        copyright=config.get_app_copyright(),
        website=GITHUB_URL,
    )
    window = MainWindow(store, SoapService(), theme, about, default_timeout=config.get_app_timeout())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 移除舊 wx 介面與依賴**

```bash
git rm -r src/ui/main fbp src/utils/darkmode.py src/utils/toaster.py src/utils/balloontip.py
uv remove wxpython
```

Expected: `pyproject.toml` 的 `dependencies` 不再有 `wxpython`。

- [ ] **Step 5: 更新版本號**

`src/app_data/ws_tool.yaml` 第 5 行 `version: "v1.1.5"` 改為：

```yaml
  version: "v2.0.0"
```

- [ ] **Step 6: 執行測試確認通過**

Run: `uv run pytest -v`
Expected: 全部 PASS（含 `tests/test_entry_point.py` 的 2 個測試）

- [ ] **Step 7: 實際啟動 App 驗證**

Run（背景啟動 8 秒後確認程序仍在，再關閉）：

```bash
(uv run python src/ws_tool.py &) ; sleep 8; tasklist //FI "IMAGENAME eq python.exe" | tail -3; tail -5 src/app_data/logs/run.log
```

Expected: `tasklist` 看得到 python.exe；`run.log` 沒有新的 `ERROR`。不要用 `taskkill` 結束 python.exe（可能誤殺使用者其他 Python 程式），請使用者手動關閉視窗。

請使用者目視確認：跟隨系統 / 淺色 / 深色 切換時，標題列、選單、捲軸都跟著變色；讀取一個真實的 WSDL 並執行一次請求。

- [ ] **Step 8: 打包 exe 並驗證**

Run: `echo | cmd //c "D:\\GITLocal\\webservice-py-tool\\build.bat"`
Expected: 最後一行出現 `Build process finished: dist\WebService-Tool.exe`

```bash
ls -la dist/WebService-Tool.exe
(cd dist && ./WebService-Tool.exe &) ; sleep 8; tasklist //FI "IMAGENAME eq WebService-Tool.exe" | tail -2; taskkill //F //IM WebService-Tool.exe
```

Expected: exe 存在且程序持續執行；記錄大小（預期明顯大於舊版的約 26 MB，但不應超過 80 MB；若超過，回報給使用者再決定是否加 `--exclude-module`）。

- [ ] **Step 9: 更新 README**

把 `README.md` 從開頭到 `## 內置功能` 之前（不含）的內容換成：

````markdown
# 專案簡介

WebService服務部署到了服務器，但是只能本地訪問，下載soapui有點太大了，找其他的測試工具又沒有合適的，就自己寫了個比較簡單的小工具！

* Python 3.14
* PySide6（Essentials）6.11
* suds 1.2
* lxml 6.1
* PyInstaller 6.22

## 開發說明
1. 安裝依賴：`$ uv sync`（或 `$ pip install -r requirements.txt`，此檔由 `uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt` 產生）
2. 啟動程式：`$ uv run python src/ws_tool.py`
3. 執行測試：`$ uv run pytest`
4. UI 檢測工具（類似瀏覽器的「檢查元素」）：`$ uv run python -m PyQtInspect --direct --file src/ws_tool.py`
5. 打包 exe：執行根目錄的 `build.bat`，完成後會在 `dist` 目錄產生 `WebService-Tool.exe`
6. 暫時不支持mac環境打包，如果有想法也可以自己去找到合適的配套方案

## 介面
* 左側為連線清單（可搜尋、新增、刪除），右側為請求與回應工作區
* 左下角「主題」可切換 跟隨系統 / 淺色 / 深色
* 快捷鍵：F1 新增連線、F2 刪除連線、F3 讀取 WSDL、F5 執行、F6 清空、Ctrl+Shift+F 格式化請求、Esc 離開

## 版本產生
切到 src/config 底下輸入
`python grab_version.py C:\Windows\System32\WWAHost.exe`  
系統自動產生 file_version_info.txt 用於包裝到pyinstaller的版本檔案使用

````

並刪除 README 最後的 `## 畫面設計器預覽` 整段（含其下的 `<table>`），以及 `## 下載體驗` 中「下載畫面設計器」那一行。

- [ ] **Step 10: 重新產生 requirements.txt**

```bash
uv export --format requirements-txt --no-hashes --no-emit-project -o requirements.txt
```

Expected: `requirements.txt` 含 `pyside6-essentials`，不含 `wxpython`。

- [ ] **Step 11: 執行全部測試**

Run: `uv run pytest -v`
Expected: 全部 PASS

- [ ] **Step 12: Commit**

```bash
git add -A src pyproject.toml uv.lock requirements.txt README.md tests/test_entry_point.py
git status --short
```

確認 `git status` 沒有列出 `dist/`、`build/`、`*.log`、`settings.ini`。

訊息：

```
改用 PySide6 新介面並移除 wxPython

- 新進入點：主題、連線設定、全域例外處理
- 刪除舊 wx 介面、wxFormBuilder 設計檔與相關工具
- 版本升至 v2.0.0，更新 README 與 requirements.txt

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

- [ ] **Step 13: 提醒使用者**

回報時說明：README 的截圖（`docs/webservice_tool_00*.png`）仍是舊版畫面，需要使用者在新介面上重新擷取。
