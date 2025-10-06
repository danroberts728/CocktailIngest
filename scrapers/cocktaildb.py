
import time, re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Tuple, Set

from app.models import RecipeVersion, Ingredient, Attribution
from scrapers.base import SourceScraper, register_source
from utils.text import slugify, normalize_whitespace

BASE = "https://www.thecocktaildb.com/"
BROWSE_LETTER = urljoin(BASE, "browse/letter/")
API_LOOKUP = urljoin(BASE, "api/json/v1/1/lookup.php?i=")

HEADERS = {"User-Agent": "CocktailIngest/1.0 (+personal noncommercial use)"}

@register_source("cocktaildb")
class CocktailDBScraper(SourceScraper):
    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.session = requests.Session()

    def fetch(self, url: str) -> str:
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"fetch() expected URL, got: {repr(url)[:80]}")
        r = self.session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    def fetch_json(self, url: str) -> dict:
        r = self.session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.json()

    def _collect_letter_pages(self, letter: str) -> List[str]:
        start = urljoin(BROWSE_LETTER, letter)
        to_visit = [start]
        seen = {start}
        pages = []

        base_netloc = urlparse(BASE).netloc
        prefix = f"/browse/letter/{letter}"

        while to_visit:
            url = to_visit.pop(0)
            pages.append(url)
            html = self.fetch(url)
            soup = BeautifulSoup(html, "html.parser")

            for a in soup.select("a.page-numbers, nav.pagination a, a[rel='next'], a[href*='/browse/letter/']"):
                href = a.get("href")
                if not href:
                    continue
                pg = urljoin(BASE, href).split("#", 1)[0]
                pu = urlparse(pg)
                if pu.netloc != base_netloc:
                    continue
                if not pu.path.startswith(prefix):
                    continue
                if pg not in seen:
                    seen.add(pg)
                    to_visit.append(pg)
        return pages

    def _collect_drink_ids(self, page_url: str) -> List[Tuple[str, str]]:
        html = self.fetch(page_url)
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.select("a[href*='/drink/']"):
            href = a.get("href")
            if not href:
                continue
            full = urljoin(BASE, href)
            m = re.search(r"/drink/(\d+)", full)
            if m:
                out.append((m.group(1), full))
        return out

    def _api_to_version(self, drink: dict, page_url: str) -> RecipeVersion:
        ingredients = []
        for i in range(1, 16):
            ing = drink.get(f"strIngredient{i}")
            meas = drink.get(f"strMeasure{i}")
            if not ing:
                continue
            name = normalize_whitespace(ing)
            measure = normalize_whitespace(meas) if meas else None
            ingredients.append(Ingredient(id=slugify(name), name=name, measure=measure))

        name = drink.get("strDrink") or "Unknown Cocktail"
        name_slug = slugify(name)
        return RecipeVersion(
            id=f"cocktaildb::{drink.get('idDrink')}",
            name=name,
            name_slug=name_slug,
            ingredients=ingredients,
            instructions=(drink.get("strInstructions") or "").strip(),
            glass=drink.get("strGlass"),
            tags=[t.strip() for t in (drink.get("strTags") or "").split(",") if t and t.strip()],
            image=drink.get("strDrinkThumb"),
            garnish=None,
            method=None,
            attribution=Attribution(
                source_name="TheCocktailDB",
                source_url=page_url or (BASE + f"drink/{drink.get('idDrink')}"),
                fetched_at=datetime.utcnow().isoformat(timespec="seconds")+"Z"
            )
        )

    def iter_recipes(self):
        letters = [chr(c) for c in range(ord('a'), ord('z')+1)] + ["0-9"]
        seen_ids: Set[str] = set()

        for letter in letters:
            try:
                pages = self._collect_letter_pages(letter)
            except Exception:
                continue

            for pg in pages:
                try:
                    id_and_urls = self._collect_drink_ids(pg)
                except Exception:
                    continue

                for drink_id, page_url in id_and_urls:
                    if drink_id in seen_ids:
                        continue
                    seen_ids.add(drink_id)
                    try:
                        data = self.fetch_json(API_LOOKUP + drink_id)
                        drinks = data.get("drinks") or []
                        if not drinks:
                            continue
                        yield self._api_to_version(drinks[0], page_url)
                    except Exception:
                        continue
