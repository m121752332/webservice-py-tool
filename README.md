# 專案簡介

WebService服務部署到了服務器，但是只能本地訪問，下載soapui有點太大了，找其他的測試工具又沒有合適的，就自己寫了個比較簡單的小工具！

* Python 3.14
* PySide6（Essentials）6.11
* suds 1.2
* lxml 6.1
* PyInstaller 6.22

## 開發說明
1. 安裝依賴：`$ uv sync`（或 `$ pip install -r requirements.txt`，此檔由 `uv export --format requirements-txt --no-hashes --no-emit-project --no-dev -o requirements.txt` 產生）
2. 啟動程式：`$ uv run python src/ws_tool.py`
3. 執行測試：`$ uv run pytest`
4. UI 檢測工具（類似瀏覽器的「檢查元素」）：`$ uv run python -m PyQtInspect --direct --file src/ws_tool.py`
5. 打包 exe：執行根目錄的 `build.bat`，完成後會在 `dist` 目錄產生 `WebService-Tool.exe`；散布時務必把 `app_data/`（含 `ws_tool.yaml`、`connections.profile`）資料夾與 exe 放在同一層目錄（工作目錄），如 `dist/app_data` 這樣的結構，否則程式找不到設定與連線資料
6. 暫時不支持mac環境打包，如果有想法也可以自己去找到合適的配套方案

## 介面
* 左側為連線清單（可搜尋、新增、刪除），可用目錄分組：拖曳或右鍵「移動到」把連線放進目錄、拖曳調整順序，右鍵「重新命名」修改目錄名稱
* 左下角「主題」可切換 跟隨系統 / 淺色 / 深色
* 快捷鍵：F1 新增連線、F2 刪除選取的連線或目錄、F3 讀取 WSDL、F5 執行、F6 清空、Ctrl+Shift+F 格式化請求、Esc 離開

## 版本產生
切到 src/config 底下輸入
`python grab_version.py C:\Windows\System32\WWAHost.exe`  
系統自動產生 file_version_info.txt 用於包裝到pyinstaller的版本檔案使用

## 內置功能

1.  測試WebService接口（支持多參數，不支持添加請求頭）

## 下載體驗

- 下載檔案：[WebService.exe](<https://github.com/m121752332/webservice-py-tool/releases>)


## 演示效果

<table>
    <tr>
        <td><label>收集請求資料內容</label></td>
    </tr>
    <tr>
        <td><img src="docs/webservice_tool_002.png"/></td>
    </tr>
    <tr>
        <td><label>執行請求參數取得回應資料</label></td>
    </tr>
    <tr>
        <td><img src="docs/webservice_tool_003.png"/></td>
    </tr>
</table>