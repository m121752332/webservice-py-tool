# -- coding: utf-8 --
# @Time : 2024/03/20
# @Author : Tiger
# @File : ConnectionManager.py
# @Software: vscode
from loguru import logger

from src.utils import yaml_values, pathutil


class WebServiceConfig:

    def __init__(self):
        self.app_config = yaml_values.load_yaml_file(
            pathutil.resource_abspath('app_data\\ws_tool.yaml')
        )

        # APP 配置
        self.app_name = self.app_config['app']['name']
        self.app_version = self.app_config['app']['version']
        self.app_copyright = self.app_config['app']['copyright']

        # LOG 配置
        self.app_log_path = self.app_config['app']['log']['path']
        self.app_log_level = self.app_config['app']['log']['level']
        self.app_log_retention = self.app_config['app']['log']['retention']

        # CONN 配置
        self.app_connection_path = self.app_config['app']['connection']['path']
        self.app_connection_profile = self.app_config['app']['connection']['profile']

        # IMG 配置
        self.app_img_path = self.app_config['app']['img']

    def get_app_name(self):
        return self.app_name

    def get_app_version(self):
        return self.app_version

    def get_app_copyright(self):
        return self.app_copyright

    def get_app_log_path(self):
        return self.app_log_path

    def get_app_log_level(self):
        return self.app_log_level

    def get_app_log_retention(self):
        return self.app_log_retention

    def get_app_img_path(self):
        return self.app_img_path

    def get_app_connection_path(self):
        return self.app_connection_path

    def get_app_connection_profile(self):
        return self.app_connection_profile
