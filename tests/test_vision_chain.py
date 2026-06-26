import pytest

import backend.services.vision.chain as chain_mod
from backend.services.vision.base import VisionSource
from backend.services.vision.chain import VisionChain


class StubSource(VisionSource):
    """Records how many times it was asked to capture."""

    def __init__(self, result):
        self.result = result
        self.calls = 0

    def capture(self):
        self.calls += 1
        return self.result


@pytest.fixture(autouse=True)
def fixed_window(monkeypatch):
    # Deterministic cache key so TTL behaviour is testable.
    monkeypatch.setattr(chain_mod, "get_foreground_window", lambda: 123)


def test_dom_hit_short_circuits():
    dom, acc, vlm = StubSource("DOM"), StubSource("ACC"), StubSource("VLM")
    chain = VisionChain([dom, acc, vlm], ttl=0)
    assert chain.capture() == "DOM"
    assert acc.calls == 0 and vlm.calls == 0


def test_falls_through_to_accessibility():
    dom, acc, vlm = StubSource(None), StubSource("ACC"), StubSource("VLM")
    chain = VisionChain([dom, acc, vlm], ttl=0)
    assert chain.capture() == "ACC"
    assert dom.calls == 1 and vlm.calls == 0


def test_falls_through_to_vlm():
    dom, acc, vlm = StubSource(None), StubSource(None), StubSource("VLM")
    chain = VisionChain([dom, acc, vlm], ttl=0)
    assert chain.capture() == "VLM"
    assert dom.calls == 1 and acc.calls == 1 and vlm.calls == 1


def test_all_sources_fail_returns_none():
    dom, acc, vlm = StubSource(None), StubSource(None), StubSource(None)
    chain = VisionChain([dom, acc, vlm], ttl=0)
    assert chain.capture() is None


def test_ttl_cache_avoids_recapture():
    dom = StubSource("DOM")
    chain = VisionChain([dom], ttl=999)
    chain.capture()
    chain.capture()
    assert dom.calls == 1
