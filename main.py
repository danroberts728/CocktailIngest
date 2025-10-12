
import argparse
import json
import glob
import sys
from pathlib import Path
from typing import List
from app.models import RecipeVersion
from scrapers.base import get_scraper  # registry wired by imports below
from pipeline.dedupe import merge_to_canonical
from pipeline.export_pack import build_pack, write_pack

import scrapers.iba # noqa: F401
import scrapers.cocktaildb #noqa: F401

def write_jsonl(path: Path, objs):
    with path.open("w", encoding="utf-8") as f:
        for o in objs:
            f.write(json.dumps(o.to_dict(), ensure_ascii=False) + "\n")

def _load_versions(paths: List[str]) -> List[RecipeVersion]:
    versions = []
    for p in paths:
        with Path(p).open("r", encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                versions.append(_dict_to_version(d))
    return versions

def _dict_to_version(d) -> RecipeVersion:
    from app.models import Ingredient, Attribution, RecipeVersion
    ingredients = [Ingredient(**ing) for ing in d.get("ingredients", [])]
    attribution = Attribution(**d["attribution"]) if d.get("attribution") else None
    return RecipeVersion(
        id=d["id"],
        name=d["name"],
        name_slug=d.get("name_slug") or d["id"].split("::")[-1],
        ingredients=ingredients,
        instructions=d.get("instructions") or "",
        glass=d.get("glass"),
        tags=d.get("tags", []),
        image=d.get("image"),
        garnish=d.get("garnish"),
        method=d.get("method"),
        attribution=attribution
    )

def cmd_scrape(args):
    outdir = Path("data/sources")
    outdir.mkdir(parents=True, exist_ok=True) 
    scraper = get_scraper(args.source, delay=args.delay)
    versions = list(scraper.iter_recipes())
    path = outdir / f"{args.source}.jsonl"
    write_jsonl(path, versions)
    print(f"Wrote {len(versions)} recipe versions -> {path}")

def cmd_merge(args):
    inputs = []
    for pattern in args.inputs:
        inputs.extend(glob.glob(pattern))
    if not inputs:
        print("No input files found.", file=sys.stderr)
        sys.exit(2)
    versions = _load_versions(inputs)
    canon = merge_to_canonical(versions)
    Path("data").mkdir(exist_ok=True, parents=True)
    out = Path("data/canonical.json")
    out.write_text(json.dumps([c.to_dict() for c in canon], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(canon)} canonical cocktails -> {out}")

def cmd_validate(args):
    p = Path(args.file)
    d = json.loads(p.read_text(encoding="utf-8"))
    ids = set()
    for c in d:
        if not c["id"] or not c["name"] or not c.get("versions"):
            raise SystemExit("Invalid canonical entry found.")
        if c["id"] in ids:
            raise SystemExit(f"Duplicate canonical id: {c['id']}")
        ids.add(c["id"])
    print(f"OK: {len(d)} canonical cocktails in {p}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("scrape", help="Scrape a source and write JSONL")
    sp.add_argument("--source", required=True, help="e.g., iba")
    sp.add_argument("--delay", type=float, default=0.6)
    sp.set_defaults(func=cmd_scrape)

    mp = sub.add_parser("merge", help="Merge JSONL sources into canonical.json")
    mp.add_argument("--inputs", nargs="+", required=True, help="Glob(s) for jsonl files")
    mp.set_defaults(func=cmd_merge)

    vp = sub.add_parser("validate", help="Validate a canonical.json")
    vp.add_argument("--file", required=True)
    vp.set_defaults(func=cmd_validate)

    pp = sub.add_parser("pack", help="Build web-consumable JSON pack")
    pp.add_argument("--canonical", default="data/canonical.json")
    pp.add_argument("--inputs", nargs="+", default=["data/sources/iba.jsonl","data/sources/cocktaildb.jsonl"])
    pp.add_argument("--outdir", default="build")
    pp.add_argument("--bundle", action="store_true", help="write single pack.json instead of split files")
    def cmd_pack(args):
        pack = build_pack(args.canonical, args.inputs)
        write_pack(pack, args.outdir, split=not args.bundle)
        print(f"Packed -> {args.outdir}")
    pp.set_defaults(func=cmd_pack)

    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
