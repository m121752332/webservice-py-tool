# 工具參數設定編輯器（ParameterTree 外掛）設計

- 日期：2026-09-26
- 分支：`feat/settings-editor`

## 1. 目標與範圍

把 `src/app_data/ws_tool.yaml` 的工具參數從「用文字編輯器改」變成程式內的可視化編輯：按 **F11** 把右側工作區換成 pyqtgraph `ParameterTree` 設定頁，改值後按「儲存」寫回 yaml，部分參數立即熱重載。

**範圍內**

- F11 切換右側工作區 ↔ 設定頁（左側連線清單保留）
- yaml 每個欄位正上方的註解作為唯讀標籤顯示
- 按「儲存」才寫檔；「還原」回到最後儲存的值；離開時未存檔詢問
- 寫回時只改值，註解、空行、縮排、換行符號原樣保留
- 熱重載：`app.name`、`app.version`、`app.copyright`、`app.img`、`app.timeout`
- 其餘欄位（`app.log.*`、`app.connection.*`）只存檔，提示「需重新啟動才會生效」
- 編輯器以**外掛資料夾**形式另外打包：主程式 exe 不含 pyqtgraph／numpy

**不在範圍內**

- 在 UI 內編輯註解、新增或刪除欄位
- `connections.profile`、`settings.ini` 的編輯
- log、connection 設定的熱重載
- 外掛版本管理、線上下載外掛
- 兩個獨立 exe 的打包方式（方案 B，僅在方案 A 不可行時才考慮；spike 已證實 A 可行）

**相容性要求**

- 現有 `ws_tool.yaml` 格式不變，未修改的欄位逐位元組保留
- 啟動流程（`WebServiceConfig` 讀 yaml）不變
- 沒有外掛時主程式所有既有功能照常運作

## 2. 可行性驗證（spike 結論）

於 repo 外暫存目錄以專案 `.venv`（Python 3.14.6 / AMD64）與 PyInstaller `-F -w` 驗證：

| 項目 | 結果 |
|---|---|
| 主程式僅含 PySide6 | 41.5 MB |
| 主程式加上外掛所需 hiddenimports | 45.7 MB（+4.2 MB） |
| 外掛資料夾（pyqtgraph 0.14.0 + numpy 2.5.3 + colorama） | 47 MB（未壓縮） |
| 執行期 `sys.path` 加入外掛資料夾後 import 並操作 ParameterTree | 成功，pyqtgraph 自動沿用主程式的 PySide6 |

兩個必要條件：

1. **主程式必須預先打包外掛會用到的模組**。PyInstaller 只打包主程式靜態可見的模組；實測缺 `platform`（標準庫）與 `PySide6.QtOpenGL`、`QtOpenGLWidgets`、`QtSvg`、`QtTest`。以腳本實際載入外掛、列出 `sys.modules` 中的標準庫與 `PySide6.*` 模組，產生 hiddenimports 清單解決。
2. **外掛必須以與主程式相同的 Python 版本／平台建置**，用專案 `.venv` 的直譯器執行 `uv pip install --target` 即可保證。

## 3. 架構

```
主程式（WebService-Tool.exe，不含 pyqtgraph）
├─ src/config/app_settings.py   新增：yaml 讀取、標籤擷取、保留註解寫回、變更分類（不依賴 Qt）
├─ src/ui/plugin_loader.py      新增：尋找外掛資料夾、加入 sys.path、import
├─ src/ui/settings_page.py      新增：設定頁外框（按鈕列、通知列、外掛元件或佔位畫面）
├─ src/ui/main_window.py        修改：右側 QStackedWidget、F11、apply_app_settings()
└─ src/ws_tool.py               修改：把 ws_tool.yaml 絕對路徑傳給 MainWindow

外掛（plugins/settings_editor/，另外打包）
├─ settings_editor.py           SettingsTree：欄位清單 ↔ ParameterTree
├─ gen_host_imports.py          產生 host_imports.txt
├─ host_imports.txt             主程式需額外打包的模組清單（納入版控）
└─ build_plugin.py              建置 dist/plugins/settings_editor/
```

**邊界原則**

- 外掛只負責顯示與收集值，不 import `src.*`；與主程式之間只傳遞 dict、list、str 等基本型別
- 存檔、比對、按鈕、通知、熱重載全部在主程式，可在沒有 pyqtgraph 的情況下測試核心邏輯
- 外掛不寫死顏色，由主程式傳入目前主題色票

## 4. 設定文件（`src/config/app_settings.py`）

### 4.1 資料結構

