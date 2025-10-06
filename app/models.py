
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

@dataclass
class Ingredient:
    id: str
    name: str
    measure: Optional[str] = None

@dataclass
class Attribution:
    source_name: str
    source_url: str
    author: Optional[str] = None
    license: Optional[str] = None
    fetched_at: Optional[str] = None

@dataclass
class RecipeVersion:
    id: str
    name: str
    name_slug: str
    ingredients: List[Ingredient]
    instructions: str
    glass: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    image: Optional[str] = None
    garnish: Optional[str] = None
    method: Optional[str] = None
    attribution: Attribution = None

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d

@dataclass
class CanonicalRecipe:
    id: str
    name: str
    versions: List[str]
    primary_version_id: Optional[str] = None
    aka: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
