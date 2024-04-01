# -*- coding: utf-8 -*-
# @Time : 2024/03/31
# @Author : Tiger
# @File : pathutil.py
# @Software: vscode
"""
路径工具类
"""
import os
import sys

from loguru import logger

from src.utils import globalvalues

CONNECTS_PROFILE = "connections.profile"
SETTINGFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONNECTS_PROFILE)


def resource_path(relative_path):
    """
    返回资源绝对路径
    
    参数:
        relative_path (str): 相对路径或者资源名称
    返回:
        绝对路径（带临时目录的）
    """
    # logger.info("resource_path: {}", relative_path)
    # logger.info("cwd: {}", os.getcwd())
    # logger.info("SETTING FILE: {}", SETTINGFILE)
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller会创建临时亙件夹temp
        # 并把路径存储在_MEIPASS
        # logger.info("exepath: _MEIPASS = {}", sys._MEIPASS)
        exepath = sys._MEIPASS
    else:
        # logger.info("exepath: abspath = {}", os.path.abspath(''))
        exepath = os.path.abspath('')
        if len(globalvalues.EXE_PATH) > 0:
            # logger.info("exepath: EXE_PATH = {}", globalvalues.EXE_PATH)
            exepath = globalvalues.EXE_PATH
        else:
            # logger.info("exepath: EXE_PATH = {}", exepath)
            globalvalues.EXE_PATH = exepath
    return os.path.join(exepath, relative_path)


def resource_abspath(relative_path):
    # logger.info("exe path: relative_path = {}", relative_path)
    exe_path = os.path.abspath('')
    if len(globalvalues.EXE_PATH) > 0:
        # logger.info("exe path: EXE_PATH = {}", globalvalues.EXE_PATH)
        exe_path = globalvalues.EXE_PATH
    else:
        # logger.info("exe path: EXE_PATH = {}", exe_path)
        globalvalues.EXE_PATH = exe_path
    return os.path.join(exe_path, relative_path)
