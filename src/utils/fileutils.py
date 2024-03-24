# -- coding: utf-8 --
# @Time : 2021/02/20
# @Author : Tiger
# @File : pathutil.py
# @Software: vscode
"""
檔案存取類
"""
import json

from loguru import logger

"""
Write the given data to a JSON file.
:param data: the data to be written to the file
:param filename: the name of the file to write to
"""


def write_json_to_file(data, filename):
    logger.debug("write_json_to_file: %s" % filename)
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)


"""
Reads a JSON file and returns its contents as a Python object.
Parameters:
    filename (str): The path to the JSON file to be read.
Returns:
    dict or list: The contents of the JSON file as a Python object.
"""


def read_json_from_file(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return data
