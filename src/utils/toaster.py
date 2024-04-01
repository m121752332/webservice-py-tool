# -- coding: utf-8 --
# @Time : 2024/03/31
# @Author : Tiger
# @File : toaster.py
# @Software: vscode
import sys
import traceback
from enum import Enum

import wx
import wx.adv
import wx.lib.agw.toasterbox as TB
from loguru import logger


def show_message(message):
    """統一顯示對話框

    根據傳入對話框內容顯示對話框

    Args:
        message (str): 對話框內容
    """
    wx.MessageDialog(None, message, u"傳遞檢查", wx.OK).ShowModal()


def send(enum_msg, title, message):
    """
    Function to send a message with a specified title and content.

    Args:
        enum_msg:
        title (str): The title of the message.
        message (str): The content of the message.
    """
    try:
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
        # tb.SetPopupPosition(wx.Position(x - 100, y + 10))
        # 在主框體中間
        tb.CenterOnParent()
        # 在螢幕正中間
        tb.CenterOnScreen()

        # wx controls
        tb_panel = tb.GetToasterBoxWindow()
        panel = wx.Panel(tb_panel, -1)

        # 检查 enum_msg 是否在 EnumMsg 枚举中
        if enum_msg.upper() not in EnumMsg.__members__:
            return show_message("請檢查訊息字串是否正確! enum_msg: %s" % enum_msg)

        panel.SetBackgroundColour(EnumMsg[enum_msg.upper()].value)
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


class EnumMsg(Enum):
    SUCCESS = 'blue'
    ERROR = 'red'
    QUESTION = 'white'
    WARNING = 'yellow'
    INFO = 'green'
    INFORMATION = 'green'
