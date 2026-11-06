"""eBay Canada category list (top level and second level), loaded from data/ebay_categories_ca.txt.

An item's category is stored as a path string: "<Top level> > <Second level>",
e.g. "Computers/Tablets & Networking > Laptops & Netbooks". The path is unique even
when a second-level name (like "Wholesale Lots") appears under several top levels.
"""
import os

SEPARATOR = ' > '
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'ebay_categories_ca.txt')


def _load(path):
    tree = []
    with open(path, encoding='utf-8') as f:
        for line_no, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            kind, name, cat_id = (part.strip() for part in line.split('|'))
            if kind == 'TOP':
                tree.append({'name': name, 'id': cat_id, 'subs': []})
            elif kind == 'SUB' and tree:
                tree[-1]['subs'].append({
                    'name': name,
                    'id': cat_id,
                    'path': f"{tree[-1]['name']}{SEPARATOR}{name}",
                })
            else:
                raise ValueError(f"{path}:{line_no}: unexpected line {line!r}")
    # Show top levels alphabetically (as eBay's listing form does); keep subs in page order sorted too
    tree.sort(key=lambda t: t['name'].lower())
    for top in tree:
        top['subs'].sort(key=lambda s: s['name'].lower())
    return tree


EBAY_CATEGORY_TREE = _load(DATA_FILE)

# Full path -> eBay category ID (second level)
CATEGORY_IDS = {sub['path']: sub['id'] for top in EBAY_CATEGORY_TREE for sub in top['subs']}
# Top-level name -> eBay category ID
TOP_LEVEL_IDS = {top['name']: top['id'] for top in EBAY_CATEGORY_TREE}
TOP_LEVEL_NAMES = [top['name'] for top in EBAY_CATEGORY_TREE]


def is_valid_category(path):
    return path in CATEGORY_IDS


def top_level(category):
    """Top-level part of a category path ("A > B" -> "A"). Old-style categories are returned as-is."""
    if not category:
        return None
    return category.split(SEPARATOR, 1)[0]


def ebay_category_id(category):
    return CATEGORY_IDS.get(category) if category else None
