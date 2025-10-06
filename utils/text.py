
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
    units = ['oz', 'ml', 'cl', 'dash', 'dashes', 'barspoon', 'tsp', 'teaspoon', 'cube', 'slice', 'wheel']
    keywords = ['syrup','juice','bitters','vermouth','liqueur','gin','rum','tequila','whiskey','vodka',
                'brandy','cognac','wine','beer','soda','sparkling','salt','sugar','cream','egg','ginger',
                'campari','cointreau','curacao','maraschino','chartreuse','agave','honey']
    l = line.lower()
    return any(u in l for u in units) or any(k in l for k in keywords)

def split_measure_ingredient(line: str):
    tokens = line.split()
    if not tokens:
        return None, line.strip()
    joiners = set(['oz','ml','cl','dash','dashes','barspoon','tsp','teaspoon'])
    if any(t.replace('/', '').replace('.', '').isdigit() for t in tokens[:2]) or any(t.lower() in joiners for t in tokens[:3]):
        measure = []
        i = 0
        while i < len(tokens) and (tokens[i].replace('/', '').replace('.', '').isdigit() or tokens[i].lower() in joiners):
            measure.append(tokens[i]); i += 1
        if i < len(tokens) and tokens[i].lower() in joiners:
            measure.append(tokens[i]); i += 1
        return ' '.join(measure), ' '.join(tokens[i:]).strip()
    return None, line.strip()
