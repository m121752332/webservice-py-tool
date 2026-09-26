# AGENTS.md

給所有 AI 編輯工具（Claude Code、Codex 等）共用的專案規則。

## 專案概覽

WebService 測試工具，PySide6 桌面 App，取代 wxPython 舊版。純 Windows 環境（打包與開發皆針對 win32/AMD64）。

- `src/ui/` — 介面元件（QWidget 子類、主題、特效）
- `src/core/` — 核心邏輯：連線資料存取（`connection_store.py`）、SOAP 呼叫（`soap_service.py`），不依賴 Qt
- `src/config/` — 設定檔讀寫、版本資訊產生
- `src/utils/` — 通用工具（路徑、檔案、UUID）
- `src/ws_tool.py` — 程式進入點
- `plugins/settings_editor/` — 設定編輯器外掛（pyqtgraph ParameterTree），另外打包；不可 import `src.*`，主程式不可直接依賴 pyqtgraph
- `tests/` — pytest 測試，檔名與 `src/` 對應模組一一對應
- `docs/superpowers/` — 大型功能的設計文件（specs）與實作計畫（plans），檔名格式 `YYYY-MM-DD-主題[-design].md`

## 開發流程

1. 安裝依賴：`uv sync`
2. 啟動程式：`uv run python src/ws_tool.py`
3. 執行測試：`uv run pytest`（或本機已知路徑 `.venv/Scripts/python -m pytest`）
4. 每次修改後，先跑過對應的測試再回報完成

## 程式風格

- 全部原始碼採用 UTF-8，檔案開頭一律 `# -*- coding: utf-8 -*-`
- **註解、docstring、UI 文字、commit 訊息一律使用繁體中文**；程式識別字（變數、函式、類別名稱）用英文
- 模組頂端用一段簡短 docstring 說明檔案職責（例：`"""主視窗：左側連線清單 + 右側工作區"""`）
- 核心邏輯（`src/core`）與 UI 分離：不要讓 `connection_store.py`、`soap_service.py` 依賴 PySide6
- 背景工作（讀取 WSDL、執行請求）一律透過 `src/ui/workers.py` 的 `run_in_background`，不可阻塞主執行緒
- 主題色票、樣式一律集中在 `src/ui/theme.py`（`LIGHT` / `DARK` palette + QSS Template），元件不要寫死顏色
- 新增按鈕等互動元件請延續既有慣例（例如 `variant` property 對應 QSS selector、`HoverLift` 懸浮效果）

## 測試

- 測試框架為 pytest，Qt 測試固定使用 `QT_QPA_PLATFORM=offscreen`（見 `tests/conftest.py`），不需額外設定
- 新增或修改 UI 行為時，同步更新/新增對應的 `tests/test_*.py`
- 修改前先確認既有測試綠燈，避免回歸

## Git 慣例

- commit 訊息、PR 說明一律繁體中文，動詞開頭、精簡描述變更內容（可參考 `git log` 既有寫法）
- **commit 訊息含中文時，請先用 Write 工具寫入暫存檔，再以 `git commit -F <檔案>` 提交**；不要用 bash heredoc/`printf` 直接組訊息，會產生亂碼（見專案記憶 `chinese-commit-message-encoding`）
- 大型功能異動前，先在 `docs/superpowers/specs/` 補設計文件、`docs/superpowers/plans/` 補實作計畫，再動工
- 不要主動 push；如需 push 請先詢問使用者

## 其他限制

- 不支援 macOS 打包（`pyproject.toml` 的 `required-environments` 已限定 `win32`/`AMD64`），不要加入跨平台相容程式碼
- `src/app_data/connections.profile`、`src/app_data/ws_tool.yaml` 的既有欄位格式需保持相容，異動請確認舊資料仍可讀取
- 版本資訊由 `src/config/grab_version.py` 產生 `file_version_info.txt`，供 PyInstaller 打包使用，不要手動編輯該檔案