```python
FieldKind = Literal["group", "str", "int", "float", "bool", "list"]

@dataclass(frozen=True)
class SettingField:
    key: str                 # 以點分隔的路徑，例如 "app.log.level"
    label: str               # 正上方註解；無註解時為 key 的最後一段
    kind: FieldKind
    value: object = None     # group 為 None
    limits: tuple | None = None  # int：(最小, 最大)；list：選項

@dataclass(frozen=True)
class SettingsChanges:
    hot: tuple[str, ...]      # 需熱重載的 key（依文件順序）
    restart: tuple[str, ...]  # 需重新啟動的 key

@dataclass(frozen=True)
class AppSettings:           # 熱重載用的五個值
    name: str
    version: str
    copyright: str
    img: str
    timeout: int

class SettingsError(Exception): ...
```

### 4.2 `SettingsDocument` 介面

```python
HOT_RELOAD_KEYS = ("app.name", "app.version", "app.copyright", "app.img", "app.timeout")

class SettingsDocument:
    @classmethod
    def load(cls, path) -> "SettingsDocument"  # 讀檔失敗或格式不支援時丟 SettingsError
    path: Path
    fields: list[SettingField]                 # 依文件順序，含 group
    def values(self) -> dict[str, object]      # 只含葉節點
    def app_settings(self) -> AppSettings
    def changes(self, new_values: dict[str, object]) -> SettingsChanges
    def render(self, new_values: dict[str, object]) -> str
    def save(self, new_values: dict[str, object]) -> "SettingsDocument"  # 回傳重新載入後的文件
```

- 不在 `HOT_RELOAD_KEYS` 內的葉節點一律歸類為 `restart`
- `new_values` 只需包含要變更的 key；未知的 key 丟 `SettingsError`
- 與現值相同的 key 不算變更

### 4.3 解析規則

- 值由 `yaml.safe_load` 解析；只支援巢狀 mapping + 純量值，遇到 list、多行字串、錨點等丟 `SettingsError`
- 另外逐行掃描記錄每個 key 的行號、縮排、值的位置與引號風格：以縮排推算父層路徑
- **標籤**：key 正上方**連續**的整行註解（`#` 開頭，去掉 `#` 與前後空白後以換行串接）；中間隔空行即中斷；沒有註解則用 key 名稱
- **型別**：依 PyYAML 結果推斷 `str`／`int`／`float`／`bool`；mapping 為 `group`。特例：
  - `app.timeout`：`int`，`limits=(5, 120)`（與 `main_window.TIMEOUT_MIN/MAX` 一致，常數移到 `app_settings` 由兩邊共用）
  - `app.log.level`：`list`，選項為 loguru 等級 `trace`、`debug`、`info`、`success`、`warning`、`error`、`critical`（現值轉小寫後顯示；只有使用者改選時才寫回，寫回為小寫）

### 4.4 寫回規則

- 只替換有變更那一行的「值」部分；其他字元（含註解行、空行、行尾 `# 註解`、`\r\n` 換行）完全不動
- 引號：原值為雙引號 → 輸出雙引號並跳脫 `\` 與 `"`；原值為單引號 → 單引號並把 `'` 變成 `''`；原值無引號 → 若無引號輸出後以 PyYAML 解析會得到不同的值或型別（例如字串 `"123"`、`"true"`、含 `: ` 或 `#`），自動改用雙引號
- bool 輸出 `true`／`false`，數字以 `str()` 輸出
- **驗證**：寫檔前以 PyYAML 解析 `render()` 結果，逐一比對所有葉節點應等於預期值，不符丟 `SettingsError`
- **寫入**：UTF-8，先寫同目錄暫存檔再 `os.replace`；任一步失敗原檔不動
- 型別不符（例如 int 欄位給字串）或超出 `limits` 丟 `SettingsError`

## 5. 外掛（`plugins/settings_editor/settings_editor.py`）

```python
API_VERSION = 1

class SettingsTree(QWidget):
    valueChanged = Signal()
    valueEditing = Signal()          # 選用
    def load(self, fields: list[dict]) -> None
    def values(self) -> dict[str, object]
    def commit(self) -> None         # 選用
    def set_palette(self, colors: dict[str, str]) -> None
```

