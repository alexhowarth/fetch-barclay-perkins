#!/usr/bin/env python3
"""fetch-barclay-perkins.py - Convert Barclay Perkins blog recipes to BeerXML format.

Fetches recipes from barclayperkins.blogspot.com and generates BeerXML 1.0 files.

Usage:
    python3 fetch-barclay-perkins.py --limit 5                            # Test with 5 recipes
    python3 fetch-barclay-perkins.py --notes full                          # Full export with blog text
    python3 fetch-barclay-perkins.py --experimental-hop-adjustment         # Also generate era-adjusted alpha set
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from xml.sax.saxutils import escape as xml_escape

# ─── Constants ───────────────────────────────────────────────────────────────

FEED_BASE = "https://barclayperkins.blogspot.com/feeds/posts/default/-/beer%20recipes"
FEED_PAGE_SIZE = 150

BATCH_SIZE_L = 22.7124707
TRUB_LOSS_L = 3.7854118
EVAP_RATE_L_PER_HR = 5.338  # derived from pattinson.xml 60-min equipment
POST_BOIL_L = BATCH_SIZE_L + TRUB_LOSS_L  # 26.50 L
EFFICIENCY = 72.0
COOLING_LOSS_PCT = 4.0

# Equipment profile (from pattinson.xml)
EQUIPMENT = {
    'name': 'Pot and Cooler (10 Gal/37.8 L) - All Grain',
    'tun_volume': 37.8541178,
    'tun_weight': 4.0823280,
    'tun_specific_heat': 0.3,
    'top_up_water': 0.0,
    'trub_chiller_loss': TRUB_LOSS_L,
    'lauter_deadspace': 3.0283294,
    'top_up_kettle': 0.0,
    'hop_utilization': 100.0,
    'cooling_loss_pct': COOLING_LOSS_PCT,
}

# Mash defaults (from pattinson.xml + BeerSmith profile)
MASH_DEFAULTS = {
    'name': 'Single Infusion, Light Body, No Mash Out',
    'grain_temp': 22.2222222,
    'tun_temp': 22.2222222,
    'sparge_temp': 75.5555556,  # 168°F, overridden per-recipe
    'ph': 5.4,
    'tun_weight': 144.0,
    'tun_specific_heat': 0.3,
    'step_time': 75.0,
    'step_type': 'Infusion',
    'ramp_time': 2.0,
    'step_temp': 65.5555556,  # 150°F, overridden per-recipe
    'water_grain_ratio_qt_lb': 1.25,
}

# Fermentation defaults (from pattinson.xml)
FERM_DEFAULTS = {
    'stages': 2,
    'primary_age': 4.0,
    'primary_temp': 19.4444444,
    'secondary_age': 10.0,
    'secondary_temp': 19.4444444,
    'carbonation': 2.3,
}

# ─── Alpha Acid Databases ────────────────────────────────────────────────────

# BeerSmith defaults from https://beersmith.com/hop-list/
BEERSMITH_ALPHAS = {
    'Fuggles': 4.5, 'Goldings': 5.0, 'Cluster': 7.0,
    'Hallertau': 4.8, 'Hallertau Mittelfruh': 4.0,
    'Saaz': 4.0, 'Strisselspalt': 4.0,
    'Styrian Goldings': 5.4, 'Northern Brewer': 8.5,
    'Bramling Cross': 6.0, "Brewer's Gold": 8.0,
    'WGV': 6.0, 'Target': 11.0, 'Challenger': 7.5,
    'Northdown': 8.5, 'Spalt': 4.5, 'Lublin': 5.0,
    'Progress': 6.3, 'Bullion': 8.0,
    'Poperinge': 5.0, 'Alsace': 3.5,
}

# Historical alphas by era (from Brewers' Society data, Ron's blog)
HISTORICAL_ALPHAS = {
    'Fuggles':          {'pre1940': 5.5, '1940s': 5.0, '1970s': 4.2, 'modern': 4.5},
    'Goldings':         {'pre1940': 6.0, '1940s': 5.5, '1970s': 4.8, 'modern': 5.0},
    'Cluster':          {'pre1940': 7.0, '1940s': 7.0, '1970s': 7.0, 'modern': 7.0},
    'Hallertau':        {'pre1940': 4.0, '1940s': 4.0, '1970s': 4.0, 'modern': 4.0},
    'Hallertau Mittelfruh': {'pre1940': 4.0, '1940s': 4.0, '1970s': 4.0, 'modern': 4.0},
    'Saaz':             {'pre1940': 3.5, '1940s': 3.5, '1970s': 3.5, 'modern': 3.75},
    'Strisselspalt':    {'pre1940': 3.5, '1940s': 3.5, '1970s': 3.5, 'modern': 3.5},
    'Styrian Goldings': {'pre1940': 5.0, '1940s': 5.0, '1970s': 5.0, 'modern': 5.25},
    'Northern Brewer':  {'pre1940': 8.0, '1940s': 8.0, '1970s': 7.0, 'modern': 8.0},
    'Bramling Cross':   {'pre1940': 6.0, '1940s': 6.0, '1970s': 5.5, 'modern': 6.5},
    "Brewer's Gold":    {'pre1940': 8.0, '1940s': 8.0, '1970s': 7.5, 'modern': 8.5},
    'WGV':              {'pre1940': 5.5, '1940s': 5.5, '1970s': 5.3, 'modern': 6.0},
    'Target':           {'pre1940': None,'1940s': None,'1970s': 10.0,'modern': 11.0},
    'Challenger':       {'pre1940': None,'1940s': None,'1970s': 7.2, 'modern': 7.5},
    'Northdown':        {'pre1940': None,'1940s': None,'1970s': 8.1, 'modern': 8.0},
    'Spalt':            {'pre1940': 4.5, '1940s': 4.5, '1970s': 4.5, 'modern': 4.5},
    'Lublin':           {'pre1940': 5.0, '1940s': 5.0, '1970s': 5.0, 'modern': 5.0},
    'Progress':         {'pre1940': 6.0, '1940s': 6.0, '1970s': 5.4, 'modern': 6.3},
    'Bullion':          {'pre1940': 7.0, '1940s': 7.0, '1970s': 7.5, 'modern': 8.0},
    'Poperinge':        {'pre1940': 5.5, '1940s': 5.0, '1970s': 5.0, 'modern': 5.0},
    'Alsace':           {'pre1940': 3.5, '1940s': 3.5, '1970s': 3.5, 'modern': 3.5},
}

# ─── Fermentable Database ────────────────────────────────────────────────────
# (keyword_pattern, name, type, yield%, color_SRM, origin)

FERMENTABLE_DB = [
    # Base malts
    (r'pale\s*malt|pale\s*ale\s*malt', 'Pale Malt (2 Row) UK', 'Grain', 78.0, 3.0, 'United Kingdom'),
    (r'lager\s*malt', 'Lager Malt', 'Grain', 80.0, 2.0, 'Germany'),
    (r'mild\s*malt', 'Mild Malt', 'Grain', 75.0, 4.0, 'United Kingdom'),
    (r'maris\s*otter', 'Maris Otter Pale Malt', 'Grain', 78.0, 3.0, 'United Kingdom'),
    (r'pilsner\s*malt|pilsener', 'Pilsner Malt', 'Grain', 81.0, 2.0, 'Germany'),
    (r'vienna\s*malt', 'Vienna Malt', 'Grain', 78.0, 4.0, 'Germany'),
    (r'munich\s*malt', 'Munich Malt', 'Grain', 77.0, 9.0, 'Germany'),
    (r'wheat\s*malt', 'Wheat Malt', 'Grain', 80.0, 2.0, 'Germany'),
    (r'oat\s*malt', 'Oat Malt', 'Grain', 70.0, 3.0, 'United Kingdom'),
    (r'rye\s*malt', 'Rye Malt', 'Grain', 75.0, 4.0, 'Germany'),
    # Specialty malts
    (r'amber\s*malt', 'Amber Malt', 'Grain', 70.0, 22.0, 'United Kingdom'),
    (r'brown\s*malt', 'Brown Malt', 'Grain', 70.0, 65.0, 'United Kingdom'),
    (r'chocolate\s*malt', 'Chocolate Malt', 'Grain', 60.0, 350.0, 'United Kingdom'),
    (r'black\s*(patent|malt)', 'Black Patent Malt', 'Grain', 55.0, 500.0, 'United Kingdom'),
    (r'roast(ed)?\s*barley', 'Roasted Barley', 'Grain', 55.0, 300.0, 'United Kingdom'),
    (r'crystal\s*malt|caramalt', 'Crystal Malt', 'Grain', 75.0, 60.0, 'United Kingdom'),
    (r'cara-?pils|carapils', 'CaraPils/Dextrine', 'Grain', 72.0, 2.0, 'United Kingdom'),
    (r'Special\s*B', 'Special B Malt', 'Grain', 68.0, 180.0, 'Belgium'),
    (r'biscuit', 'Biscuit Malt', 'Grain', 75.0, 23.0, 'Belgium'),
    (r'aromatic', 'Aromatic Malt', 'Grain', 72.0, 26.0, 'Belgium'),
    (r'acid\s*malt', 'Acid Malt', 'Grain', 72.0, 3.0, 'Germany'),
    (r'smoked\s*malt|rauch', 'Smoked Malt', 'Grain', 77.0, 2.0, 'Germany'),
    (r'peat(ed)?\s*malt', 'Peated Malt', 'Grain', 77.0, 3.0, 'United Kingdom'),
    # Adjuncts
    (r'flaked\s*barley', 'Flaked Barley', 'Adjunct', 70.0, 2.0, 'United Kingdom'),
    (r'flaked\s*maize|flaked\s*corn', 'Flaked Maize', 'Adjunct', 80.0, 1.0, 'US'),
    (r'flaked\s*oats', 'Flaked Oats', 'Adjunct', 70.0, 1.0, 'United Kingdom'),
    (r'flaked\s*rice', 'Flaked Rice', 'Adjunct', 80.0, 1.0, 'US'),
    (r'flaked\s*wheat', 'Flaked Wheat', 'Adjunct', 77.0, 2.0, 'United Kingdom'),
    (r'torrified\s*wheat|torrefied\s*wheat', 'Torrified Wheat', 'Adjunct', 77.0, 2.0, 'United Kingdom'),
    (r'torrified\s*barley|torrefied\s*barley', 'Torrified Barley', 'Adjunct', 70.0, 2.0, 'United Kingdom'),
    (r'rice\s*grits', 'Rice Grits', 'Adjunct', 80.0, 1.0, 'US'),
    (r'corn\s*grits|maize\s*grits', 'Corn Grits', 'Adjunct', 80.0, 1.0, 'US'),
    # Sugars (check No. X invert before generic invert)
    (r'No\.?\s*1\s*invert|invert\s*No\.?\s*1', 'No. 1 Invert Sugar', 'Sugar', 100.0, 1.0, 'United Kingdom'),
    (r'No\.?\s*2\s*invert|invert\s*No\.?\s*2', 'No. 2 Invert Sugar', 'Sugar', 100.0, 30.0, 'United Kingdom'),
    (r'No\.?\s*3\s*invert|invert\s*No\.?\s*3', 'No. 3 Invert Sugar', 'Sugar', 100.0, 75.0, 'United Kingdom'),
    (r'No\.?\s*4\s*invert|invert\s*No\.?\s*4', 'No. 4 Invert Sugar', 'Sugar', 100.0, 150.0, 'United Kingdom'),
    (r'invert\s*sugar|invert', 'Invert Sugar', 'Sugar', 100.0, 30.0, 'United Kingdom'),
    (r'glucose|dextrose|corn\s*sugar', 'Glucose (Dextrose)', 'Sugar', 100.0, 0.0, 'US'),
    (r'golden\s*syrup', 'Golden Syrup', 'Sugar', 95.0, 3.0, 'United Kingdom'),
    (r'treacle', 'Treacle', 'Sugar', 95.0, 50.0, 'United Kingdom'),
    (r'molasses', 'Molasses', 'Sugar', 80.0, 80.0, 'United Kingdom'),
    (r'honey', 'Honey', 'Sugar', 95.0, 5.0, 'United Kingdom'),
    (r'lyle', 'Lyle\'s Golden Syrup', 'Sugar', 95.0, 3.0, 'United Kingdom'),
    (r'lactose|milk\s*sugar', 'Lactose', 'Sugar', 100.0, 0.0, 'United Kingdom'),
    (r'sucrose|cane\s*sugar|white\s*sugar|table\s*sugar', 'Cane Sugar', 'Sugar', 100.0, 0.0, 'United Kingdom'),
    (r'sugar', 'Sugar', 'Sugar', 100.0, 0.0, 'United Kingdom'),
    # Caramel colouring (handle "caramel XXXX SRM" pattern)
    (r'caramel', 'Caramel Colouring', 'Sugar', 100.0, 2000.0, 'United Kingdom'),
]

# ─── Hop Name Normalisation ──────────────────────────────────────────────────

def normalise_hop(raw_name):
    """Normalise blog hop name. Returns (canonical_name, embedded_alpha_or_None)."""
    s = raw_name.strip()
    s = re.sub(r'\s+s$', '', s)  # strip trailing ' s' artifact

    # Extract embedded alpha if present (e.g. "Goldings 5.5%")
    alpha_match = re.search(r'(\d+\.?\d*)\s*%', s)
    embedded_alpha = float(alpha_match.group(1)) if alpha_match else None
    if alpha_match:
        s = s[:alpha_match.start()].strip()

    # Strip IBU annotations like "31bu" or "6bu"
    s = re.sub(r'\d+\s*bu\b', '', s, flags=re.IGNORECASE).strip()

    s_lower = s.lower()
    if 'fuggle' in s_lower:
        return 'Fuggles', embedded_alpha
    if 'styrian' in s_lower and 'golding' in s_lower:
        return 'Styrian Goldings', embedded_alpha
    if 'golding' in s_lower:
        return 'Goldings', embedded_alpha
    if 'cluster' in s_lower:
        return 'Cluster', embedded_alpha
    if 'hallertau' in s_lower and ('mittel' in s_lower or 'früh' in s_lower or 'fruh' in s_lower):
        return 'Hallertau Mittelfruh', embedded_alpha
    if 'hallertau' in s_lower:
        return 'Hallertau', embedded_alpha
    if 'saaz' in s_lower:
        return 'Saaz', embedded_alpha
    if 'stris' in s_lower:
        return 'Strisselspalt', embedded_alpha
    if 'northern' in s_lower and 'brewer' in s_lower:
        return 'Northern Brewer', embedded_alpha
    if 'bramling' in s_lower:
        return 'Bramling Cross', embedded_alpha
    if 'brewer' in s_lower and 'gold' in s_lower:
        return "Brewer's Gold", embedded_alpha
    if 'wgv' in s_lower or 'whitbread' in s_lower:
        return 'WGV', embedded_alpha
    if 'target' in s_lower:
        return 'Target', embedded_alpha
    if 'challenger' in s_lower:
        return 'Challenger', embedded_alpha
    if 'northdown' in s_lower:
        return 'Northdown', embedded_alpha
    if 'spalt' in s_lower:
        return 'Spalt', embedded_alpha
    if 'lublin' in s_lower:
        return 'Lublin', embedded_alpha
    if 'progress' in s_lower:
        return 'Progress', embedded_alpha
    if 'bullion' in s_lower:
        return 'Bullion', embedded_alpha
    if 'poperinge' in s_lower or 'alsace' in s_lower:
        return s.strip(), embedded_alpha
    return s.strip() or raw_name.strip(), embedded_alpha


def get_era(year):
    if year < 1940: return 'pre1940'
    if year < 1970: return '1940s'
    if year < 1990: return '1970s'
    return 'modern'


def lookup_alpha(hop_name, year, embedded_alpha, mode):
    """Get alpha acid for hop. Returns (alpha, source_description).
    embedded_alpha always takes priority."""
    if embedded_alpha is not None:
        return embedded_alpha, 'blog'
    if mode == 'beersmith':
        if hop_name in BEERSMITH_ALPHAS:
            return BEERSMITH_ALPHAS[hop_name], 'BeerSmith default'
        return 5.0, 'fallback (unknown hop)'
    else:  # historical
        era = get_era(year)
        entry = HISTORICAL_ALPHAS.get(hop_name)
        if entry:
            val = entry.get(era)
            if val is not None:
                return val, f'historical ({era})'
            return entry.get('modern', 5.0), 'historical (modern fallback)'
        if hop_name in BEERSMITH_ALPHAS:
            return BEERSMITH_ALPHAS[hop_name], 'BeerSmith default (no historical data)'
        return 5.0, 'fallback (unknown hop)'

# ─── Fermentable Classification ──────────────────────────────────────────────

def classify_fermentable(raw_name):
    """Match raw grain name to fermentable DB entry.
    Returns dict with name, type, yield, color, origin."""
    clean = re.sub(r'\s+', ' ', raw_name).strip()

    # Handle "caramel XXXX SRM" pattern
    caramel_match = re.match(r'caramel\s+(\d+)\s*SRM', clean, re.IGNORECASE)
    if caramel_match:
        srm = float(caramel_match.group(1))
        return {
            'name': f'Caramel Colouring {int(srm)} SRM',
            'type': 'Sugar', 'yield': 100.0, 'color': srm,
            'origin': 'United Kingdom',
        }

    # Handle "crystal XXL" or "crystal XX" pattern
    crystal_match = re.match(r'crystal\s+(\d+)\s*L?', clean, re.IGNORECASE)
    if crystal_match:
        lovibond = float(crystal_match.group(1))
        return {
            'name': f'Crystal Malt {int(lovibond)}L',
            'type': 'Grain', 'yield': 75.0, 'color': lovibond,
            'origin': 'United Kingdom',
        }

    for pattern, name, ftype, fyield, color, origin in FERMENTABLE_DB:
        if re.search(pattern, clean, re.IGNORECASE):
            return {
                'name': name, 'type': ftype, 'yield': fyield,
                'color': color, 'origin': origin,
            }

    # Unknown fermentable — assume grain
    return {
        'name': f'UNKNOWN: {clean}', 'type': 'Grain', 'yield': 70.0,
        'color': 5.0, 'origin': 'United Kingdom',
        'assumed': True,
    }

# ─── HTML Parsers ────────────────────────────────────────────────────────────

class TableParser(HTMLParser):
    """Extract all tables from HTML as lists of rows."""
    def __init__(self):
        super().__init__()
        self.in_table = self.in_td = self.in_tr = False
        self.tables, self.current_table, self.current_row = [], [], []
        self.current_cell = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True; self.current_table = []
        elif tag == 'tr' and self.in_table:
            self.in_tr = True; self.current_row = []
        elif tag in ('td', 'th') and self.in_tr:
            self.in_td = True; self.current_cell = ''
        elif tag == 'br' and self.in_td:
            self.current_cell += ' '

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
            if self.current_table:
                self.tables.append(self.current_table)
        elif tag == 'tr' and self.in_table:
            self.in_tr = False
            if self.current_row:
                self.current_table.append(self.current_row)
        elif tag in ('td', 'th') and self.in_td:
            self.in_td = False
            self.current_row.append(self.current_cell.strip())

    def handle_data(self, data):
        if self.in_td:
            self.current_cell += data


class TextExtractor(HTMLParser):
    """Extract readable text from HTML, skipping tables."""
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_script = False
        self.parts = []
        self.current = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.in_table = True
        elif tag in ('script', 'style'):
            self.in_script = True
        elif tag in ('p', 'br', 'div', 'h1', 'h2', 'h3', 'h4', 'li'):
            if self.current.strip():
                self.parts.append(self.current.strip())
            self.current = ''

    def handle_endtag(self, tag):
        if tag == 'table':
            self.in_table = False
        elif tag in ('script', 'style'):
            self.in_script = False
        elif tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'li'):
            if self.current.strip():
                self.parts.append(self.current.strip())
            self.current = ''

    def handle_data(self, data):
        if not self.in_table and not self.in_script:
            self.current += data

    def get_text(self):
        if self.current.strip():
            self.parts.append(self.current.strip())
        return '\n\n'.join(self.parts)

# ─── Recipe Parsing ──────────────────────────────────────────────────────────

METADATA_LABELS = {
    'og', 'fg', 'abv', 'ibu', 'srm', 'mash at', 'sparge at',
    'boil time', 'pitching temp', 'yeast', 'apparent attenuation',
    'attenuation',
}


def is_metadata_row(c0_lower):
    return any(c0_lower.startswith(m) for m in METADATA_LABELS)


def parse_recipe_table(table):
    """Parse a blog recipe table into a structured dict.
    Returns None if the table doesn't look like a recipe."""
    title_row = None
    fermentables = []
    hops = []
    metadata = {}

    for row in table:
        # Title row: single cell
        if len(row) == 1:
            title_row = row[0].strip()
            continue

        if len(row) < 2:
            continue

        c0 = row[0].strip()
        c1 = row[1].strip()
        c2 = row[2].strip() if len(row) > 2 else ''
        c0_lower = c0.lower()

        # -- Metadata rows --
        if c0_lower.startswith('og'):
            metadata['og'] = c1; continue
        if c0_lower.startswith('fg'):
            metadata['fg'] = c1; continue
        if c0_lower.startswith('abv'):
            metadata['abv'] = c1; continue
        if c0_lower.startswith('ibu'):
            metadata['ibu'] = c1; continue
        if c0_lower.startswith('srm'):
            metadata['srm'] = c1; continue
        if c0_lower.startswith('mash at'):
            metadata['mash_temp'] = c1; continue
        if c0_lower.startswith('sparge at'):
            metadata['sparge_temp'] = c1; continue
        if c0_lower.startswith('boil time'):
            metadata['boil_time'] = c1; continue
        if c0_lower.startswith('pitching temp'):
            metadata['pitching_temp'] = c1; continue
        if c0_lower.startswith('yeast'):
            metadata['yeast'] = c1; continue
        if 'attenuation' in c0_lower:
            metadata['attenuation'] = c1; continue

        # -- Hop row: contains time indication --
        time_match = re.search(r'(\d+)\s*min', c0, re.IGNORECASE)
        is_dry_hop = bool(re.search(r'dry\s*hop', c0, re.IGNORECASE))

        if time_match or is_dry_hop:
            if time_match:
                boil_min = int(time_match.group(1))
                hop_raw = c0[:time_match.start()].strip()
            else:
                boil_min = 0
                hop_raw = re.sub(r'dry\s*hop(s|ped)?', '', c0, flags=re.IGNORECASE).strip()

            hop_raw = re.sub(r'[\[\]\(\)]', '', hop_raw).strip()
            weight_str = re.sub(r'[^\d.]', '', c1)
            try:
                weight_oz = float(weight_str)
            except ValueError:
                continue

            use = 'Dry Hop' if is_dry_hop else 'Boil'
            hops.append({
                'raw_name': hop_raw,
                'weight_oz': weight_oz,
                'time': boil_min,
                'use': use,
            })
            continue

        # -- Fermentable row: col 1 has weight, col 2 has percentage --
        weight_match = re.search(r'([\d.]+)\s*(lb|oz)', c1, re.IGNORECASE)
        if weight_match and c0 and not is_metadata_row(c0_lower):
            weight_val = float(weight_match.group(1))
            weight_unit = weight_match.group(2).lower()
            weight_lb = weight_val if weight_unit == 'lb' else weight_val / 16.0

            pct = None
            pct_match = re.search(r'([\d.]+)\s*%', c2)
            if pct_match:
                pct = float(pct_match.group(1))

            fermentables.append({
                'raw_name': c0,
                'weight_lb': weight_lb,
                'percentage': pct,
            })
            continue

    # Validate: need at least 1 fermentable, 1 hop, and an OG
    if not fermentables or not hops or 'og' not in metadata:
        return None

    return {
        'table_title': title_row,
        'fermentables': fermentables,
        'hops': hops,
        'metadata': metadata,
    }


