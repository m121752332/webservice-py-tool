# -- coding: utf-8 --
# @Time : 2021/02/20
# @Author : Tiger
# @File : pathutil.py
# @Software: vscode
"""
檔案存取類
"""
import json


def write_json_to_file(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)


def read_json_from_file(filename):
    with open(filename, 'r') as file:
        data = json.load(file)
        return data
