# -*- coding: utf-8 -*-
from pathlib import Path
from xml.sax.saxutils import escape

import pytest
from suds.client import Client
from suds.transport import Reply
from suds.transport.http import HttpTransport

from src.core.soap_service import ParamCountMismatch, SoapService, format_xml, split_params

WSDL_URL = (Path(__file__).parent / "fixtures" / "sample.wsdl").resolve().as_uri()


class FakeTransport(HttpTransport):
    """WSDL 照常從檔案讀取；送出的 SOAP 請求改為回傳預先準備的回應"""

    def __init__(self, body, sent):
        super().__init__()
        self._body = body
        self._sent = sent

    def send(self, request):
        self._sent.append(request.message)
        return Reply(200, {"Content-Type": "text/xml; charset=utf-8"}, self._body)


class FakeClientFactory:
    """每次建立 Client 都配一個新的 transport（suds 的 transport 不能給多個 Client 共用）"""

    def __init__(self, response_element="GetPODataResponse", response_text="<ok/>"):
        self._body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
            f'<{response_element} xmlns="http://example.com/ws">'
            f'<response>{escape(response_text)}</response>'
            f'</{response_element}>'
            '</soap:Body></soap:Envelope>'
        ).encode("utf-8")
        self.sent = []
        self.clients = []

    def __call__(self, url, timeout):
        client = Client(url, timeout=timeout, cache=None, transport=FakeTransport(self._body, self.sent))
        self.clients.append(client)
        return client


def test_split_params_single():
    assert split_params("<a/>") == ["<a/>"]


def test_split_params_multiple_and_strips_newlines():
    assert split_params("<a>\r\n  1</a>#~#\n<b/>") == ["<a>  1</a>", "<b/>"]


def test_format_xml_indents_and_keeps_declaration():
    raw = '<?xml version="1.0" encoding="utf-8"?><Request><Access user="a"/></Request>'
    assert format_xml(raw) == (
        '<?xml version="1.0" encoding="utf-8"?>\n<Request>\n  <Access user="a"/>\n</Request>\n'
    )


def test_format_xml_reindents_existing_whitespace():
    assert format_xml("<a>\n      <b/>\n</a>") == "<a>\n  <b/>\n</a>\n"


def test_format_xml_keeps_non_utf8_declaration():
    assert format_xml('<?xml version="1.0" encoding="big5"?><r>中文</r>') == (
        '<?xml version="1.0" encoding="big5"?>\n<r>中文</r>\n'
    )


@pytest.mark.parametrize("bad", ["", "   ", "<a>", "not xml", "3"])
def test_format_xml_rejects_invalid(bad):
    with pytest.raises(ValueError):
        format_xml(bad)


def test_param_count_mismatch_message():
    err = ParamCountMismatch(expected=2, actual=1)
    assert (err.expected, err.actual) == (2, 1)
    assert str(err) == "此方法需要 2 個參數，目前輸入 1 個（多個參數請用 #~# 隔開）"


def test_load_methods_returns_sorted_names():
    service = SoapService(client_factory=FakeClientFactory())
    assert service.load_methods(WSDL_URL, 5) == ["AddTwo", "GetPOData"]


def test_load_methods_always_rebuilds_client():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.load_methods(WSDL_URL, 5)
    service.load_methods(WSDL_URL, 5)
    assert len(factory.clients) == 2


def test_call_maps_param_and_formats_response():
    factory = FakeClientFactory("GetPODataResponse", '<Response><Status code="0"/></Response>')
    service = SoapService(client_factory=factory)
    result = service.call(WSDL_URL, "GetPOData", "<Request/>", 5)
    assert result.text == '<Response>\n  <Status code="0"/>\n</Response>\n'
    assert result.size == len('<Response><Status code="0"/></Response>'.encode("utf-8"))
    assert result.elapsed >= 0
    assert b"&lt;Request/&gt;" in factory.sent[0]


def test_call_with_multiple_params_returns_raw_non_xml():
    factory = FakeClientFactory("AddTwoResponse", "3")
    service = SoapService(client_factory=factory)
    result = service.call(WSDL_URL, "AddTwo", "1#~#2", 5)
    assert result.text == "3"
    assert result.size == 1
    assert b">1</" in factory.sent[0] and b">2</" in factory.sent[0]


def test_call_raises_on_param_count_mismatch():
    service = SoapService(client_factory=FakeClientFactory("AddTwoResponse", "3"))
    with pytest.raises(ParamCountMismatch) as info:
        service.call(WSDL_URL, "AddTwo", "only-one", 5)
    assert (info.value.expected, info.value.actual) == (2, 1)


def test_call_unknown_method_raises_value_error():
    service = SoapService(client_factory=FakeClientFactory())
    with pytest.raises(ValueError, match="NoSuchMethod"):
        service.call(WSDL_URL, "NoSuchMethod", "<r/>", 5)


def test_call_reuses_client_from_load_methods():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.load_methods(WSDL_URL, 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    assert len(factory.clients) == 1


def test_call_updates_timeout_on_cached_client():
    factory = FakeClientFactory()
    service = SoapService(client_factory=factory)
    service.call(WSDL_URL, "GetPOData", "<r/>", 5)
    service.call(WSDL_URL, "GetPOData", "<r/>", 30)
    assert len(factory.clients) == 1
    assert factory.clients[0].options.timeout == 30


class BrokenTransport(HttpTransport):
    def send(self, request):
        raise ConnectionError("連線被拒")


def broken_factory(url, timeout):
    return Client(url, timeout=timeout, cache=None, transport=BrokenTransport())


def test_call_records_success_with_envelopes():
    records = []
    service = SoapService(FakeClientFactory(response_text="<r>好</r>"), recorder=records.append)
    result = service.call(WSDL_URL, "GetPOData", "<a/>", 5, connection="訂單")
    [record] = records
    assert (record.connection, record.url, record.method, record.status, record.error) == (
        "訂單", WSDL_URL, "GetPOData", "success", "",
    )
    assert (record.params, record.response, record.size) == ("<a/>", result.text, result.size)
    assert "Envelope" in record.sent and "GetPOData" in record.sent
    assert "GetPODataResponse" in record.received
    assert record.elapsed >= 0


def test_call_records_failure_and_reraises():
    records = []
    service = SoapService(broken_factory, recorder=records.append)
    with pytest.raises(Exception, match="連線被拒"):
        service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    [record] = records
    assert record.status == "failed" and "連線被拒" in record.error and record.response == ""
    assert record.received == ""


def test_param_mismatch_is_not_recorded():
    records = []
    service = SoapService(FakeClientFactory(), recorder=records.append)
    with pytest.raises(ParamCountMismatch):
        service.call(WSDL_URL, "GetPOData", "<a/>#~#<b/>", 5)
    assert records == []


def test_recorder_error_does_not_break_call():
    def boom(_record):
        raise RuntimeError("寫檔失敗")

    service = SoapService(FakeClientFactory(), recorder=boom)
    assert service.call(WSDL_URL, "GetPOData", "<a/>", 5).text


def test_failed_call_does_not_reuse_previous_envelope():
    records = []
    factory = FakeClientFactory()
    service = SoapService(factory, recorder=records.append)
    service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    factory.clients[0].set_options(transport=BrokenTransport())
    with pytest.raises(Exception):
        service.call(WSDL_URL, "GetPOData", "<a/>", 5)
    assert records[1].received == ""
