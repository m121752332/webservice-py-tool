# -*- coding: utf-8 -*-
# @Time : 2024/03/31
# @Author : Tiger
# @File : uuid_util.py
# @Software: vscode

import uuid

"""
UUID 產生工具
"""


def new_uuid() -> str:
    return str(uuid.uuid4())
