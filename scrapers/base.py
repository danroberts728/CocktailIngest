
from typing import Iterator
from app.models import RecipeVersion
from abc import ABC, abstractmethod

_REGISTRY = {}

def register_source(name: str):
    def wrap(cls):
        _REGISTRY[name] = cls
        return cls
    return wrap

def get_scraper(name: str, **kwargs):
    cls = _REGISTRY.get(name)
    if not cls:
        raise ValueError(f'Unknown source: {name}. Registered: {list(_REGISTRY.keys())}')
    return cls(**kwargs)

class SourceScraper(ABC):
    @abstractmethod
    def iter_recipes(self) -> Iterator[RecipeVersion]:
        raise NotImplementedError
