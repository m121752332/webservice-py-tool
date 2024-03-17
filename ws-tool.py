# -*- coding: utf-8 -*-
# @Time : 2021/09/29
# @Author : Tiger
# @File : ws-tool.py
# @Software: vscode
"""
启动
"""
import wx
from ui import main
from loguru import logger

if __name__ == '__main__':
    """
    程式入口
    """
    logger.add('out.log')
    app = wx.App(False)
    frame = main.Main(None)
    frame.Show(True)
    try:
        app.MainLoop()
    except Exception as err:
        logger.error('程式發生異常問題: {}', err)
        raise