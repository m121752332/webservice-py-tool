# -*- coding: utf-8 -*-
"""
WebService 呼叫：讀取 WSDL 方法、依參數呼叫方法、XML 排版
"""
import re
import threading
import time
from dataclasses import dataclass

from lxml import etree
from suds.client import Client

PARAM_SEPARATOR = "#~#"
_DECLARATION = re.compile(r"^\s*(<\?xml[^>]*\?>)\s*")


@dataclass
class CallResult:
    text: str
    elapsed: float
    size: int


class ParamCountMismatch(Exception):
    def __init__(self, expected: int, actual: int):
        super().__init__(
            f"此方法需要 {expected} 個參數，目前輸入 {actual} 個（多個參數請用 {PARAM_SEPARATOR} 隔開）"
        )
        self.expected = expected
        self.actual = actual


def split_params(raw: str) -> list[str]:
    """移除換行後以 #~# 切分參數（沿用舊版規則）"""
    return raw.replace("\r", "").replace("\n", "").split(PARAM_SEPARATOR)


def format_xml(text: str) -> str:
    """重新縮排 XML；保留原本的 <?xml ?> 宣告。不是合法 XML 時丟出 ValueError"""
    match = _DECLARATION.match(text)
    declaration = match.group(1) if match else ""
    body = text[match.end():] if match else text
    parser = etree.XMLParser(remove_blank_text=True)
    try:
        root = etree.fromstring(body.strip(), parser)
    except etree.XMLSyntaxError as err:
        raise ValueError(f"不是合法的 XML：{err}") from err
    pretty = etree.tostring(root, encoding="unicode", pretty_print=True)
    return f"{declaration}\n{pretty}" if declaration else pretty


def _default_client_factory(url: str, timeout: int) -> Client:
    # cache=None：每次「讀取 WSDL」都重新下載，不使用 suds 預設一天的磁碟快取
    return Client(url, timeout=timeout, cache=None)


def _port_methods(client: Client):
    return client.wsdl.services[0].ports[0].methods


def _param_names(client: Client, method: str) -> list[str]:
    methods = _port_methods(client)
    if method not in methods:
        raise ValueError(f"WSDL 中找不到方法 {method}")
    definition = methods[method]
    return [str(param[0]) for param in definition.binding.input.param_defs(definition)]


class SoapService:
    def __init__(self, client_factory=_default_client_factory):
        self._client_factory = client_factory
        self._clients: dict[str, Client] = {}
        self._lock = threading.Lock()

    def load_methods(self, url: str, timeout: int) -> list[str]:
        client = self._client_factory(url, timeout)
        with self._lock:
            self._clients[url] = client
        return sorted(str(name) for name in _port_methods(client))

    def call(self, url: str, method: str, raw_params: str, timeout: int) -> CallResult:
        client = self._client_for(url, timeout)
        names = _param_names(client, method)
        values = split_params(raw_params)
        if len(values) != len(names):
            raise ParamCountMismatch(expected=len(names), actual=len(values))
        started = time.perf_counter()
        result = getattr(client.service, method)(**dict(zip(names, values)))
        elapsed = time.perf_counter() - started
        raw = "" if result is None else str(result)
        try:
            text = format_xml(raw)
        except ValueError:
            text = raw
        return CallResult(text=text, elapsed=elapsed, size=len(raw.encode("utf-8")))

    def _client_for(self, url: str, timeout: int) -> Client:
        with self._lock:
            client = self._clients.get(url)
        if client is None:
            client = self._client_factory(url, timeout)
            with self._lock:
                self._clients[url] = client
        else:
            # 取消後的舊請求可能仍在使用同一個 client；suds 1.2 的 clone() 會 RecursionError，
            # 所以直接共用，只更新逾時設定
            client.set_options(timeout=timeout)
        return client
