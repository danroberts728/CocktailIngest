from datetime import datetime
import time
import json
import requests
import urllib.request
from utils import text
from app import models
from scrapers.base import SourceScraper, register_source


BASE = "https://www.thecocktaildb.com/api/json/v1/1/"
LOOKUP_URL = BASE + "lookup.php?i="
HEADERS = {"User-Agent": "CocktailIngest/1.0 (+for personal noncommercial use)"}


@register_source("cocktaildb")
class CocktailDbScraper(SourceScraper):
    def __init__(self, delay: float = 0.1):
        self.delay = delay
        self.session = requests.Session()

    def fetch(self, url: str):
        r = self.session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    def _parse_recipe(self, drink):
        recipeVersion = models.RecipeVersion(
            id=f"cocktaildb:{text.slugify(drink['strDrink'])}",
            name=drink["strDrink"],
            name_slug=text.slugify(drink["strDrink"]),
            ingredients=[
                models.Ingredient(
                    id=text.slugify(text.replace_text_by_rule(drink[f"strIngredient{i}"])),
                    name=text.replace_text_by_rule(drink[f"strIngredient{i}"]),
                    measure=text.replace_text_by_rule(drink[f"strMeasure{i}"]),
                )
                for i in range(1, 16)
                if drink.get(f"strIngredient{i}")
            ],
            instructions=drink["strInstructions"],
            glass=drink["strGlass"],
            tags=[],
            image=drink["strDrinkThumb"],
            garnish=None,
            method=None,
            attribution=models.Attribution(
                source_name="CocktailDb (thecocktaildb.com)",
                source_url=f"https://thecocktaildb.com/drink/{drink['idDrink']}-{text.slugify(drink['strDrink'])}",
                fetched_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            ),
        )
        return recipeVersion
    
    def _get_filters(self, kind, property):
        url = BASE + f"list.php?{kind}=list"
        data = requests.get(url, timeout=20).json()
        return [d[property] for d in data.get("drinks", []) if d.get(property)]
    
    def _get_drink_ids(self, kind: str, value: str):
        url = BASE + f"filter.php?{kind}={value.replace(' ', '+')}"
        data = requests.get(url, timeout=20).json()
        return [d["idDrink"] for d in data.get("drinks", []) if d.get("idDrink")]

    def iter_recipes(self):
        drinkIds = set()

        # This dataset has a lot of not-really-cocktail drinks, so
        # we're goign to limit this drinks with known liquor ingredients
        ingredients = self._get_filters('i', 'strIngredient1')
        allowed_ingredient_substr = [
            'rum', 'bourbon', 'vodka', 'gin', 'whiskey', 'tequila', 'brandy', 'southern comfort',
            'amaretto', 'scotch', 'cognac', 'johnnie walker', 'everclear', 'absolut', 'jack daniels'
        ]
        filtered_ingredients = [i for i in ingredients if any(s in i.lower() for s in allowed_ingredient_substr)]
        for i in filtered_ingredients:
            drinkIds.update(self._get_drink_ids('i', i))


        all_urls = [
            f"{LOOKUP_URL}{str(id)}" for id in drinkIds
        ]
        for url in all_urls:
            with urllib.request.urlopen(url) as page:
                data = json.load(page)
                if data["drinks"] is None:
                    continue
                for drink in data["drinks"]:
                    try:
                        yield self._parse_recipe(drink)
                    except Exception as e:
                        print(e)
                        continue
