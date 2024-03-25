# -- coding: utf-8 --
# @Time : 2021/02/20
# @Author : Tiger
# @File : balloontip.py
# @Software: vscode

import wx.lib.agw.balloontip as bat
import wx

"""
檔案存取類
"""


def show_balloon_tip(item, toptitle, message):
    # You can define your BalloonTip as follows:
    tip = bat.BalloonTip(topicon=None, toptitle=toptitle,
                         message=message,
                         shape=bat.BT_ROUNDED,
                         tipstyle=bat.BT_BUTTON)

    # Set the BalloonTip target
    tip.SetTarget(item)
    # Set the BalloonTip background colour
    tip.SetBalloonColour(wx.Colour(128, 128, 128))
    # Set the font for the balloon title
    tip.SetTitleFont(wx.Font(9, wx.SWISS, wx.NORMAL, wx.BOLD, False))
    # Set the colour for the balloon title
    tip.SetTitleColour(wx.BLUE)
    # Leave the message font as default
    tip.SetMessageFont()
    # Set the message (tip) foreground colour
    tip.SetMessageColour(wx.BLUE)
    # Set the start delay for the BalloonTip
    tip.SetStartDelay(1000)
    # Set the time after which the BalloonTip is destroyed
    tip.SetEndDelay(5000)
