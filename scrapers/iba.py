
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin, urlparse
from typing import Iterator, List
from app.models import RecipeVersion, Ingredient, Attribution
from scrapers.base import SourceScraper, register_source
from utils.text import slugify, normalize_whitespace, looks_like_ingredient, split_measure_ingredient

BASE = "https://iba-world.com/"
ALL_URL = urljoin(BASE, "cocktails/all-cocktails/")
HEADERS = {"User-Agent": "CocktailIngest/1.0 (+for personal noncommercial use)"}

@register_source("iba")
class IBAScraper(SourceScraper):
    def __init__(self, delay: float = 0.6):
        self.delay = delay
        self.session = requests.Session()

    def fetch(self, url: str):
        r = self.session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    def _parse_all(self, html: str, links=None, pages_parsed =None) -> List[str]:
        if links is None:
            links = set()
        if pages_parsed is None:
            pages_parsed = set()

        soup = BeautifulSoup(html, "html.parser")

        for a in soup.select("a"):
            href = a.get("href", "")
            if not href:
                continue

            full = urljoin(BASE, href)  # normalize relative URLs
            path = urlparse(full).path.rstrip("/")
            parts = path.split("/")

            # Collect recipe links
            if "/iba-cocktail/" in full:
                if len(parts) >= 3 and parts[1] == "iba-cocktail":
                    links.add(full)

            # Follow pagination
            elif "/page/" in path:
                # pull page number to avoid loops
                try:
                    page_num = path.split("/page/")[1].split("/")[0]
                except IndexError:
                    page_num = None
                if page_num and page_num not in pages_parsed:
                    pages_parsed.add(page_num)
                    next_html = self.fetch(full)            # <-- key fix: fetch HTML here
                    self._parse_all(next_html, links, pages_parsed)

        return links  # caller can do: sorted(self._parse_all(...))

    def _parse_recipe(self, url: str, html: str) -> RecipeVersion:
        soup = BeautifulSoup(html, "html.parser")

        title = soup.find(["h1","h2"])
        name = title.get_text(strip=True) if title else "Unknown IBA Cocktail"
        name_slug = slugify(name)

        img = soup.find("img")
        image = img["src"] if img and img.get("src") else None
        if image and image.startswith("//"):
            image = "https:" + image
        if image and image.startswith("/"):
            image = urljoin(BASE, image)

        ingredients = []
        hdr = None
        for tag in soup.find_all(["h2","h3","h4","h5","h6"]):
            if "ingredient" in tag.get_text(strip=True).lower():
                hdr = tag
                break
        if hdr:
            lst = hdr.find_next(["ul","ol"])
            if lst:
                for li in lst.find_all("li"):
                    line = normalize_whitespace(li.get_text(" ", strip=True))
                    if not line:
                        continue
                    m, n = split_measure_ingredient(line)
                    ingredients.append(Ingredient(id=slugify(n), name=n, measure=m))
        if not ingredients:
            for li in soup.select("li"):
                line = normalize_whitespace(li.get_text(' ', strip=True))
                if looks_like_ingredient(line):
                    m, n = split_measure_ingredient(line)
                    ingredients.append(Ingredient(id=slugify(n), name=n, measure=m))

        seen = set(); uniq = []
        for ing in ingredients:
            key = (ing.id, ing.measure or "")
            if key in seen: continue
            seen.add(key); uniq.append(ing)
        ingredients = uniq

        instructions = ""
        for tag in soup.find_all(["h2","h3","h4","h5","h6"]):
            if any(k in tag.get_text(strip=True).lower() for k in ["method","directions","instructions","preparation"]):
                parts = []
                for sib in tag.find_all_next():
                    if sib.name and sib.name.lower() in ["h1","h2","h3","h4","h5","h6"]:
                        break
                    if sib.name in ("p","div"):
                        t = sib.get_text(" ", strip=True); 
                        if t: parts.append(t)
                    if sib.name in ("ul","ol"):
                        for li in sib.find_all("li"):
                            t = li.get_text(" ", strip=True)
                            if t: parts.append(t)
                instructions = "\\n".join(parts).strip()
                break
        if not instructions:
            p = soup.find("p")
            if p:
                instructions = p.get_text(" ", strip=True)

        glass = None
        for tag in soup.find_all(["p","li","span"]):
            t = tag.get_text(" ", strip=True).lower()
            if "glass" in t and len(t) < 120:
                glass = t
                break

        tags = []
        for a in soup.select("a[rel='tag'], a[href*='/category/']"):
            t = a.get_text(strip=True)
            if t:
                tags.append(t)

        garnish = None
        for tag in soup.find_all(["p","li"]):
            t = tag.get_text(" ", strip=True)
            if "garnish" in t.lower():
                garnish = t
                break

        rv = RecipeVersion(
            id=f"iba::{name_slug}",
            name=name,
            name_slug=name_slug,
            ingredients=ingredients,
            instructions=instructions,
            glass=glass,
            tags=tags,
            image=image,
            garnish=garnish,
            method=None,
            attribution=Attribution(
                source_name="IBA (iba-world.com)",
                source_url=url,
                fetched_at=datetime.utcnow().isoformat(timespec="seconds")+"Z"
            )
        )
        return rv

    def iter_recipes(self):
        index_html = self.fetch(ALL_URL)
        urls = self._parse_all(index_html)
        for u in urls:
            try:
                html = self.fetch(u)
                yield self._parse_recipe(u, html)
            except Exception:
                continue
