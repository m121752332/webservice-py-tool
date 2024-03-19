# -*- coding: utf-8 -*-
# @Time : 2021/02/20
# @Author : Tiger
# @File : pathutil.py
# @Software: vscode
"""
路径工具类
"""
import os
import sys
from src.utils import globalvalues


def resource_path(relative_path):
    """
    返回资源绝对路径
    
    参数:
        relative_path (str): 相对路径或者资源名称
    返回:
        绝对路径（带临时目录的）
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller会创建临时亙件夹temp
        # 并把路径存储在_MEIPASS
        exepath = sys._MEIPASS
    else:
        exepath = os.path.abspath('')
        if len(globalvalues.EXE_PATH) > 0:
            exepath = globalvalues.EXE_PATH
        else:
            globalvalues.EXE_PATH = exepath

    return os.path.join(exepath, relative_path)