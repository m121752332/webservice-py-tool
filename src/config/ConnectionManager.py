# -- coding: utf-8 --
# @Time : 2024/03/20
# @Author : Tiger
# @File : ConnectionManager.py
# @Software: vscode
from loguru import logger


class ConnectionManager:
    def __init__(self, connections):
        # self.connections = {conn["uuid"]: conn for conn in connections}
        self.connections = {}
        for conn in connections:
            # logger.info(" {}", type(conn))
            # logger.info(" {}", conn)
            uuid_str = conn["uuid"]
            self.connections[uuid_str] = conn

    def get_connection_by_uuid(self, uuid):
        # 從 connections 字典中逐筆抓資料
        for connection in self.connections.values():
            if connection["uuid"] == uuid:
                conn = Connect(connection["uuid"], connection["name"], connection["url"], connection["method"])
                return conn
        return None

    def get_name_by_uuid(self, uuid):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            return connection.get("name")
        return None

    def get_url_by_uuid(self, uuid):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            return connection.get("url")
        return None

    def get_method_by_uuid(self, uuid):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            return connection.get("method")
        return None

    def set_name_by_uuid(self, uuid, name):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            connection["name"] = name

    def set_url_by_uuid(self, uuid, url):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            connection["url"] = url

    def set_method_by_uuid(self, uuid, method):
        connection = self.get_connection_by_uuid(uuid)
        if connection:
            connection["method"] = method

    def get_connection_by_name(self, name):
        return self.connections.get(name)

    def get_uuid_by_name(self, name):
        connection = self.get_connection_by_name(name)
        if connection:
            return connection.get("uuid")
        return None

    def get_url_by_name(self, name):
        connection = self.get_connection_by_name(name)
        if connection:
            return connection.get("url")
        return None

    def get_method_by_name(self, name):
        connection = self.get_connection_by_name(name)
        if connection:
            return connection.get("method")
        return None

    def set_uuid_by_name(self, name, uuid):
        connection = self.get_connection_by_name(name)
        if connection:
            connection["uuid"] = uuid

    def set_url_by_name(self, name, url):
        connection = self.get_connection_by_name(name)
        if connection:
            connection["url"] = url

    def set_method_by_name(self, name, method):
        connection = self.get_connection_by_name(name)
        if connection:
            connection["method"] = method

    def get_connection_by_url(self, url):
        # 從 connections 字典中逐筆抓資料
        for connection in self.connections.values():
            if connection["url"] == url:
                conn = Connect(connection["uuid"], connection["name"], connection["url"], connection["method"])
                return conn
        return None

    def get_uuid_by_url(self, url):
        connection = self.get_connection_by_url(url)
        if connection:
            return connection.get("uuid")
        return None

    def get_name_by_url(self, url):
        connection = self.get_connection_by_url(url)
        if connection:
            return connection.get("name")
        return None

    def get_method_by_url(self, url):
        connection = self.get_connection_by_url(url)
        if connection:
            return connection.get("method")
        return None

    def set_uuid_by_url(self, url, uuid):
        connection = self.get_connection_by_url(url)
        if connection:
            connection["uuid"] = uuid

    def set_name_by_url(self, url, name):
        connection = self.get_connection_by_url(url)
        if connection:
            connection["name"] = name

    def set_method_by_url(self, url, method):
        connection = self.get_connection_by_url(url)
        if connection:
            connection["method"] = method

    def print_connections_recursively(self, connections_dict=None, indent=0):
        if connections_dict is None:
            connections_dict = self.connections
        for uuid, connection in connections_dict.items():
            print(" " * indent, f"UUID: {uuid}")
            for key, value in connection.items():
                if isinstance(value, list):
                    print(" " * (indent + 2), f"{key}:")
                    for item in value:
                        print(" " * (indent + 4), item)
                else:
                    print(" " * (indent + 2), f"{key}: {value}")
            print()


class Connect:
    def __init__(self, uuid, name, url, method):
        self.uuid = uuid
        self.name = name
        self.url = url
        self.method = method

    def get_uuid(self):
        return self.uuid

    def get_name(self):
        return self.name

    def get_url(self):
        return self.url

    def get_method(self):
        return self.method
