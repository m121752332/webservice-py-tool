# -*- coding: utf-8 -*-
# @Time : 2021/09/29 10:16
# @Author : Tiger
# @File : main.py
# @Software: vscode
import random
import sys
import traceback

from loguru import logger
import suds
from suds.client import Client
from lxml import etree
import xml.dom.minidom
import wx
import wx.adv
from wx.lib.wordwrap import wordwrap

import src.ui.main.main_frame as frame
from src.config.ConnectionManager import ConnectionManager
from src.config.web_service_config import WebServiceConfig
from src.utils import pathutil, yaml_values
from src.utils import fileutils
from src.utils import uuidutil
from src.utils.balloontip import show_balloon_tip
import wx.lib.agw.infobar as IB
import wx.lib.agw.toasterbox as TB


def show_message(message):
    """統一顯示對話框

    根據傳入對話框內容顯示對話框

    Args:
        message (str): 對話框內容
    """
    wx.MessageDialog(None, message, u"操作提醒", wx.OK).ShowModal()


def show_warning(message):
    dialog = wx.MessageDialog(None, message, u"警告", wx.OK | wx.ICON_WARNING)
    return dialog


class Main(frame.MainFrame):
    # 類變數 json_data
    json_data = ""

    def __init__(self, parent):
        frame.MainFrame.__init__(self, parent)
        self.TotalMsgs = 1
        self._infoBar = IB.InfoBar(self)

        # logger
        self.app_config = WebServiceConfig()

        logger.add(self.app_config.get_app_log_path() + '/run.log',
                   retention=self.app_config.get_app_log_retention())

        self.panel = wx.Panel(self, wx.ID_ANY)
        self.icon = wx.Icon(pathutil.resource_path(self.app_config.get_app_img_path()),
                            wx.BITMAP_TYPE_ICO)
        self.SetIcon(self.icon)
        self.Centre()

        # 執行狀態，初始化給False
        self.open_state = False
        # 配置url給予選擇item
        self.url_item = 0
        # 目前連線器物件
        self.connect = None
        # 若配置名稱空白則預設
        self.m_text_ctrl_name_placeholder = u"請輸入配置名稱，最多100字元"
        print(self.app_config.get_app_connection_path())
        print(type(self.app_config.get_app_connection_path()))
        app_connection_path = self.app_config.get_app_connection_path()
        app_connection_profile = self.app_config.get_app_connection_profile()
        self.connect_profile = "{}\\{}".format(str(app_connection_path), str(app_connection_profile))

        try:
            # 從檔案中讀取資料
            self.load_json_data()

            # 連線包建立完成
            if len(Main.json_data) == 0:
                return

            urls = self.get_connetions_urls(Main.json_data)
            if len(urls) == 0:
                self.add_new_data()
                urls = self.get_connetions_urls(Main.json_data)
                self.url_item = 0
                show_message("請填寫配置名稱再輸入WebService網址，後綴請用?WSDL當結尾")

            # 設定下拉物件清單
            self.m_combo_urls.SetItems(urls)  # 設定後會進入 OnComboBoxUrlsText
            # 設定選擇0
            self.m_combo_urls.SetSelection(self.url_item)
            # 從字典中提取 connections 部分
            connections_dict = Main.json_data.get("connections", {})
            self.connection_manager = ConnectionManager(connections_dict)
            self.url = self.m_combo_urls.GetItems()[self.m_combo_urls.GetSelection()]
            self.switch_connect_by_url()

            # 配置名設定最多輸入100字元
            self.m_text_ctrl_name.SetValue(self.connect.get_name())
        except Exception as err:
            logger.error("讀取失敗: {}", err)
            show_message("請填寫配置名稱再輸入WebService網址，後綴請用?WSDL當結尾")

        self.open_state = True

        # 做點限制
        self.m_text_ctrl_name.SetMaxLength(100)
        # show_balloon_tip(self.m_text_ctrl_name,"配置說明","請輸入配置名稱，最多100字元，\n這裡可以輸入各種配置名稱隨時都能修改內容。")

        # 若無配置名，顯示欄位解析
        if self.m_text_ctrl_name.GetValue() == "":
            self.m_text_ctrl_name.SetValue(self.m_text_ctrl_name_placeholder)
            self.m_text_ctrl_name.SetForegroundColour(wx.Colour(128, 128, 128))

        # wx.CallLater(2000, self.show_info)

    def send_notify(self, event):
        # 滑鼠座標を取得
        (x, y) = wx.GetMousePosition()

        # ToasterBox
        toaster = TB.ToasterBox(self, tbstyle=TB.TB_SIMPLE)
        toaster.SetTitle("溫馨提示")
        toaster.SetPopupBackgroundColour((255, 200, 50, 255))
        # 配置彈出時間
        toaster.SetPopupPauseTime(3000)
        toaster.SetPopupScrollSpeed(6)
        # 配置彈出文字
        toaster.SetPopupText(event)
        # 配置彈出窗體大小
        toaster.SetPopupSize(wx.Size(400, 100))
        # 配置彈出位置
        toaster.SetPopupPosition(wx.Position(x - 100, y + 10))
        # Parameters: 0: 左上角 1: 右上角 2: 左下角 3: 右下角
        # toaster.SetPopupPositionByInt(3)
        # 設定彈出字體
        toaster.SetPopupTextFont(
            wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, False, '微軟正黑體'))
        # toaster.SetUseFocus(True)
        toaster.Play()

    def send_msg(self, title, message):
        wx_icon = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION,
                                           wx.ART_OTHER, (48, 48))
        (x, y) = wx.GetMousePosition()
        tb = TB.ToasterBox(wx.GetApp().GetTopWindow(),
                           TB.TB_COMPLEX,
                           TB.TB_DEFAULT_STYLE,
                           TB.TB_ONTIME)
        tb.SetPopupSize((400, 80))
        tb.SetPopupPauseTime(3000)
        tb.SetPopupScrollSpeed(8)
        # tb.SetPopupPositionByInt(3)
        # 配置彈出位置
        tb.SetPopupPosition(wx.Position(x - 100, y + 10))

        # wx controls
        tb_panel = tb.GetToasterBoxWindow()
        panel = wx.Panel(tb_panel, -1)
        # panel.SetBackgroundColour(wx.WHITE)
        panel.SetBackgroundColour((255, 200, 50, 255))
        wx_icon = wx.StaticBitmap(panel, -1, wx_icon)
        title = wx.StaticText(panel, -1, title)
        message = wx.StaticText(panel, -1, message)

        # wx layout controls
        ver_sizer = wx.BoxSizer(wx.VERTICAL)
        ver_sizer.Add(title, 0, wx.ALL, 4)
        ver_sizer.Add(message, 0, wx.ALL, 4)

        hor_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # hor_sizer.Add(wx_icon, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 4)
        hor_sizer.Add(wx_icon, 0, wx.ALL, 4)
        hor_sizer.Add(ver_sizer, 1, wx.EXPAND)
        hor_sizer.Layout()
        panel.SetSizer(hor_sizer)

        tb.AddPanel(panel)
        tb.Play()

    def load_json_data(self):
        # 從檔案中讀取資料
        Main.json_data = fileutils.read_json_from_file(
            pathutil.resource_abspath(self.connect_profile)
        )

    def add_new_data(self):
        logger.trace('add_new_data')

        # 下拉選單共多少個
        url_items_count = self.m_combo_urls.GetCount()
        self.url_item = self.m_combo_urls.GetSelection()
        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)

        web_new_url = u"請輸入網站"
        connections_dict = Main.json_data.get("connections", {})

        # 新的配置字典
        new_config = {
            "uuid": str(uuidutil.get_uuid()),
            "name": u"",
            "url": web_new_url,
            "method": []
        }

        # 将新的配置字典添加到 connections 列表中
        connections_dict.append(new_config)

        Main.json_data = {"connections": connections_dict}

        self.connection_manager = ConnectionManager(connections_dict)
        self.url = web_new_url
        self.connect = self.connection_manager.get_connection_by_url(self.url)
        # logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())
        # self.switch_connect_by_url()

        # Main.json_data 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

        # 連線包建立完成
        if len(Main.json_data) == 0:
            return

        url_selection = url_items_count
        urls = self.get_connetions_urls(Main.json_data)

        # 設定下拉物件清單
        self.m_combo_urls.SetItems(urls)
        # 設定選擇0
        self.m_combo_urls.SetSelection(url_selection)
        self.url = self.m_combo_urls.GetItems()[url_selection]

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        # logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())

    def file_save_reload(self):
        # 從檔案中讀取資料
        self.load_json_data()

        # 連線包建立完成
        if len(Main.json_data) == 0:
            return

        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)

    def get_connetions_urls(self, data):
        """獲取WebService方法

        Args:
            client (suds.client): 客戶端對象
        """
        urls = []
        for data in data.values():
            for service in data:
                urls.append(service['url'])
        return urls

    def ws_get_methods(self, client):
        """獲取WebService方法

        Args:
            client (suds.client): 客戶端對象
        """
        return [method for method in sorted(client.wsdl.services[0].ports[0].methods)]

    """
    獲取WebService方法對應的參數

    Args:
        client (suds.client): 客戶端對象
        method_str (str): 方法名稱
    """

    def get_method_args(self, client, method_str):
        method = client.wsdl.services[0].ports[0].methods[method_str]
        input_params = method.binding.input
        return input_params.param_defs(method)

    def update_service_name_by_url(self, url, name):
        # 無詢問直接更新配置名方法
        for data in Main.json_data.values():
            for service in data:
                if service['url'] == url:
                    service['name'] = name
        # logger.info(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

    def update_service_methods_by_uuid(self, uuid, new_url, new_methods):
        logger.info("update_service_methods_by_uuid: %s" % uuid)
        logger.debug("new_url: {}", new_url)
        logger.debug("new_methods: {}", new_methods)
        # 無詢問直接更新服務方法
        for data in Main.json_data.values():
            for service in data:
                if service['uuid'] == uuid:
                    service['url'] = new_url
                    service['method'] = new_methods
        logger.debug(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

    def update_service_methods_by_name(self, name, url, new_methods):
        # 無詢問直接更新服務方法
        for data in Main.json_data.values():
            for service in data:
                if service['name'] == name:
                    service['method'] = new_methods
                if service['url'] == "":
                    service['uuid'] = str(uuidutil.get_uuid())
                    service['url'] = url
        self.url = url
        logger.info(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

    '''
    更新WebService服務方法
    '''

    def update_service_methods_by_url(self, url, new_methods):
        logger.info("update_service_methods_by_url: %s" % url)
        logger.info(" {}", new_methods)
        # 無詢問直接更新服務方法
        for data in Main.json_data.values():
            for service in data:
                if service['url'] == url:
                    service['method'] = new_methods
        logger.info(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

    def update_service_url_by_uuid(self, new_url, uuid):
        logger.debug("update_service_url_by_uuid: %s" % uuid)
        logger.debug("> new_url: {}", new_url)
        if uuid == "" or new_url == "":
            return
        # 無詢問直接更新服務方法
        for data in Main.json_data.values():
            for service in data:
                if service['uuid'] == uuid:
                    service['url'] = new_url
        self.url = new_url
        logger.debug(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file()
        self.file_save_reload()

    '''
    將DICT(json_data)資料寫入 connections.profile
    '''

    def write_to_file(self):
        logger.trace("write_to_file")
        # 寫入檔案內
        fileutils.write_json_to_file(
            Main.json_data,
            pathutil.resource_abspath(self.connect_profile)
        )

    # 執行讀取服務的事件
    def OnClickEventLoad(self, event):
        logger.info("OnClickEventLoad: %s" % event.GetString())

        if len(self.m_combo_urls.GetValue()) == 0:
            # show_message(u"請填寫WSDL地址")
            # self.show_notify(u"請填寫WSDL地址")
            self.send_msg("溫馨提示", u"請填寫WSDL地址")
            return
        try:
            # 禁用按鈕
            self.form_button_disable()

            self.url = self.m_combo_urls.GetValue()
            logger.info("Use:{} get methods", self.url)

            client = suds.client.Client(self.m_combo_urls.GetValue(), timeout=3)
            # methods list loading
            methods = self.ws_get_methods(client)

            if self.connect.get_uuid() == "":
                # 應該不會走這段
                self.update_service_methods_by_name(
                    self.connect.get_name(),
                    self.m_combo_urls.GetValue(),
                    methods
                )
            else:
                self.update_service_methods_by_uuid(
                    self.connect.get_uuid(),
                    self.url,
                    methods
                )

            self.switch_connect_by_url()

            self.m_combo_methods.SetItems(methods)
            self.m_combo_methods.SetSelection(0)

            # 設定請求內容增加XML起始資訊
            self.m_text_ctrl_params.SetValue("<?xml version=\"1.0\" encoding=\"utf-8\"?>")

        except Exception as err:

            logger.error("讀取發生異常: {}", err)
            err_type = err.__class__.__name__  # 取得錯誤的class 名稱
            info = err.args[0]  # 取得詳細內容
            detains = traceback.format_exc()  # 取得完整的tracestack
            n1, n2, n3 = sys.exc_info()  # 取得Call Stack
            lastCallStack = traceback.extract_tb(n3)[-1]  # 取得Call Stack 最近一筆的內容
            fn = lastCallStack[0]  # 取得發生事件的檔名
            lineNum = lastCallStack[1]  # 取得發生事件的行數
            funcName = lastCallStack[2]  # 取得發生事件的函數名稱
            errMesg = f"FileName: {fn}, lineNum: {lineNum}, Fun: {funcName}, reason: {info}, trace:\n {traceback.format_exc()}"
            logger.error("檢視: {}", errMesg)
            show_message("讀取發生異常: " + str(err))
        finally:
            # 啟用按鈕
            self.form_button_enable()

            # 設定下拉物件清單
            urls = self.get_connetions_urls(Main.json_data)
            self.m_combo_urls.SetItems(urls)
            self.m_combo_urls.SetSelection(self.url_item)

    def form_button_enable(self):
        self.m_btn_load.Enable()
        self.m_btn_start.Enable()
        self.m_btn_clear.Enable()
        self.m_btn_append_connect.Enable()
        self.m_btn_delete_connect.Enable()

    def form_button_disable(self):
        self.m_btn_load.Disable()
        self.m_btn_start.Disable()
        self.m_btn_clear.Disable()
        self.m_btn_append_connect.Disable()
        self.m_btn_delete_connect.Disable()

    # 處理請求執行處理的事件
    def OnClickEventStart(self, event):

        url = self.m_combo_urls.GetValue()
        if len(url) == 0:
            show_message(u"請填寫WSDL地址")
            return

        select_methods_index = self.m_combo_methods.GetSelection()
        if select_methods_index < 0:
            show_message(u"請選擇請求服務方法")
            return
        method = self.m_combo_methods.GetItems()[select_methods_index]
        self.m_text_ctrl_result.Clear()
        try:
            # 禁用按鈕
            self.form_button_disable()
            data = self.m_text_ctrl_params.GetValue().replace('\n',
                                                              '').split('#~#')
            client = suds.client.Client(url)
            args = self.get_method_args(client, method)
            if len(args) != len(data):
                show_message(u"該服務方法需要" + str(len(args)) + "個參數，而你只輸入了" +
                             str(len(data)) + "個，多參數請使用#~#隔開，並保證參數順序")
                return
            argv = {}
            for index in range(len(args)):
                argv[args[index][0]] = data[index]
            result = getattr(client.service, method)(**argv)
            logger.info("\n網址: {}\n服務：{}\n參數：{}\n回應結果: {}", url, method, argv, result)
            encoding = xml.dom.minidom.parseString(result).encoding
            if not encoding:
                encoding = 'utf-8'
            str_xml = etree.fromstring(
                bytes(bytearray(result, encoding=encoding)))
            pretty_xml = etree.tostring(str_xml,
                                        xml_declaration=True,
                                        encoding=encoding,
                                        pretty_print=True)
            self.m_text_ctrl_result.SetValue(pretty_xml.decode(encoding))
        except Exception as err:
            logger.error("發生異常: {}", err)
            show_message("請求服務後發生異常: " + str(err))
        finally:
            # 啟用按鈕
            self.form_button_enable()

    def OnTextCtrlNameText(self, event):
        logger.info('OnTextCtrlNameText: %s' % event.GetString())

        connections_dict = Main.json_data.get("connections", {})
        if len(connections_dict) == 0:
            return
        if self.open_state:
            self.update_service_name_by_url(
                self.m_combo_urls.GetValue(), event.GetString()
            )

    def OnTextCtrlNameTextEnter(self, event):
        logger.info('OnTextCtrlNameTextEnter: %s' % event.GetString())

    def OnTextCtrlNameMaxLen(self, event):
        logger.info('OnTextCtrlNameMaxLen: %s' % event.GetString())
        dlg = show_warning(u"輸入太長了")
        if dlg.ShowModal() == wx.ID_OK:
            self.m_text_ctrl_name.SetValue(self.connect.get_name())

    def OnTextCtrlNameSetFocus(self, event):
        if self.m_text_ctrl_name.GetValue() == self.m_text_ctrl_name_placeholder:
            self.m_text_ctrl_name.SetValue("")
            self.m_text_ctrl_name.SetForegroundColour(wx.NullColour)
        event.Skip()

    def OnTextCtrlNameKillFocus(self, event):
        if self.m_text_ctrl_name.GetValue() == "":
            self.m_text_ctrl_name.SetValue(self.m_text_ctrl_name_placeholder)
            self.m_text_ctrl_name.SetForegroundColour(wx.Colour(128, 128, 128))
        event.Skip()

    """
    若網址選擇，將選擇值改為選擇的connect
    Args:
        event (wx.CommandEvent): The event object containing information about the event.
    Returns:
        None
    """

    def OnComboBoxUrlsSelect(self, event):
        logger.info('OnComboBoxUrlsSelect: %s' % event.GetString())
        self.url_item = self.m_combo_urls.GetSelection()

        self.url = self.m_combo_urls.GetItems()[self.url_item]
        logger.info(" {}", self.m_combo_urls.GetValue())
        logger.info("url: {}", self.url)

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())

        # 配置名設定最多輸入100字元
        self.m_text_ctrl_name.SetValue(self.connect.get_name())

    """
    若網址選擇後直接貼上值
    Args:
        event (wx.CommandEvent): The event object containing information about the event.
    Returns:
        None
    """

    def OnComboBoxUrlsText(self, event):
        logger.info('OnComboBoxUrlsText: %s' % event.GetString())
        logger.info(' > self.open_state: %s' % self.open_state)
        logger.info(' > self.m_combo_urls.GetSelection(): %s' % self.m_combo_urls.GetSelection())

        if self.open_state and self.m_combo_urls.GetSelection() > 0:
            self.url_item = self.m_combo_urls.GetSelection()
            logger.info('url_select_item: %s' % self.url_item)
            self.url = self.m_combo_urls.GetItems()[self.url_item]
            logger.info('url: %s' % self.url)

            self.connect = self.connection_manager.get_connection_by_url(self.url)
            # logger.info("connect: {}", self.connect)
            logger.info("connect(uuid) -{}", self.connect.get_uuid())
            logger.info("connect(name) -{}", self.connect.get_name())
            logger.info("connect(url)  -{}", self.connect.get_url())

            if self.open_state:
                self.update_service_url_by_uuid(
                    event.GetString(),
                    self.connect.get_uuid()
                )

    def OnComboBoxUrlsEnter(self, event):
        logger.info('OnComboBoxUrlsEnter: %s' % event.GetString())

    # 處理服務方法下拉框選擇事件
    def OnComboBoxMethodSelect(self, event):
        logger.info('OnComboBoxMethodSelect: %s' % event.GetString())
        item = event.GetSelection()

    """
    Handle the event when the text in the ComboBox changes.

    Args:
        event: The event object containing information about the text change.

    Returns:
        None
    """

    def OnComboBoxMethodText(self, event):
        logger.info('OnComboBoxMethodText: %s' % event.GetString())

        item = event.GetSelection()

    """
    Handle the event when the menu click event for exiting is triggered.

    Args:
        self: The object instance.
        event: The event object.

    Returns:
        None
    """

    def OnClickEventAdd(self, event):
        logger.info('OnClickEventAdd: %s' % event.GetString())

        # 下拉選單共多少個
        url_items_count = self.m_combo_urls.GetCount()
        self.url_item = self.m_combo_urls.GetSelection()
        logger.info("url count: {} url_selection: {} url_item_value: {}", url_items_count, self.url_item,
                    self.m_combo_urls.GetValue())
        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)

        web_new_url = u"請輸入網站"
        connections_dict = Main.json_data.get("connections", {})
        for connection in connections_dict:
            if connection["url"] == web_new_url:
                web_new_url = u"請輸入網站" + str(random.sample(range(1, 1001), 1))

        # 新的配置字典
        new_config = {
            "uuid": str(uuidutil.get_uuid()),
            "name": u"",
            "url": web_new_url,
            "method": []
        }

        # 将新的配置字典添加到 connections 列表中
        connections_dict.append(new_config)
        Main.json_data = {"connections": connections_dict}
        # Main.json_data 更新完高速寫入connections.profile
        self.write_to_file()
        self.url_item = self.m_combo_urls.GetCount()
        self.file_save_reload()

        # 連線包建立完成
        if len(Main.json_data) == 0:
            return

        url_selection = url_items_count
        urls = self.get_connetions_urls(Main.json_data)

        # 設定下拉物件清單
        self.m_combo_urls.SetItems(urls)
        # 設定選擇0
        self.m_combo_urls.SetSelection(url_selection)
        self.url = self.m_combo_urls.GetItems()[url_selection]

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        # logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())
        # 配置名設定最多輸入100字元
        self.m_text_ctrl_name.SetValue(self.connect.get_name())
        self.OnTextCtrlNameKillFocus(event)

    def OnClickEventDel(self, event):
        logger.info("OnClickEventDel")

        # 連線包建立完成
        if len(Main.json_data) == 0:
            return
        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)
        self.url = self.m_combo_urls.GetValue()
        self.connect = self.connection_manager.get_connection_by_url(self.url)

        uuid_to_delete = self.connect.get_uuid()
        for connection in connections_dict:
            if connection["uuid"] == uuid_to_delete:
                connections_dict.remove(connection)
        Main.json_data = {"connections": connections_dict}
        self.write_to_file()
        self.file_save_reload()

        # 已經無連線紀錄
        if len(connections_dict) == 0:
            self.m_text_ctrl_name.Clear()  # 配置名稱欄位
            self.m_combo_urls.Clear()
            self.m_combo_methods.Clear()  # 服務方法區域
            self.m_text_ctrl_params.SetValue("")  # 提交參數區域
            self.m_text_ctrl_result.SetValue("")  # 回應結果區域
            return

        # 重新讀取url選單內容
        urls = self.get_connetions_urls(Main.json_data)
        # 設定下拉選單內容
        self.m_combo_urls.SetItems(urls)
        # 設定選擇第1筆 (index=0)
        self.url_item = 0
        self.m_combo_urls.SetSelection(self.url_item)
        # 如果還有連線資料 就跳回第一筆[index=0]
        self.url = self.m_combo_urls.GetItems()[self.url_item]
        # url切換connect物件後顯示名稱
        self.switch_connect_by_url()

    """
    A method to switch the UUID based on the URL.
    透過 self.url 取出connect物件資料集
    """

    def switch_connect_by_url(self):
        logger.info("switch_uuid_by_url")
        # 取得 連線dict 資料放入管理器
        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)
        # 透過sel.url 拿到網址
        self.url = self.m_combo_urls.GetValue()
        # 用網址找到連線物件(connect)
        self.connect = self.connection_manager.get_connection_by_url(self.url)
        logger.info("connect: {}", str(self.connect))
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())
        self.m_text_ctrl_name.SetValue(self.connect.get_name())

    """
    Clears the values of various fields in the UI when the clear button is clicked.

    :param event: The event object that triggered the click event.
    :return: None
    """

    # 處理清空按鈕的事件
    def OnClickEventClear(self, event):
        # self.m_text_ctrl_name.SetValue("")  # 配置名稱欄位
        # self.m_combo_urls.SetValue("")      # 網址欄位
        self.m_combo_methods.Clear()  # 服務方法區域
        self.m_text_ctrl_params.SetValue("")  # 提交參數區域
        self.m_text_ctrl_result.SetValue("")  # 回應結果區域

    '''
        處理退出選單事件
        '''

    def OnMenuClickEventAbout(self, event):
        logger.info("OnMenuClickEventAbout")
        # 開啟About窗口
        info = wx.adv.AboutDialogInfo()
        info.SetName(self.app_config.get_app_name())
        info.SetVersion(self.app_config.get_app_version())
        info.SetDescription(wordwrap(
            '''
            這是一款針對WebService設計的開源工具，簡單好用配置靈活度高，有興趣研究請上GitHub我的專案，連結如下
            ''',
            350, wx.ClientDC(self.panel)))
        info.SetCopyright(self.app_config.get_app_copyright())
        info.SetWebSite("https://github.com/m121752332/webservice-py-tool")
        info.AddDeveloper("原創: Tiger Tseng")
        info.AddTranslator("原創: Tiger Tseng")
        info.AddArtist("原創: Tiger Tseng")
        info.SetLicence(
            wordwrap("Completely and totally open source!", 500,
                     wx.ClientDC(self.panel)))
        # Show the wx.AboutBox
        wx.adv.AboutBox(info)

    '''
    處理退出選單事件
    '''

    def OnMenuClickEventExit(self, event):
        app_exit = wx.MessageDialog(None, u"確定退出嗎？", u"退出提醒", wx.YES_NO | wx.ICON_QUESTION)
        if app_exit.ShowModal() == wx.ID_YES:
            self.Destroy()
        app_exit.Destroy()