- `fields` 每筆為 `{"key", "label", "kind", "value", "limits"}`（由 `SettingField` 轉成 dict）；依 `key` 的父子關係建立 `Parameter` 群組
- 每個 `Parameter` 的 `title` 為 `label`、`tip` 為 `key`；`name` 使用 key 最後一段
- `values()` 回傳所有葉節點 `{key: 值}`
- `load()` 期間不發出 `valueChanged`
- pyqtgraph 的文字欄位要等 `editingFinished`、數值欄位要等編輯完成或延遲後才把值寫入參數；輸入途中 `values()` 仍是舊值：
  - `valueEditing`：使用者輸入中（值尚未提交）時發出；程式設定值與 `load()` 不發出
  - `commit()`：把輸入中尚未提交的值寫入參數（數值欄位的無效文字比照失去焦點時捨棄）；有值改變時照常發出 `valueChanged`
  - 兩者皆為選用、不影響 `API_VERSION`；主程式以 `getattr` 取用，缺少時略過
- `set_palette()` 的 `colors` 為 `ThemePalette` 除 `name`、`xml` 以外的欄位；用來設定樹的 QSS 以及 pyqtgraph 群組列的底色與文字色
- 主程式載入外掛後檢查 `API_VERSION == 1`，不符視同未安裝

## 6. 主程式 UI

### 6.1 `plugin_loader.py`

```python
PLUGIN_NAME = "settings_editor"

def plugin_dir() -> Path          # 打包後：<exe 目錄>/plugins/settings_editor；開發時：<repo>/plugins/settings_editor
def load_settings_plugin(directory: Path | None = None) -> ModuleType | None
```

- 把 `<dir>/site-packages`（若存在）與 `<dir>` 加到 `sys.path` 最前面（不重複加入），再 import `settings_editor`
- 資料夾不存在、import 失敗、`API_VERSION` 不符 → 記錄 log 並回傳 `None`，不丟例外
- 結果快取，只載入一次

### 6.2 `settings_page.py`

```python
class SettingsPage(QWidget):
    saved = Signal(object, object)   # (SettingsDocument, SettingsChanges)
    backRequested = Signal()
    def __init__(self, plugin: ModuleType | None, palette: ThemePalette, parent=None)
    def open(self, path: Path) -> None     # 每次進入都重新讀檔
    def is_dirty(self) -> bool
    def save(self) -> bool                 # 成功回傳 True
    def revert(self) -> None
    def set_palette(self, palette: ThemePalette) -> None
```

- 版面：標題「工具參數設定」＋按鈕列「儲存」(`green`)、「還原」、「返回」(沿用 `_button`、`variant`、`HoverLift`)；下方自有 `NotificationBar`；再下方為 `SettingsTree`
- 外掛為 `None` 時顯示佔位畫面「設定編輯器外掛未安裝」並說明外掛應放置的資料夾路徑；「儲存」「還原」停用
- `open()` 讀檔失敗：顯示 error 通知，「儲存」停用
- 未修改時「儲存」「還原」停用；`valueChanged` 後依目前值是否與檔案不同更新；`valueEditing` 時立即啟用（使用者一開始輸入即可儲存）
- `is_dirty()` 與 `save()` 先呼叫外掛的 `commit()`，確保離開（F11／Esc／返回／關窗）前的詢問與寫回都包含輸入中尚未提交的值
- `save()`：`SettingsDocument.save()` 失敗 → error 通知並回傳 False；成功 → 發出 `saved`，並顯示：
  - 只有熱重載欄位：success「設定已儲存並套用」
  - 含需重啟欄位：warning「已儲存，以下設定需重新啟動才會生效：app.log.level、…」

### 6.3 `main_window.py`

- 建構子新增參數 `settings_path: Path`；右側改為 `QStackedWidget`：索引 0 為既有工作區，索引 1 為 `SettingsPage`（首次按 F11 時才載入外掛並建立）
- **F11**：工作區 → 呼叫 `settings_page.open(settings_path)` 並切換；設定頁 → 等同「返回」
- 設定頁中 **Esc** 等同「返回」；工作區中 Esc 維持離開程式
- **返回**：若 `is_dirty()`，詢問「儲存／不儲存／取消」；儲存失敗或取消則留在設定頁
- 回到工作區時，若設定頁通知列仍顯示 warning／error（例如從詢問選「儲存」後的需重新啟動、找不到圖示），同樣的等級與文字轉送到工作區通知列
- 設定頁顯示期間：左側 `Sidebar` 停用；F1～F6、Ctrl+Shift+F 快捷鍵停用；回到工作區後恢復
- `closeEvent`：設定頁有未存檔修改時先詢問儲存／不儲存／取消，再走既有「確定要離開嗎？」
- `saved` 訊號：`changes.hot` 非空時呼叫 `apply_app_settings(doc.app_settings(), changes.hot)`
- `apply_app_settings(settings: AppSettings, keys: Iterable[str] = HOT_RELOAD_KEYS)`：只套用 `keys` 列出的欄位（未變更的欄位不動，例如只改名稱時保留使用者本次手動調整的逾時）
  - `app.name`：視窗標題、側欄標題、`QApplication.setApplicationName`、`self._about.name`
  - `app.version`、`app.copyright`：更新 `self._about` 對應欄位（`website` 沿用）
  - `app.img`：以 `pathutil.resource_path` 解析；檔案存在才 `QApplication.setWindowIcon`，否則保留原圖示並在設定頁顯示 warning
  - `app.timeout`：`timeout_spin.setValue`（限制在 5～120）
