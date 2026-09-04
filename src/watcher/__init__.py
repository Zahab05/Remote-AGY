from src.watcher.base import BaseSLCMAdapter, AssignmentData
from src.watcher.mock_watcher import MockSLCMAdapter
from src.watcher.ui_satu_adapter import SatuUIAdapter

def get_adapter(name: str, config: dict = None) -> BaseSLCMAdapter:
    config = config or {}
    if name == "ui_satu":
        return SatuUIAdapter(config)
    elif name == "mock":
        return MockSLCMAdapter(config)
    else:
        raise ValueError(f"Unknown adapter: {name}")
