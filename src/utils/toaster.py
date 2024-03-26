# -- coding: utf-8 --
# @Time : 2021/02/20
# @Author : Tiger
# @File : toaster.py
# @Software: vscode
import wx
import wx.adv
import wx.lib.agw.toasterbox as TB


def send_warning(title, message):
    """
    Function to send a message with a specified title and content.

    Args:
        title (str): The title of the message.
        message (str): The content of the message.
    """
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


def send_hint(title, message):
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
    panel.SetBackgroundColour((128, 255, 128))
    # panel.SetBackgroundColour((255, 200, 50, 255))
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


def send_error(title, message):
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
    panel.SetBackgroundColour("red")
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