def parse_gravity(val_str):
    """Parse gravity from blog notation (1048 or 1.048) to decimal (1.048)."""
    try:
        val = float(val_str.replace(',', '').strip())
        if val > 2:
            return val / 1000.0
        return val
    except (ValueError, TypeError):
        return None


def parse_temp_f(val_str):
    """Parse temperature string (e.g. '149° F', '149º F') to Celsius."""
    if not val_str:
        return None
    m = re.search(r'([\d.]+)', val_str)
    if m:
        f = float(m.group(1))
        return (f - 32.0) * 5.0 / 9.0
    return None


def parse_minutes(val_str):
    """Parse boil time string to integer minutes."""
    if not val_str:
        return None
    m = re.search(r'(\d+)', val_str)
    return int(m.group(1)) if m else None


def extract_year(title):
    """Extract 4-digit year from recipe title."""
    m = re.search(r'\b(1[6-9]\d{2}|20[0-2]\d)\b', title)
    return int(m.group(1)) if m else None


def clean_recipe_name(title):
    """Strip 'Let's Brew [day] -' prefix from post title, preserving year."""
    name = re.sub(
        r"^\s*Let['\u2018\u2019\u201b.\[\]]?s['\u2018\u2019\u201b]?s?\s+Brew\s*"
        r"(\w+da?y\s*)?(\([^)]*\)\s*)?[-\u2013\u2014:.]?\s*",
        '', title, flags=re.IGNORECASE,
    )
    return name.strip()