- `themeChanged` 時同步呼叫 `settings_page.set_palette()`

### 6.4 `ws_tool.py`

- 以 `WebServiceConfig.config_path`（程式啟動時實際讀取的 `ws_tool.yaml` 絕對路徑）傳給 `MainWindow(settings_path=...)`，確保設定頁編輯的就是正在使用的那一份

## 7. 打包

- `pyproject.toml`：`dev` 群組加入 `pyqtgraph==0.14.0`、`numpy==2.5.3`（固定版本）；`dependencies` 不變
- `gen_host_imports.py`：在 offscreen 模式實際建立 `SettingsTree` 並 `load()` 一份範例欄位，將 `sys.modules` 中的標準庫（`sys.stdlib_module_names`，排除 `_` 開頭）與 `PySide6.*` 模組排序寫入 `host_imports.txt`；PyInstaller 回報找不到的模組（如 `collections.abc`）無害，保留
- `build.bat`：打包主程式時逐行讀取 `host_imports.txt` 加上 `--hidden-import`，其餘參數不變；接著執行 `uv run python plugins/settings_editor/build_plugin.py`
- `build_plugin.py`：清空並建立 `dist/plugins/settings_editor/`；以專案 `.venv` 直譯器 `uv pip install --target .../site-packages pyqtgraph==0.14.0 numpy==2.5.3`；複製 `settings_editor.py`；刪除 `pyqtgraph/examples`、所有 `__pycache__`
- 升級 pyqtgraph 或 numpy 時：同步修改 `pyproject.toml` 與 `build_plugin.py` 的版本，重跑 `gen_host_imports.py`

## 8. 錯誤處理

| 情境 | 行為 |
|---|---|
| 外掛不存在／import 失敗／API 版本不符 | 設定頁顯示「設定編輯器外掛未安裝」與預期路徑，log 記錄原因 |
| yaml 讀取失敗或格式不支援 | 設定頁 error 通知，儲存停用 |
| 寫回驗證失敗、寫檔失敗 | error 通知，原檔不動，留在設定頁 |
| `img` 檔案不存在 | 仍存檔；保留原圖示，warning 通知 |
| 使用者在設定頁期間於外部修改 yaml | 儲存時以設定頁載入時的內容為基準覆寫（不做合併）；下次進入設定頁重新讀檔 |

## 9. 測試

| 測試檔 | 內容 |
|---|---|
| `tests/test_app_settings.py` | 標籤擷取（含群組、無註解、空行中斷、多行註解）；型別推斷與 `timeout`、`log.level` 特例；無變更時 `render` 與原檔逐位元組相同；改值後註解與縮排保留；`\r\n` 保留；引號規則（雙、單、無引號需自動加引號）；型別不符、超出範圍、未知 key 丟例外；寫檔失敗原檔不動；`changes()` 分類；讀取 repo 內現有 `ws_tool.yaml` |
| `tests/test_plugin_loader.py` | 從 repo `plugins/` 載入成功；資料夾不存在、import 失敗、API 版本不符回傳 `None` |
| `tests/test_settings_page.py` | 標籤與值正確顯示；修改後 dirty、按鈕啟用；儲存寫檔並發出 `saved`；通知 level 依變更分類；還原；外掛為 `None` 的佔位畫面 |
| `tests/test_main_window.py`（補充） | F11 切換、側欄與快捷鍵停用／恢復、設定頁 Esc 返回、未存檔三選一詢問、`apply_app_settings` 更新標題／關於／圖示／逾時、主題切換傳遞色票 |
| `tests/test_entry_point.py`（補充） | `settings_path` 指向實際的 `ws_tool.yaml` |

**實機驗證**：執行 `build.bat` 後啟動 `dist\WebService-Tool.exe`，確認 F11 載入外掛、儲存、熱重載、需重啟提示；移除 `dist\plugins\` 後 F11 顯示「未安裝」。
