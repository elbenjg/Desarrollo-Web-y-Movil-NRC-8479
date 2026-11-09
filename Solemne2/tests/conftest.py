import pytest


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    items.sort(key=lambda item: item.name == "test_limite_de_solicitudes_en_login")