# ─── BeerXML Generation ─────────────────────────────────────────────────────

def fmt(val):
    """Format numeric value to 7 decimal places (matching pattinson.xml style)."""
    if isinstance(val, float):
        return f'{val:.7f}'
    return str(val)


def build_recipe_xml(recipe, alpha_mode, include_narrative):
    """Generate BeerXML <RECIPE> element for a single recipe."""
    meta = recipe['metadata']
    year = recipe.get('year', 1900)
    boil_time = parse_minutes(meta.get('boil_time')) or 60

    # OG / FG
    og = parse_gravity(meta.get('og')) or 1.050
    fg = parse_gravity(meta.get('fg'))

    # Mash / Sparge temps
    mash_c = parse_temp_f(meta.get('mash_temp')) or MASH_DEFAULTS['step_temp']
    sparge_c = parse_temp_f(meta.get('sparge_temp')) or MASH_DEFAULTS['sparge_temp']

    # Track assumptions
    assumptions = []
    if year == 1900 and not extract_year(recipe.get('name', '')):
        assumptions.append('Year not found in title, assumed 1900')
    if not parse_minutes(meta.get('boil_time')):
        assumptions.append('Boil time not specified, assumed 60 min')
    if not parse_gravity(meta.get('og')):
        assumptions.append('OG not parseable, assumed 1.050')
    if not parse_temp_f(meta.get('mash_temp')):
        assumptions.append(f'Mash temp not specified, assumed {MASH_DEFAULTS["step_temp"]:.1f}\u00b0C (150\u00b0F)')
    if not parse_temp_f(meta.get('sparge_temp')):
        assumptions.append(f'Sparge temp not specified, assumed {MASH_DEFAULTS["sparge_temp"]:.1f}\u00b0C (168\u00b0F)')
    if not meta.get('yeast'):
        assumptions.append('Yeast not specified, assumed English Ale Yeast')

    # Boil size
    boil_size = POST_BOIL_L + EVAP_RATE_L_PER_HR * (boil_time / 60.0)

    # Total grain weight for infuse amount calc
    total_grain_kg = sum(f['weight_lb'] * 0.45359237 for f in recipe['fermentables'])
    total_grain_lb = sum(f['weight_lb'] for f in recipe['fermentables'])
    infuse_qt = total_grain_lb * MASH_DEFAULTS['water_grain_ratio_qt_lb']
    infuse_L = infuse_qt * 0.946352946

    # Yeast info
    yeast_name = meta.get('yeast', 'English Ale Yeast')
    yeast_name_clean = re.sub(r'\s+', ' ', yeast_name).strip()
    yeast_type = 'Lager' if 'lager' in yeast_name_clean.lower() else 'Ale'

    lines = []
    def L(text):
        lines.append(text)

    L('<RECIPE>')
    L(f' <NAME>{xml_escape(recipe["name"])}</NAME>')
    L(' <VERSION>1</VERSION>')
    L(' <TYPE>All Grain</TYPE>')
    L(' <BREWER>barclayperkins.blogspot.com</BREWER>')
    L(f' <BATCH_SIZE>{fmt(BATCH_SIZE_L)}</BATCH_SIZE>')
    L(f' <BOIL_SIZE>{fmt(boil_size)}</BOIL_SIZE>')
    L(f' <BOIL_TIME>{fmt(float(boil_time))}</BOIL_TIME>')
    L(f' <EFFICIENCY>{fmt(EFFICIENCY)}</EFFICIENCY>')

    # Hops
    L(' <HOPS>')
    for h in recipe['hops']:
        hop_name, embedded_alpha = normalise_hop(h['raw_name'])
        alpha, alpha_source = lookup_alpha(hop_name, year, embedded_alpha, alpha_mode)
        if 'fallback' in alpha_source or 'no historical' in alpha_source:
            assumptions.append(f'Hop "{hop_name}": alpha {alpha}% ({alpha_source})')
        weight_kg = h['weight_oz'] * 0.0283495
        L('  <HOP>')
        L(f'   <NAME>{xml_escape(hop_name)}</NAME>')
        L('   <VERSION>1</VERSION>')
        L(f'   <ALPHA>{fmt(alpha)}</ALPHA>')
        L(f'   <AMOUNT>{fmt(weight_kg)}</AMOUNT>')
        L(f'   <USE>{h["use"]}</USE>')
        L(f'   <TIME>{fmt(float(h["time"]))}</TIME>')
        L('   <TYPE>Both</TYPE>')
        L('   <FORM>Pellet</FORM>')
        L('  </HOP>')
    L(' </HOPS>')

    # Fermentables
    L(' <FERMENTABLES>')
    for f in recipe['fermentables']:
        info = classify_fermentable(f['raw_name'])
        if info.get('assumed'):
            assumptions.append(f'Grain "{f["raw_name"]}": not recognised, assumed generic Grain 70% yield')
        weight_kg = f['weight_lb'] * 0.45359237
        L('  <FERMENTABLE>')
        L(f'   <NAME>{xml_escape(info["name"])}</NAME>')
        L('   <VERSION>1</VERSION>')
        L(f'   <TYPE>{info["type"]}</TYPE>')
        L(f'   <AMOUNT>{fmt(weight_kg)}</AMOUNT>')
        L(f'   <YIELD>{fmt(info["yield"])}</YIELD>')
        L(f'   <COLOR>{fmt(info["color"])}</COLOR>')
        L(f'   <ADD_AFTER_BOIL>FALSE</ADD_AFTER_BOIL>')
        L(f'   <ORIGIN>{xml_escape(info["origin"])}</ORIGIN>')
        L('  </FERMENTABLE>')
    L(' </FERMENTABLES>')

    # Miscs (empty)
    L(' <MISCS/>')

    # Yeasts
    L(' <YEASTS>')
    L('  <YEAST>')
    L(f'   <NAME>{xml_escape(yeast_name_clean)}</NAME>')
    L('   <VERSION>1</VERSION>')
    L(f'   <TYPE>{yeast_type}</TYPE>')
    L('   <FORM>Liquid</FORM>')
    L(f'   <AMOUNT>{fmt(0.125)}</AMOUNT>')
    L('  </YEAST>')
    L(' </YEASTS>')

    # Waters (empty)
    L(' <WATERS/>')

    # Style (minimal generic)
    L(' <STYLE>')
    L('  <NAME>Historical Beer</NAME>')
    L('  <VERSION>1</VERSION>')
    L('  <CATEGORY>Historical Beer</CATEGORY>')
    L('  <CATEGORY_NUMBER>27</CATEGORY_NUMBER>')
    L('  <STYLE_LETTER>A</STYLE_LETTER>')
    L('  <STYLE_GUIDE>BJCP 2015</STYLE_GUIDE>')
    L(f'  <TYPE>{yeast_type}</TYPE>')
    L(f'  <OG_MIN>{fmt(og * 0.9)}</OG_MIN>')
    L(f'  <OG_MAX>{fmt(og * 1.1)}</OG_MAX>')
    L(f'  <FG_MIN>{fmt((fg or og * 0.75) * 0.9)}</FG_MIN>')
    L(f'  <FG_MAX>{fmt((fg or og * 0.75) * 1.1)}</FG_MAX>')
    L('  <IBU_MIN>0.0000000</IBU_MIN>')
    L('  <IBU_MAX>100.0000000</IBU_MAX>')
    L('  <COLOR_MIN>0.0000000</COLOR_MIN>')
    L('  <COLOR_MAX>100.0000000</COLOR_MAX>')
    L(' </STYLE>')

    # Equipment
    eq = EQUIPMENT
    L(' <EQUIPMENT>')
    L(f'  <NAME>{xml_escape(eq["name"])}</NAME>')
    L('  <VERSION>1</VERSION>')
    L(f'  <BOIL_SIZE>{fmt(boil_size)}</BOIL_SIZE>')
    L(f'  <BATCH_SIZE>{fmt(BATCH_SIZE_L)}</BATCH_SIZE>')
    L(f'  <TUN_VOLUME>{fmt(eq["tun_volume"])}</TUN_VOLUME>')
    L(f'  <TUN_WEIGHT>{fmt(eq["tun_weight"])}</TUN_WEIGHT>')
    L(f'  <TUN_SPECIFIC_HEAT>{fmt(eq["tun_specific_heat"])}</TUN_SPECIFIC_HEAT>')
    L(f'  <TOP_UP_WATER>{fmt(eq["top_up_water"])}</TOP_UP_WATER>')
    L(f'  <TRUB_CHILLER_LOSS>{fmt(eq["trub_chiller_loss"])}</TRUB_CHILLER_LOSS>')
    L(f'  <BOIL_TIME>{fmt(float(boil_time))}</BOIL_TIME>')
    L('  <CALC_BOIL_VOLUME>TRUE</CALC_BOIL_VOLUME>')
    L(f'  <LAUTER_DEADSPACE>{fmt(eq["lauter_deadspace"])}</LAUTER_DEADSPACE>')
    L(f'  <TOP_UP_KETTLE>{fmt(eq["top_up_kettle"])}</TOP_UP_KETTLE>')
    L(f'  <HOP_UTILIZATION>{fmt(eq["hop_utilization"])}</HOP_UTILIZATION>')
    L(f'  <COOLING_LOSS_PCT>{fmt(eq["cooling_loss_pct"])}</COOLING_LOSS_PCT>')
    L(' </EQUIPMENT>')

    # Mash
    md = MASH_DEFAULTS
    L(' <MASH>')
    L(f'  <NAME>{xml_escape(md["name"])}</NAME>')
    L('  <VERSION>1</VERSION>')
    L(f'  <GRAIN_TEMP>{fmt(md["grain_temp"])}</GRAIN_TEMP>')
    L(f'  <TUN_TEMP>{fmt(md["tun_temp"])}</TUN_TEMP>')
    L(f'  <SPARGE_TEMP>{fmt(sparge_c)}</SPARGE_TEMP>')
    L(f'  <PH>{fmt(md["ph"])}</PH>')
    L('  <EQUIP_ADJUST>TRUE</EQUIP_ADJUST>')
    L('  <MASH_STEPS>')
    L('   <MASH_STEP>')
    L('    <NAME>Mash In</NAME>')
    L('    <VERSION>1</VERSION>')
    L(f'    <TYPE>{md["step_type"]}</TYPE>')
    L(f'    <INFUSE_AMOUNT>{fmt(infuse_L)}</INFUSE_AMOUNT>')
    L(f'    <STEP_TIME>{fmt(md["step_time"])}</STEP_TIME>')
    L(f'    <STEP_TEMP>{fmt(mash_c)}</STEP_TEMP>')
    L(f'    <RAMP_TIME>{fmt(md["ramp_time"])}</RAMP_TIME>')
    L(f'    <END_TEMP>{fmt(mash_c)}</END_TEMP>')
    L('   </MASH_STEP>')
    L('  </MASH_STEPS>')
    L(' </MASH>')

    # Recipe-level fields — build notes now that all assumptions are collected
    notes_parts = []
    notes_parts.append(f"Recipe credit: Ron Pattinson, Barclay Perkins blog")
    notes_parts.append(f"Year: {year}")
    if meta.get('ibu'):
        notes_parts.append(f"Blog IBU: {meta['ibu']}")
    if meta.get('srm'):
        notes_parts.append(f"Blog SRM: {meta['srm']}")
    if meta.get('abv'):
        notes_parts.append(f"Blog ABV: {meta['abv']}")
    if meta.get('attenuation'):
        notes_parts.append(f"Apparent Attenuation: {meta['attenuation']}")
    if meta.get('pitching_temp'):
        notes_parts.append(f"Pitching Temp: {meta['pitching_temp']}")
    if alpha_mode == 'historical':
        notes_parts.append(f"Alpha acid mode: experimental-hop-adjustment (era-adjusted alphas)")
    if assumptions:
        notes_parts.append('')
        notes_parts.append('--- Assumptions ---')
        for a in assumptions:
            notes_parts.append(f'* {a}')
    if recipe.get('tags'):
        notes_parts.append('')
        notes_parts.append(f"Tags: {', '.join(recipe['tags'])}")
    if include_narrative and recipe.get('narrative'):
        notes_parts.append('')
        notes_parts.append('--- Blog Text ---')
        notes_parts.append(recipe['narrative'])
    notes_parts.append('')
    notes_parts.append(f"Source: {recipe.get('url', '')}")
    notes_text = '\n'.join(notes_parts)

    L(f' <NOTES>{xml_escape(notes_text)}</NOTES>')
    L(f' <OG>{fmt(og)}</OG>')
    if fg:
        L(f' <FG>{fmt(fg)}</FG>')
    L(f' <CARBONATION>{fmt(FERM_DEFAULTS["carbonation"])}</CARBONATION>')
    L(f' <FERMENTATION_STAGES>{FERM_DEFAULTS["stages"]}</FERMENTATION_STAGES>')
    L(f' <PRIMARY_AGE>{fmt(FERM_DEFAULTS["primary_age"])}</PRIMARY_AGE>')
    L(f' <PRIMARY_TEMP>{fmt(FERM_DEFAULTS["primary_temp"])}</PRIMARY_TEMP>')
    L(f' <SECONDARY_AGE>{fmt(FERM_DEFAULTS["secondary_age"])}</SECONDARY_AGE>')
    L(f' <SECONDARY_TEMP>{fmt(FERM_DEFAULTS["secondary_temp"])}</SECONDARY_TEMP>')
    L(f' <IBU_METHOD>Tinseth</IBU_METHOD>')
    L('</RECIPE>')

    return '\n'.join(lines)

