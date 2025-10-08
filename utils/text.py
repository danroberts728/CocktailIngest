import json
import re
import unicodedata

def slugify(s: str) -> str:
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    return s

def normalize_whitespace(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()

def looks_like_ingredient(line: str) -> bool:
    units = ['oz', 'ml', 'cl', 'dash', 'dashes', 'drops', 'barspoon', 'tsp', 'teaspoon', 'teaspoons', 'cube', 'slice', 'wheel']
    keywords = ['syrup','juice','bitters','vermouth','liqueur','gin','rum','tequila','whiskey','vodka',
                'brandy','cognac','wine','beer','soda','sparkling','salt','sugar','cream','egg','ginger',
                'campari','cointreau','curacao','maraschino','chartreuse','agave','honey']
    line_lower = line.lower()
    return any(u in line_lower for u in units) or any(k in line_lower for k in keywords)

def split_measure_ingredient(line: str):
    tokens = line.split()
    if not tokens:
        return None, line.strip()

    joiners = set(['oz','ml','cl','dash','dashes','barspoon','barspoons','tablespoon','tablespoons',
                   'tsp','teaspoon','teaspoons','pcs','drops','splash'])

    if (
        any(
            t.replace('/', '').replace('.', '').isdigit() or
            re.fullmatch(r'\d+\s*-\s*\d+', t)
            for t in tokens[:2]
        )
        or any(t.lower() in joiners for t in tokens[:3])
    ):
        measure = []
        i = 0
        while i < len(tokens) and (
            tokens[i].replace('/', '').replace('.', '').isdigit()
            or re.fullmatch(r'\d+\s*-\s*\d+', tokens[i])
            or tokens[i].lower() in joiners
        ):
            measure.append(tokens[i])
            i += 1

        if i < len(tokens) and tokens[i].lower() in joiners:
            measure.append(tokens[i])
            i += 1

        return ' '.join(measure), ' '.join(tokens[i:]).strip()

    return None, line.strip()

def replace_text_by_rule(line: str) -> str:
    # Hard-coded path to the substitutions file
    SUBS_PATH = "./utils/substitutes.json"

    # Load substitutions
    with open(SUBS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Allow for a list with one dict or a plain dict
    if isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
        data = data[0]
    elif not isinstance(data, dict):
        raise ValueError("substitutes.json must be a dict or a list with one dict")

    # Sort keys so longer patterns replace first
    keys = sorted(data.keys(), key=len, reverse=True)

    out = line
    for key in keys:
        val = data[key]
        # Regex key: starts and ends with /
        if isinstance(key, str) and key.startswith("/") and key.endswith("/"):
            pattern = key[1:-1]
            out = re.sub(pattern, val, out, flags=re.IGNORECASE)
        else:
            out = re.sub(re.escape(key), val, out, flags=re.IGNORECASE)

    return out