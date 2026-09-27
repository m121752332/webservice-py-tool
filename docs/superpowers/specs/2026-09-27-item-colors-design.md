# 專案目錄與連線顏色標記設計

- 日期：2026-09-27
- 分支：`feat/item-colors`

## 1. 目標與範圍

左側專案目錄可以替目錄與連線各自標記顏色，方便一眼區分（例如正式區標紅、測試區標綠）。顏色從 8 種預選色中挑選，淺色與深色主題各有一組易辨識的色碼，透過右鍵選單設定。

**範圍內**

- 目錄：資料夾圖示染成指定顏色，目錄名稱維持一般文字色
- 連線：只有連線名稱（粗體那一行）改成指定顏色，下方網址維持灰色
- 右鍵選單「顏色 ▸」：預設 + 8 色，目前選用的項目打勾
- 顏色存進 `connections.profile`，重開程式後保留
- 切換淺色／深色主題時同步換成對應色碼

**不在範圍內**

- 連線繼承目錄顏色（未設色的連線一律顯示一般文字色）
- 自訂任意色碼（色盤／色碼輸入）
- 多選批次設色
- 顏色影響工作區、請求紀錄等其他畫面

**相容性要求**

- 舊版 `connections.profile`（沒有 `color` 欄位）可直接讀取，所有項目視為預設色
- 未設色的項目存檔時不寫 `color` 欄位，檔案內容與現行格式完全相同
- `color` 欄位值不合法（非字串、未知代號）時視為預設色，**不**當作檔案損毀處理
- 舊版程式可讀取新格式（忽略 `color`），但舊版存檔時會丟失顏色設定

## 2. 色票（`src/ui/theme.py`）

8 色依色相排列。淺色主題取較深色階、深色主題取較亮色階，所有色碼對清單背景（`bg`）與選取列背景（`surface_hover`）的對比度皆 ≥ 4.5:1（WCAG AA 一般文字）。

| 代號 | 名稱 | 淺色主題 | 對比 bg / 選取 | 深色主題 | 對比 bg / 選取 |
|---|---|---|---|---|---|
| `red` | 紅 | `#C81E1E` | 5.2 / 4.8 | `#FC8181` | 6.7 / 4.8 |
| `orange` | 橘 | `#B23C0A` | 5.3 / 4.9 | `#FB923C` | 7.2 / 5.2 |
| `yellow` | 黃 | `#8A5A00` | 5.3 / 4.9 | `#FACC15` | 10.6 / 7.7 |
| `green` | 綠 | `#15703A` | 5.5 / 5.1 | `#4ADE80` | 9.4 / 6.7 |
| `teal` | 青 | `#0D6C65` | 5.6 / 5.2 | `#2DD4BF` | 8.8 / 6.3 |
| `blue` | 藍 | `#1D4ED8` | 6.0 / 5.6 | `#6AADFB` | 7.0 / 5.0 |
| `purple` | 紫 | `#7E22CE` | 6.3 / 5.8 | `#C99CFD` | 7.5 / 5.4 |
| `pink` | 粉紅 | `#BE185D` | 5.4 / 5.0 | `#F689C2` | 7.2 / 5.2 |

結構：

```python
@dataclass(frozen=True)
class TagColor:
    key: str    # 存檔用代號，例如 "red"
    label: str  # 選單顯示名稱，例如 "紅"
    light: str  # 淺色主題色碼
    dark: str   # 深色主題色碼

TAG_COLORS: tuple[TagColor, ...] = (...)  # 依上表順序


def tag_color(key: str | None, palette: ThemePalette) -> str | None:
    """代號轉成目前主題的色碼；None 或未知代號回傳 None（使用預設色）"""
```

`ThemePalette` 不新增欄位，由 `palette.name`（`"light"`／`"dark"`）決定取 `light` 或 `dark`。

## 3. 資料層（`src/core/connection_store.py`）

### 3.1 資料結構

```python
@dataclass
class Folder:
    uuid: str
    name: str = ""
    expanded: bool = True
    color: str | None = None  # 顏色代號，None 為預設色


@dataclass
class Connection:
    uuid: str
    name: str = ""
    url: str = ""
    methods: list[str] = field(default_factory=list)
    folder: str | None = None
    color: str | None = None  # 顏色代號，None 為預設色
```

核心層不驗證代號是否屬於 8 色之一（色票屬於 UI），只保證型別：

```python
def _parse_color(value) -> str | None:
    """color 欄位：缺少、空字串或非字串一律視為預設色（不視為檔案損毀）"""
```

### 3.2 新增介面

```python
def set_color(self, uuid: str, color: str | None) -> None: ...         # 連線
def set_folder_color(self, uuid: str, color: str | None) -> None: ...  # 目錄
```

兩者與其他修改一樣立即寫回檔案；uuid 不存在時丟 `KeyError`。

### 3.3 存檔格式

`color` 為 `None` 時不寫入該鍵：

