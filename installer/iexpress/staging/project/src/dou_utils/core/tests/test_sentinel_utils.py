import pytest
from dou_utils.core.sentinel_utils import is_placeholder_text, is_sentinel_option

def test_is_placeholder_text_basic():
    assert is_placeholder_text("Selecionar organização")
    assert is_placeholder_text("Selecione o tipo")
    assert is_placeholder_text("todos")
    assert is_placeholder_text("")  # vazio

def test_is_placeholder_text_non_placeholder():
    assert not is_placeholder_text("Ministério da Saúde")
    assert not is_placeholder_text("Educação")

def test_is_sentinel_option_dict():
    assert is_sentinel_option({"text": "Selecionar", "value": ""})
    assert is_sentinel_option({"text": "Todos", "value": "0"})
    assert not is_sentinel_option({"text": "Setor Econômico", "value": "123"})
