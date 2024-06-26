# -- coding: utf-8 --
# @Time : 2024/03/31
# @Author : Tiger
# @File : ws_tool.py
# @Software: vscode
"""
啟動
"""
import wx

from src.ui import main
from loguru import logger

if __name__ == '__main__':

    app = wx.App(False)
    frame = main.Main(None)
    frame.Show(True)

    try:
        app.MainLoop()
    except Exception as err:
        logger.error('程式發生異常問題: {}', err)
        raise

