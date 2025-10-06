
from typing import Dict, List
from app.models import RecipeVersion, CanonicalRecipe
from utils.text import slugify

def group_versions(versions: List[RecipeVersion]) -> Dict[str, List[RecipeVersion]]:
    buckets = {}
    for v in versions:
        key = v.name_slug or slugify(v.name)
        buckets.setdefault(key, []).append(v)
    return buckets

def pick_primary(group: List[RecipeVersion]) -> str:
    for v in group:
        if v.id.startswith("iba::"):
            return v.id
    group_sorted = sorted(group, key=lambda x: len(x.instructions or ""), reverse=True)
    return group_sorted[0].id

def merge_to_canonical(versions: List[RecipeVersion]) -> List[CanonicalRecipe]:
    buckets = group_versions(versions)
    canon = []
    for key, group in buckets.items():
        name = group[0].name
        primary = pick_primary(group)
        canon.append(CanonicalRecipe(
            id=key,
            name=name,
            versions=[v.id for v in group],
            primary_version_id=primary,
            aka=[]
        ))
    return canon
