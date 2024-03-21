# -*- coding: utf-8 -*-
# @Time : 2021/09/29 10:16
# @Author : Tiger
# @File : main.py
# @Software: vscode

from loguru import logger
import suds
from suds.client import Client
from lxml import etree
import xml.dom.minidom
import wx
import src.ui.main.main_frame as frame
from src.config.ConnectionManager import ConnectionManager
from src.utils import pathutil
from src.utils import fileutils
import json


class Main(frame.MainFrame):
    # 類變數 json_data
    json_data = ""

    def __init__(self, parent):
        frame.MainFrame.__init__(self, parent)
        self.icon = wx.Icon(pathutil.resource_path('img/favicon.ico'),
                            wx.BITMAP_TYPE_ICO)
        self.SetIcon(self.icon)
        self.Centre()

        # 從檔案中讀取資料
        Main.json_data = fileutils.read_json_from_file(
            pathutil.resource_path('weblog\\connections.profile')
        )
        # logger.info(" {}", type(Main.json_data))
        # logger.info(" {}", Main.json_data)
        # 從字典中提取 connections 部分
        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)
        # for conn in self.connection_manager:
        #    logger.info(" {}", )
        # self.connection_manager.print_connections_recursively()

        # 連線包建立完成
        if len(Main.json_data) == 0:
            return
        urls = self.get_connetions_urls(Main.json_data)
        # TODO: m_combo_urls => m_combo_urls
        # 設定下拉物件清單
        self.m_combo_urls.SetItems(urls)
        # 設定選擇0
        self.m_combo_urls.SetSelection(0)
        self.url = self.m_combo_urls.GetItems()[self.m_combo_urls.GetSelection()]
        logger.info(" {}", self.m_combo_urls.GetValue())
        logger.info("url: {}", self.url)

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        # logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())

        # 配置名設定最多輸入100字元
        self.m_text_ctrl_name.SetValue(self.connect.get_name())
        self.m_text_ctrl_name.SetMaxLength(100)

        # 設定請求內容增加XML起始資訊
        self.m_text_ctrl_params.SetValue("<?xml version=\"1.0\" encoding=\"utf-8\"?>")

    def show_message(self, message):
        '''統一顯示對話框

        根據傳入對話框內容顯示對話框

        Args:
            message (str): 對話框內容
        '''
        wx.MessageDialog(None, message, u"操作提醒", wx.OK).ShowModal()

    def file_save_reload(self):
        # 從檔案中讀取資料
        Main.json_data = fileutils.read_json_from_file(
            pathutil.resource_path('weblog\\connections.profile')
        )
        # 連線包建立完成
        if len(Main.json_data) == 0:
            return

        connections_dict = Main.json_data.get("connections", {})
        self.connection_manager = ConnectionManager(connections_dict)

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())

    def get_connetions_urls(self, data):
        '''獲取WebService方法

        Args:
            client (suds.client): 客戶端對象
        '''
        urls = []
        for data in data.values():
            for service in data:
                urls.append(service['url'])
        return urls

    def ws_get_methods(self, client):
        '''獲取WebService方法

        Args:
            client (suds.client): 客戶端對象
        '''
        return [method for method in sorted(client.wsdl.services[0].ports[0].methods)]

    def get_method_args(self, client, method_str):
        '''獲取WebService方法對應的參數

        Args:
            client (suds.client): 客戶端對象
            method_str (str): 方法名稱
        '''
        method = client.wsdl.services[0].ports[0].methods[method_str]
        input_params = method.binding.input
        return input_params.param_defs(method)

    def update_service_name(self, url, name):
        # 無詢問直接更新配置名方法
        for data in Main.json_data.values():
            for service in data:
                if service['url'] == url:
                    service['name'] = name
        logger.info(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file("weblog\\connections.profile")
        self.file_save_reload()

    '''
    更新WebService服務方法
    '''

    def update_service_methods(self, url, new_methods):
        # 無詢問直接更新服務方法
        for data in Main.json_data.values():
            for service in data:
                if service['url'] == url:
                    service['method'] = new_methods
        logger.info(" {}", Main.json_data)
        # 更新完高速寫入connections.profile
        self.write_to_file("weblog\\connections.profile")
        self.file_save_reload()

    '''
    將DICT(json_data)資料寫入 connections.profile
    '''

    def write_to_file(self, file_name):
        # 寫入檔案內
        fileutils.write_json_to_file(
            Main.json_data,
            pathutil.resource_path(file_name)
        )

    # 執行讀取服務的事件
    def OnClickEventLoad(self, event):
        if len(self.m_combo_urls.GetValue()) == 0:
            self.show_message(u"請填寫WSDL地址")
            return
        try:
            # 禁用按鈕
            self.m_btn_load.Disable()
            self.m_btn_start.Disable()
            self.m_btn_clear.Disable()
            logger.info("{}", self.m_combo_urls.GetValue())
            client = suds.client.Client(self.m_combo_urls.GetValue(), timeout=3)
            # methods list loading
            methods = self.ws_get_methods(client)
            methods_str = json.dumps(methods)
            logger.info(" {}", methods_str)

            self.update_service_methods(
                self.m_combo_urls.GetValue(), methods
            )

            self.m_combo_methods.SetItems(methods)
            self.m_combo_methods.SetSelection(0)

        except Exception as err:
            logger.error("讀取發生異常: {}", err)
            self.show_message("讀取發生異常: " + str(err))
        finally:
            # 啟用按鈕
            self.m_btn_load.Enable()
            self.m_btn_start.Enable()
            self.m_btn_clear.Enable()

    # 處理請求執行處理的事件
    def OnClickEventStart(self, event):
        url = self.m_combo_urls.GetValue()
        if len(url) == 0:
            self.show_message(u"請填寫WSDL地址")
            return

        select_methods_index = self.m_combo_methods.GetSelection()
        if select_methods_index < 0:
            self.show_message(u"請選擇請求服務方法")
            return
        method = self.m_combo_methods.GetItems()[select_methods_index]
        self.m_text_ctrl_result.Clear()
        try:
            # 禁用按鈕
            self.m_btn_load.Disable()
            self.m_btn_start.Disable()
            self.m_btn_clear.Disable()
            data = self.m_text_ctrl_params.GetValue().replace('\n',
                                                              '').split('#~#')
            client = suds.client.Client(url)
            args = self.get_method_args(client, method)
            if len(args) != len(data):
                self.show_message(u"該服務方法需要" + str(len(args)) + "個參數，而你只輸入了" +
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
            self.show_message("請求服務後發生異常: " + str(err))
        finally:
            # 啟用按鈕
            self.m_btn_load.Enable()
            self.m_btn_start.Enable()
            self.m_btn_clear.Enable()

    def OnTextCtrlNameText(self, event):
        logger.info('OnTextCtrlNameText: %s' % event.GetString())
        self.update_service_name(
            self.m_combo_urls.GetValue(), event.GetString()
        )

    def OnTextCtrlNameTextEnter(self, event):
        logger.info('OnTextCtrlNameTextEnter: %s' % event.GetString())

    def OnTextCtrlNameMaxLen(self, event):
        logger.info('OnTextCtrlNameMaxLen: %s' % event.GetString())
        dlg = wx.MessageDialog(None, u"輸入太長了", u"輸入提醒", wx.OK | wx.ICON_WARNING)
        if dlg.ShowModal() == wx.ID_OK:
            logger.info("還原回:{}", self.connect.get_name())
            self.m_text_ctrl_name.SetValue(self.connect.get_name())

    def OnComboBoxUrlsSelect(self, event):
        logger.info('OnComboBoxUrlsSelect: %s' % event.GetString())
        item = event.GetSelection()

        self.url = self.m_combo_urls.GetItems()[item]
        logger.info(" {}", self.m_combo_urls.GetValue())
        logger.info("url: {}", self.url)

        self.connect = self.connection_manager.get_connection_by_url(self.url)
        # logger.info("connect: {}", self.connect)
        logger.info("connect(uuid) -{}", self.connect.get_uuid())
        logger.info("connect(name) -{}", self.connect.get_name())
        logger.info("connect(url)  -{}", self.connect.get_url())

        # 配置名設定最多輸入100字元
        self.m_text_ctrl_name.SetValue(self.connect.get_name())
        self.m_text_ctrl_name.SetMaxLength(100)

    """
    若網址選擇後，將選擇值改為選擇的connect
    Args:
        event (wx.CommandEvent): The event object containing information about the event.
    Returns:
        None
    """

    def OnComboBoxUrlsText(self, event):
        logger.info('OnComboBoxUrlsText: %s' % event.GetString())
        item = event.GetSelection()

    def OnComboBoxUrlsEnter(self, event):
        logger.info('OnComboBoxUrlsEnter: %s' % event.GetString())

    # 處理服務方法下拉框選擇事件
    def OnComboBoxMethodSelect(self, event):
        logger.info('OnComboBoxMethodSelect: %s' % event.GetString())
        item = event.GetSelection()

    def OnComboBoxMethodText(self, event):
        logger.info('OnComboBoxMethodText: %s' % event.GetString())
        # 获取ComboBox中已有的选项
        # current_method_options = self.m_combo_methods.GetItems()
        # new_option = event.GetString()
        # logger.error("貼上後取得選擇內容: {}", current_method_options)
        # for option in current_method_options.items:
        #    logger.info("{} {}", option)
        #    if option == new_option:
        # 如果新选项不在当前选项中，则添加到ComboBox中
        # self.m_combo_methods.Append(option)
        #        continue
        #    else:
        # 如果新选项已经存在于当前选项中，则直接设置ComboBox的值为该选项
        #        logger.info("{} {}", option, new_option)
        #        self.m_combo_methods.SetValue(option)
        #        break  # 可以选择终止循环，以确保只设置一次值

        item = event.GetSelection()

    #  處理退出選單事件
    def OnMenuClickEventExit(self, event):
        dlg = wx.MessageDialog(None, u"確定退出嗎？", u"退出提醒", wx.YES_NO)
        if dlg.ShowModal() == wx.ID_YES:
            self.Destroy()
        dlg.Destroy()

    # 處理清空按鈕的事件
    def OnClickEventClear(self, event):
        self.m_combo_urls.SetValue("")
        self.m_text_ctrl_params.SetValue("")
        self.m_text_ctrl_result.SetValue("")
        self.m_combo_methods.Clear()
