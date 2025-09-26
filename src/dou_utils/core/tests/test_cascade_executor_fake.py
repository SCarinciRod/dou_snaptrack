import json
from pathlib import Path
from dou_utils.services.cascade_executor import CascadeExecutor, CascadeConfig

# Frame / Locator fakes simples

class FakeOption:
    def __init__(self, value, text):
        self._value = value
        self._text = text
    def get_attribute(self, name):
        if name == "value":
            return self._value
        return None
    def inner_text(self):
        return self._text

class FakeLocator:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data  # list or dict
        self._selected = {}
    def nth(self, idx):
        return FakeLocator(self.kind, self.data[idx])
    def locator(self, selector):
        if self.kind == "frame" and selector == "select":
            return FakeLocator("select-list", self.data["selects"])
        if self.kind == "select-list":
            # chaining .locator("option")
            if selector == "option":
                # flatten for each select index? adapt outside.
                raise RuntimeError("Use direto no select individual.")
        if self.kind == "select":
            if selector == "option":
                return FakeLocator("option-list", self.data["options"])
        if self.kind == "option-list":
            # not expecting deeper
            pass
        if self.kind == "frame" and selector == ".results":
            return FakeLocator("results-root", self.data["results"])
        # fallback - return empty
        return FakeLocator("empty", [])
    def count(self):
        if isinstance(self.data, list):
            return len(self.data)
        return 0
    def first(self):
        return self.nth(0)
    # select <select>
    def select_option(self, value):
        if self.kind != "select":
            raise RuntimeError("select_option apenas em select.")
        # validate value exists
        opts = [o.get("value") for o in self.data["options"]]
        if value not in opts:
            raise RuntimeError(f"valor {value} nao encontrado")
        self.data["_selected"] = value
    # option accessor
    def get_attribute(self, name):
        if self.kind == "option":
            if name == "value":
                return self.data.get("value")
        return None
    def inner_text(self):
        if self.kind == "option":
            return self.data.get("text")
        if self.kind == "result-item":
            return self.data.get("text")
        return ""
    def __getitem__(self, idx):
        return self.data[idx]
    # for option-list iteration
    def nth_option(self, i):
        return FakeLocator("option", self.data[i])
    def nth(self, idx):
        if self.kind in ("select-list",):
            return FakeLocator("select", self.data[idx])
        if self.kind == "option-list":
            return FakeLocator("option", self.data[idx])
        if self.kind == "results-list":
            return FakeLocator("result-item", self.data[idx])
        if isinstance(self.data, list):
            return FakeLocator(self.kind, self.data[idx])
        return FakeLocator("empty", [])

class FakeFrame(FakeLocator):
    def __init__(self, structure):
        super().__init__("frame", structure)
    # override required pattern
    def locator(self, selector):
        if selector == "select":
            return FakeLocator("select-list", self.data["selects"])
        if selector == ".results":
            return FakeLocator("results-root", self.data["results"])
        return FakeLocator("empty", [])

def build_fake_frame():
    structure = {
        "selects": [
            {  # N1
                "options": [
                    {"value": "", "text": "Selecione"},
                    {"value": "MA", "text": "Min A"},
                    {"value": "MB", "text": "Min B"},
                ]
            },
            {  # N2
                "options": [
                    {"value": "", "text": "Selecione"},
                    {"value": "PORT", "text": "Portaria"},
                    {"value": "RES", "text": "Resolução"},
                ]
            }
        ],
        # Results dinamicamente dependerão do par selecionado; simularemos via monkey patch no executor.
        "results": []
    }
    return FakeFrame(structure)

def test_cascade_executor_basic_dynamic(monkeypatch):
    frame = build_fake_frame()

    # Plan somente N1 (dynamicN2=True)
    plan = {
        "dynamicN2": True,
        "combos": [
            {"key1": "MA", "label1": "Min A", "_dynamicN2": True}
        ],
        "defaults": {}
    }

    # Monkeypatch _extract_results para depender do select atual
    def fake_extract_results(self):
        k1 = None
        k2 = None
        sel_list = frame.data["selects"]
        sel1 = sel_list[0].get("_selected")
        sel2 = sel_list[1].get("_selected")
        k1 = sel1
        k2 = sel2
        # gerar itens baseados em k1/k2
        if k1 and k2:
            return [{"text": f"{k1}-{k2}-Item1", "href": f"http://ex/{k1}/{k2}/1"}]
        return []
    monkeypatch.setattr("dou_utils.services.cascade_executor.CascadeExecutor._extract_results", fake_extract_results)

    cfg = CascadeConfig(
        n1_index=0,
        n2_index=1,
        results_root_selector=".results"
    )
    executor = CascadeExecutor(frame, cfg)
    result = executor.run(plan)

    assert result["summary"]["ok"] >= 1
    assert result["results"]
    first = result["results"][0]
    assert first["status"] in ("ok", "empty")
    # Ao menos 1 expansion
    assert any(r["combo"]["key2"] for r in result["results"])