```json
{
    "folders": [
        {"uuid": "…", "name": "科林儀器", "expanded": true, "color": "blue"}
    ],
    "connections": [
        {"uuid": "…", "name": "TIPTOP_TOPPROD", "url": "…", "method": [], "folder": "…", "color": "red"},
        {"uuid": "…", "name": "TIPTOP_TOPTEST", "url": "…", "method": [], "folder": "…"}
    ]
}
```

刪除目錄時目錄的顏色隨之消失；移到最外層的連線保留各自的顏色。移動、改名不影響顏色。

## 4. 圖示染色（`src/ui/icons.py`）

```python
def tinted_icon(icon: QIcon, color: str) -> QIcon:
    """保留原圖示的明暗層次與透明度，把色相換成 color"""
```

作法：對 `icon.availableSizes()` 的每個尺寸（沒有時用 `FOLDER_ICON_SIZE`）取 pixmap，轉灰階後以 `CompositionMode_Multiply` 疊上 `color`，再以原圖的 alpha（`CompositionMode_DestinationIn`）裁切，保留原本的輪廓與陰影。未設色的目錄維持原本的 `SP_DirIcon`，外觀完全不變。

## 5. 連線清單（`src/ui/connection_list.py`）

### 5.1 狀態與介面

- 建構子新增 `palette: ThemePalette` 參數（預設 `LIGHT`，方便既有測試）
- `set_palette(palette)`：記下新主題並重新套用所有項目的顏色（不重建樹）
- `set_tree()` 從 `Folder.color`／`Connection.color` 取得顏色；`update_connection()` 也會更新顏色
- 項目上以 `_COLOR_ROLE` 保存代號，換主題時據此重新上色
- 新增訊號：

```python
folderColorChanged = Signal(str, object)      # 目錄 uuid, 顏色代號或 None
connectionColorChanged = Signal(str, object)  # 連線 uuid, 顏色代號或 None
```

### 5.2 套用顏色

- 目錄：`tag_color()` 有值時 `item.setIcon(0, tinted_icon(系統資料夾圖示, 色碼))`，否則還原為系統資料夾圖示
- 連線：`ConnectionItemWidget.set_title_color(色碼 | None)`，以名稱標籤自身的 stylesheet 設定 `color`；`None` 時清除 stylesheet，回到全域 QSS 的一般文字色

### 5.3 右鍵選單

目錄與連線的右鍵選單在「刪除」前新增子選單「顏色」：

```
顏色 ▸  ✓ 預設
          ■ 紅
          ■ 橘
          …（共 8 色）
```

- 每個顏色項目帶一個以目前主題色碼繪製的方形色塊圖示
- 項目為 checkable，目前的顏色（含「預設」）打勾，同一時間只有一個打勾
- 選取後發出對應訊號；選到目前已套用的顏色不發訊號

## 6. 主視窗（`src/ui/main_window.py`）

- 建立 `ConnectionList(self._theme.palette)`
- `folderColorChanged` → `store.set_folder_color()` → 更新清單上該目錄的顏色
- `connectionColorChanged` → `store.set_color()` → 更新清單上該連線的顏色
- `_on_theme_changed` 呼叫 `connection_list.set_palette(palette)`

更新畫面時只更新該項目，不重建整棵樹，避免影響選取與捲動位置。

## 7. 錯誤處理

- 設色時項目已不存在（理論上不會發生）：`KeyError` 由既有流程處理，與改名一致
- 讀檔遇到不合法的 `color`：視為預設色，並在下次存檔時自然移除
- 染色時圖示沒有可用尺寸：以 `FOLDER_ICON_SIZE` 取 pixmap

## 8. 測試

- `tests/test_connection_store.py`
  - 預設無顏色；`set_color`、`set_folder_color` 寫回檔案並可重新讀取
  - 未設色項目存檔不含 `color` 鍵
  - 舊檔（無 `color`）可讀取；`color` 為數字、空字串時視為 `None` 且不觸發損毀備份
  - 刪除目錄後，移出的連線保留顏色
- `tests/test_theme.py`
  - `TAG_COLORS` 共 8 色、代號不重複
  - 每個色碼對 `bg`、`surface_hover` 的對比度 ≥ 4.5（淺色與深色主題皆驗證）
  - `tag_color()`：依主題取色碼、`None` 與未知代號回傳 `None`
- `tests/test_connection_list.py`
  - 右鍵選單有「顏色」子選單：預設 + 8 色，目前顏色打勾
  - 選色發出正確訊號；選目前顏色不發訊號
  - 連線名稱套用色碼；網址不受影響；清除後回到預設
  - 目錄圖示在設色後與預設圖示不同，清除後還原
  - `set_palette()` 後名稱改用新主題色碼
- `tests/test_main_window.py`
  - 從清單設色後寫進 `connections.profile`，重新建立視窗後顏色仍在
  - 切換主題後連線名稱改用深色主題色碼
- `tests/test_icons.py`（新增）
  - `tinted_icon()` 保留透明區域，不透明區域的色相接近指定顏色
