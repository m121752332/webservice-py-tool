## 專案簡介

WebService服務部署到了服務器，但是只能本地訪問，下載soapui有點太大了，找其他的測試工具又沒有合適的，就自己寫了個比較簡單的小工具！

* Python 3.8.10
* WxPython==4.2.1
* suds_jurko==0.6
* lxml==5.1.0
* setuptools==57.5.0

## 開發說明
1. 安裝依賴：`$ pip install -r requirements.txt`
2. 使用vscode開發，打開src/ws-tool.py文件，點擊運行→啟動調試，或者F5啟動程序
3. 其他工具開發，執行`$ python ws-tool.py`運行程序
4. 打包exe時候直接運行bin/package.bat即可，執行完會生成dist目錄，里面是打包好的運行文件
5. fbp下的WxPython-UI.fbp文件是頁面設計，需要用[wxFormBuilder](https://github.com/wxFormBuilder/wxFormBuilder)打開
6. 暫時不支持mac環境打包，如果有想法也可以自己去找到合適的配套方案

## 打包方式
根目錄下指令  
#### 打成一包
`pyinstaller --add-data="src/img:img" --version-file src/config/file_version_info.txt -D -w -n WebService-Tool -i src/img/favicon.ico src/ws_tool.py`  
#### 打成一個檔案
`pyinstaller --add-data="src/img:img" --version-file src/config/file_version_info.txt -F -w -n WebService-Tool -i src/img/favicon.ico src/ws_tool.py`  

## 版本產生
切到 src/config 底下輸入  
`python grab_version.py C:\Windows\System32\WWAHost.exe`  
系統自動產生 file_version_info.txt 用於包裝到pyinstaller的版本檔案使用

## 內置功能

1.  測試WebService接口（支持多參數，不支持添加請求頭）

## 下載體驗

- 下載檔案：[WebService.exe](<https://github.com/m121752332/webservice-py-tool/releases>)
- 下載畫面設計器: [wxFormBuilder](<https://github.com/wxFormBuilder/wxFormBuilder/releases/tag/v4.1.0>)


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




## 畫面設計器預覽

<table>
    <tr>
        <td><img src="docs/webservice_tool_001.png"/></td>
    </tr>
</table>