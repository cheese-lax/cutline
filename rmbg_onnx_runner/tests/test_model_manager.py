
from model_manager import provider_catalog


def test_provider_catalog_filters_supported_choices():
    assert provider_catalog(["CoreMLExecutionProvider", "CPUExecutionProvider", "AzureExecutionProvider"], "Darwin") == [
        {"id": "auto", "label": "自动检测"}, {"id": "coreml", "label": "Apple CoreML"}, {"id": "cpu", "label": "CPU"}
    ]


def test_provider_catalog_does_not_expose_unsupported_provider():
    assert provider_catalog(["CPUExecutionProvider"], "Linux") == [{"id": "auto", "label": "自动检测"}, {"id": "cpu", "label": "CPU"}]
