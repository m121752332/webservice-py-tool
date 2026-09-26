# -*- coding: utf-8 -*-
# @Time : 2024/03/20
# @Author : Tiger
# @File : web_service_config.py
# @Software: vscode
from pathlib import Path

from src.utils import yaml_values, path_util


class WebServiceConfig:

    def __init__(self):
        # 實際讀取的設定檔位置；設定頁也寫回同一個檔案
        self.config_path = Path(path_util.resource_abspath('app_data\\ws_tool.yaml'))
        self.app_config = yaml_values.load_yaml_file(self.config_path)

        # APP 配置
        self.app_name = self.app_config['app']['name']
        self.app_version = self.app_config['app']['version']
        self.app_copyright = self.app_config['app']['copyright']
        self.app_timeout = self.app_config['app']['timeout']
        # IMG 配置
        self.app_img_path = self.app_config['app']['img']

        # LOG 配置
        self.app_log_path = self.app_config['app']['log']['path']
        self.app_log_level = self.app_config['app']['log']['level']
        self.app_log_retention = self.app_config['app']['log']['retention']

        # CONN 配置
        self.app_connection_path = self.app_config['app']['connection']['path']
        self.app_connection_profile = self.app_config['app']['connection']['profile']
