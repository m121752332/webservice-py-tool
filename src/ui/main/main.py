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
from src.utils import pathutil


class Main(frame.MainFrame):
    def __init__(self, parent):
        frame.MainFrame.__init__(self, parent)
        self.icon = wx.Icon(pathutil.resource_path('img/favicon.ico'),
                            wx.BITMAP_TYPE_ICO)
        self.SetIcon(self.icon)
        self.Centre()
        self.m_text_ctrl_params.SetValue("<?xml version=\"1.0\" encoding=\"utf-8\"?>")

    def show_message(self, message):
        '''統一顯示對話框

        根據傳入對話框內容顯示對話框

        Args:
            message (str): 對話框內容
        '''
        wx.MessageDialog(None, message, u"操作提醒", wx.OK).ShowModal()

    def get_methods(self, client):
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

    # 實現加載的事件
    def OnClickEventLoad(self, event):
        if len(self.m_text_ctrl_url.GetValue()) == 0:
            self.show_message(u"請填寫WSDL地址")
            return
        try:
            #禁用按鈕
            self.m_btn_load.Disable()
            self.m_btn_start.Disable()
            self.m_btn_clear.Disable()
            client = suds.client.Client(self.m_text_ctrl_url.GetValue())
            methods = self.get_methods(client)
            self.m_combo_methods.SetItems(methods)
            self.m_combo_methods.SetSelection(0)
        except Exception as err:
            logger.error("加載發生異常: {}", err)
            self.show_message("加載發生異常: " + str(err))
        finally:
            #啟用按鈕
            self.m_btn_load.Enable()
            self.m_btn_start.Enable()
            self.m_btn_clear.Enable()

    # 實現調用的事件
    def OnClickEventStart(self, event):
        url = self.m_text_ctrl_url.GetValue()
        if len(url) == 0:
            self.show_message(u"請填寫WSDL地址")
            return
        select_methods_index = self.m_combo_methods.GetSelection()
        if select_methods_index < 0:
            self.show_message(u"請選擇調用方法")
            return
        method = self.m_combo_methods.GetItems()[select_methods_index]
        self.m_text_ctrl_result.Clear()
        try:
            #禁用按鈕
            self.m_btn_load.Disable()
            self.m_btn_start.Disable()
            self.m_btn_clear.Disable()
            data = self.m_text_ctrl_params.GetValue().replace('\n',
                                                              '').split('#~#')
            client = suds.client.Client(url)
            args = self.get_method_args(client, method)
            if len(args) != len(data):
                self.show_message(u"該方法需要" + str(len(args)) + "個參數，而你只輸入了" +
                                  str(len(data)) + "個，多參數請使用#~#隔開，並保證參數順序")
                return
            argv = {}
            for index in range(len(args)):
                argv[args[index][0]] = data[index]
            result = getattr(client.service, method)(**argv)
            logger.info("\n地址: {}\n方法：{}\n參數：{}\n返回: {}", url, method, argv, result)
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
            self.show_message("請求後發生異常: " + str(err))
        finally:
            #啟用按鈕
            self.m_btn_load.Enable()
            self.m_btn_start.Enable()
            self.m_btn_clear.Enable()

    # 實現方法下拉框選擇事件
    def OnComboBoxMethodSelect(self, event):
        item = event.GetSelection()

    # 實現退出菜單事件
    def OnMenuClickEventExit(self, event):
        dlg = wx.MessageDialog(None, u"確定退出嗎？", u"退出提醒", wx.YES_NO)
        if dlg.ShowModal() == wx.ID_YES:
            self.Destroy()
        dlg.Destroy()

    # 實現清空按鈕的事件
    def OnClickEventClear(self, event):
        self.m_text_ctrl_url.SetValue("")
        self.m_text_ctrl_params.SetValue("")
        self.m_text_ctrl_result.SetValue("")
        self.m_combo_methods.Clear()