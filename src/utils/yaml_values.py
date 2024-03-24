# -- coding: utf-8 --
# @Time : 2024/03/24
# @Author : Tiger
# @File : yaml_values.py
# @Software: vscode

import yaml


def load_yaml_file(yaml_file):
    with open(yaml_file, 'rb') as f:
        yaml_values = yaml.load(f, Loader=yaml.FullLoader)
    return yaml_values