# ─── Feed Fetching ───────────────────────────────────────────────────────────

def fetch_feed_page(start_index, max_results=FEED_PAGE_SIZE):
    """Fetch a page of blog posts from the Blogger JSON feed."""
    url = f"{FEED_BASE}?alt=json&start-index={start_index}&max-results={max_results}"
    result = subprocess.run(
        ['curl', '-s', '--max-time', '30', url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None, 0
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, 0

    total = int(data['feed'].get('openSearch$totalResults', {}).get('$t', 0))
    entries = data['feed'].get('entry', [])
    return entries, total


def get_post_url(entry):
    """Extract the blog post URL from a feed entry."""
    for link in entry.get('link', []):
        if link.get('rel') == 'alternate' and link.get('type') == 'text/html':
            return link.get('href', '')
    return ''

# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Convert Barclay Perkins blog recipes to BeerXML.',
    )
    parser.add_argument('--experimental-hop-adjustment', action='store_true',
                        help='Use era-adjusted hop alpha acids instead of BeerSmith defaults')
    parser.add_argument('--notes', choices=['minimal', 'full'],
                        default='full', help='Notes detail level (default: full)')
    parser.add_argument('--output', default='output',
                        help='Output directory (default: output)')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of recipes (0 = all)')
    parser.add_argument('--start', type=int, default=1,
                        help='Start from feed index (default: 1)')
    parser.add_argument('--combined', action='store_true',
                        help='Write all recipes to a single file instead of individual files')
    parser.add_argument('--year-first', action='store_true',
                        help='Put year at start of filenames (e.g. 1991_Youngs_Stout.xml)')
    args = parser.parse_args()

    include_narrative = (args.notes == 'full')
    if args.experimental_hop_adjustment:
        modes = ['historical']
    else:
        modes = ['beersmith']

    # Collect all recipes
    all_recipes = []
    skipped = 0
    start_index = args.start
    total_posts = None

    print("Fetching recipes from barclayperkins.blogspot.com...", file=sys.stderr)

    while True:
        entries, total = fetch_feed_page(start_index)
        if total_posts is None:
            total_posts = total
            print(f"Total posts in feed: {total}", file=sys.stderr)

        if not entries:
            break

        for entry in entries:
            title = entry['title']['$t']
            content = entry['content']['$t']
            url = get_post_url(entry)

            # Parse tables from HTML
            tp = TableParser()
            tp.feed(content)

            # Try each table as a potential recipe
            found_recipe = False

            # Extract narrative once per post (shared across recipes)
            narrative = ''
            if include_narrative:
                te = TextExtractor()
                te.feed(content)
                narrative = te.get_text()

            tags = [c['term'] for c in entry.get('category', [])]

            for table in tp.tables:
                recipe_data = parse_recipe_table(table)
                if recipe_data is None:
                    continue

                table_title = recipe_data.get('table_title')

                year = extract_year(table_title) if table_title else None
                if year is None:
                    year = extract_year(title)
                if year is None:
                    year = 1900  # fallback

                # Prefer table title (99% have one); fall back to cleaned post title
                name = table_title or clean_recipe_name(title) or title

                recipe = {
                    'name': name,
                    'year': year,
                    'url': url,
                    'narrative': narrative,
                    'tags': tags,
                    **recipe_data,
                }
                all_recipes.append(recipe)
                found_recipe = True

                if args.limit and len(all_recipes) >= args.limit:
                    break

            if not found_recipe:
                skipped += 1

            print(f"\r  {len(all_recipes)} recipes parsed, {skipped} skipped "
                  f"(page {start_index}-{start_index + len(entries) - 1} of {total_posts})",
                  end='', file=sys.stderr)

            if args.limit and len(all_recipes) >= args.limit:
                break

        if args.limit and len(all_recipes) >= args.limit:
            break

        start_index += len(entries)
        if start_index > total_posts:
            break

    print(file=sys.stderr)
    print(f"Parsed {len(all_recipes)} recipes, skipped {skipped} posts", file=sys.stderr)

    if not all_recipes:
        print("No recipes found!", file=sys.stderr)
        sys.exit(1)

    # Sort by name then year (or by year first if --year-first)
    if args.year_first:
        all_recipes.sort(key=lambda r: (r['year'], r['name']))
    else:
        all_recipes.sort(key=lambda r: (r['name'], r['year']))

    # Generate output
    MODE_DIRS = {'beersmith': 'beerxml', 'historical': 'beerxml-experimental-hop-adjustment'}
    for mode in modes:
        mode_dir = os.path.join(args.output, MODE_DIRS[mode])
        os.makedirs(mode_dir, exist_ok=True)

        if not args.combined:
            for recipe in all_recipes:
                xml = '\n'.join([
                    '<?xml version="1.0" encoding="UTF-8"?>',
                    '<RECIPES>',
                    build_recipe_xml(recipe, mode, include_narrative),
                    '</RECIPES>',
                ])
                safe_name = re.sub(r'[^\w\s-]', '', recipe['name'])
                safe_name = re.sub(r'\s+', '_', safe_name.strip())[:80]
                year_str = str(recipe['year'])
                # Only reposition year if name starts with a simple "YYYY_" pattern
                simple_year = re.match(r'^' + year_str + r'_(?!\d|and_|late)', safe_name)
                if simple_year:
                    name_no_year = safe_name[simple_year.end():]
                    if args.year_first:
                        fname = f"{year_str}_{name_no_year}.xml"
                    else:
                        fname = f"{name_no_year}_{year_str}.xml"
                else:
                    # Complex pattern — use name as-is
                    fname = f"{safe_name}.xml"
                fpath = os.path.join(mode_dir, fname)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(xml)
            print(f"Wrote {len(all_recipes)} individual files to {mode_dir}/ ({mode} alpha mode)",
                  file=sys.stderr)
        else:
            xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<RECIPES>']
            for recipe in all_recipes:
                xml_parts.append(build_recipe_xml(recipe, mode, include_narrative))
            xml_parts.append('</RECIPES>')

            out_path = os.path.join(mode_dir, 'recipes.xml')
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(xml_parts))

            print(f"Wrote {len(all_recipes)} recipes to {out_path} ({mode} alpha mode)",
                  file=sys.stderr)


if __name__ == '__main__':
    main()
