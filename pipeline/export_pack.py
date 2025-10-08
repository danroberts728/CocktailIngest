# pipeline/export_pack.py
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

def load_canonical(path: str) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_versions(paths: List[str]) -> Dict[str, dict]:
    """Map version_id -> RecipeVersion dict (from *.jsonl)."""
    out: Dict[str, dict] = {}
    for p in paths:
        for line in Path(p).read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            out[d["id"]] = d
    return out

def _flatten_primary(canon_item: dict, versions: Dict[str, dict]) -> Tuple[dict, dict]:
    """
    Returns (compact_primary_record, primary_version_dict)
    - compact_primary_record is what your web app can list quickly
    - primary_version_dict is the full source-raw RecipeVersion
    """
    primary_id = canon_item.get("primary_version_id") or canon_item["versions"][0]
    v = versions.get(primary_id)
    if not v:
        return None, None
    # Build compact
    compact = {
        "id": canon_item["id"],
        "name": canon_item["name"],
        "primary_version_id": primary_id,
        "image": v.get("image"),
        "glass": v.get("glass"),
        "tags": v.get("tags", []),
        # Raw measures preserved
        "ingredients": v.get("ingredients", []),
        "instructions": v.get("instructions") or "",
        "attribution": v.get("attribution", {}),  # source_name, source_url, fetched_at
        # Link out to see other versions if you want a “compare” UI
        "version_count": len(canon_item.get("versions", []))
    }
    return compact, v

def build_pack(canonical_path: str, source_jsonls: List[str]) -> dict:
    canonical = load_canonical(canonical_path)
    versions = load_versions(source_jsonls)

    compact_list: List[dict] = []
    version_index: Dict[str, dict] = {}
    ingredient_index: Dict[str, dict] = {}

    for c in canonical:
        compact, primary_v = _flatten_primary(c, versions)
        if not compact:
            continue
        compact_list.append(compact)

        # add all versions for this cocktail to version_index (for detail pages)
        for vid in c.get("versions", []):
            if vid in versions:
                version_index[vid] = versions[vid]

        # build a simple ingredient index (id -> {name})
        for ing in (primary_v.get("ingredients") or []):
            iid = ing.get("id")
            name = ing.get("name")
            if iid and iid not in ingredient_index:
                ingredient_index[iid] = {"id": iid, "name": name}

    manifest = {
        "name": "Cocktail Pack",
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "counts": {
            "cocktails": len(compact_list),
            "versions": len(version_index),
            "ingredients": len(ingredient_index),
        }
    }

    return {
        "manifest": manifest,
        "cocktails": compact_list,
        "versions": version_index,     # optional for detail/compare screens
        "ingredients": ingredient_index
    }

def write_pack(pack: dict, outdir: str, split: bool = True):
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)  # noqa: E702
    # Always write a manifest
    (out / "manifest.json").write_text(json.dumps(pack["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")

    if split:
        (out / "cocktails.json").write_text(json.dumps(pack["cocktails"], ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "versions.json").write_text(json.dumps(pack["versions"], ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "ingredients.json").write_text(json.dumps(pack["ingredients"], ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        (out / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
