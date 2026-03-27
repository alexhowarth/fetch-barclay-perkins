# Findings

Notes from figuring out how Ron Pattinson's blog recipes work and what goes into the BeerXML conversion.

## Source

**Blog:** [Shut up about Barclay Perkins](https://barclayperkins.blogspot.com/) by Ron Pattinson  
**Recipe label:** [beer recipes](https://barclayperkins.blogspot.com/search/label/beer%20recipes)  
**Total posts:** 1,214 tagged "beer recipes"  
**Parseable:** ~88% contain structured HTML recipe tables; ~12% are index/summary posts or historical comparison tables (skip these)

## Data Access

Blogger exposes a JSON feed API — no scraping/Cloudflare issues:

```
https://barclayperkins.blogspot.com/feeds/posts/default/-/beer%20recipes?alt=json&start-index=1&max-results=25
```

- `start-index`: 1-based offset for pagination
- `max-results`: items per page (max 150)
- Response includes `feed.openSearch$totalResults.$t` for total count
- Each entry has `entry[].content.$t` (full HTML), `entry[].title.$t`, `entry[].published.$t`

## Blog Recipe Table Format

Posts use a consistent HTML `<table>` structure:

| Row type | Col 1 | Col 2 | Col 3 |
|----------|-------|-------|-------|
| **Title** | Recipe name (colspan) | — | — |
| **Grain** | Grain name | Weight (lb) | Percentage (%) |
| **Hop** | Hop name + boil time | Weight (oz) | — |
| **Metadata** | Field label | Value | — |

### How often each metadata field appears (~51 posts checked)

| Field | Frequency | Example value |
|-------|-----------|---------------|
| OG | 98% | 1048 (brewer notation) |
| FG | 96% | 1010 |
| ABV | 94% | 4.96 |
| Apparent attenuation | 88% | 79.17% |
| IBU | 86% | 35 |
| SRM | 86% | 24 |
| Mash at | 82% | 149° F |
| Sparge at | 72% | 170° F |
| Boil time | 78% | 60 minutes |
| pitching temp | 60% | 62° F |
| Yeast | 58% | Wyeast 1768 London ESB |

### How to tell rows apart

- **Grain row:** Col 2 is a number (weight in lb), Col 3 is a percentage
- **Hop row:** Col 1 contains a time indication (e.g. "90 mins", "30 min"), Col 2 is a number (weight in oz), Col 3 is empty or absent
- **Metadata row:** Col 1 matches a known label (OG, FG, ABV, etc.), Col 2 is the value

## Unit Conversions (blog → BeerXML)

BeerXML requires metric units throughout:

| Measurement | Blog unit | BeerXML unit | Conversion |
|-------------|-----------|--------------|------------|
| Grain weight | lb | kg | × 0.45359237 |
| Hop weight | oz | kg | × 0.02834952 |
| Volume | US gal | L | × 3.78541178 |
| Temperature | °F | °C | (°F − 32) × 5/9 |
| Gravity | 1048 (brewer) | 1.048 (decimal) | ÷ 1000 |
| Time | minutes | minutes | no conversion |

## Confirmed Process Defaults

Derived from the blog's own BeerSmith recipe exports and BeerSmith mash profile. The author confirmed batch size on [The Home Brew Forum](https://www.thehomebrewforum.co.uk/) (username: patto1ro).

### Batch & Equipment

| Parameter | Value | Source |
|-----------|-------|--------|
| Batch size | 22.71 L | BeerSmith export |
| Boil size | 31.84 L (60 min boil) / 33.97 L (90 min boil) | BeerSmith export (calc'd) |
| Efficiency | 72% | BeerSmith export |
| Type | All Grain | BeerSmith export |
| Equipment | Pot and Cooler (37.85 L) | BeerSmith export |
| Tun volume | 37.85 L | BeerSmith export |
| Tun weight | 4.08 kg | BeerSmith export |
| Tun specific heat | 0.30 | BeerSmith export |
| Trub/chiller loss | 3.79 L | BeerSmith export |
| Lauter deadspace | 3.03 L | BeerSmith export |
| Hop utilization | 100% | BeerSmith export |
| Cooling loss | 4% | BeerSmith export |
| Evaporation rate | ~13% | BeerSmith export |
| IBU method | Tinseth | BeerSmith export |

### Mash

| Parameter | Value | Source |
|-----------|-------|--------|
| Mash profile | Single Infusion, Light Body, No Mash Out | BeerSmith profile |
| Step name | Mash In | BeerSmith export |
| Step type | Infusion | BeerSmith export |
| Step time | 75 min | BeerSmith export |
| Step temp | per-recipe "Mash at" from blog (default 65.56°C if absent) | blog / BeerSmith export |
| Ramp time | 2 min | BeerSmith export |
| Grain temp | 22.22°C | BeerSmith export |
| Tun temp | 22.22°C | BeerSmith export |
| Sparge temp | per-recipe "Sparge at" from blog (default 75.56°C if absent) | blog / BeerSmith export |
| Water:grain ratio | 1.25 qt/lb | BeerSmith export |
| pH | 5.4 | BeerSmith export |
| Batch sparge | FALSE | BeerSmith export |

**Note:** Mash time is never specified on the blog. Dr Mike on The Home Brew Forum confirmed: "no mash times are given." The 75 min default from the blog's BeerSmith profile is the correct value.

**Note:** "Mash at" and "Sparge at" from the blog are the authoritative per-recipe values. The blog used BeerSmith's canned mash profile (default 65.56°C / 148°F) rather than adjusting per recipe — the historical brewing-record temperatures should take priority.

### Fermentation

| Parameter | Value | Source |
|-----------|-------|--------|
| Stages | 2 | BeerSmith export |
| Primary age | 4 days | BeerSmith export |
| Primary temp | 19.44°C | BeerSmith export |
| Secondary age | 10 days | BeerSmith export |
| Secondary temp | 19.44°C | BeerSmith export |
| Carbonation | 2.3 vols CO₂ | BeerSmith export |

**Note:** When "pitching temp" is present on the blog, it represents the historical pitching temperature. It does not directly map to a BeerXML fermentation field but is valuable metadata (could go in `<NOTES>`).

## BeerXML Field Mapping

### Per-recipe fields (from blog)

| BeerXML tag | Blog source | Notes |
|-------------|------------|-------|
| `<NAME>` | Post title | Strip "Let's Brew - " prefix |
| `<OG>` | "OG" row | Convert from 1048 → 1.048 |
| `<FG>` | "FG" row | Convert from 1010 → 1.010 |
| `<BOIL_TIME>` | "Boil time" row | In minutes; default 60 if absent |
| `<FERMENTABLE><NAME>` | Grain name | As-is from blog |
| `<FERMENTABLE><AMOUNT>` | Grain weight | Convert lb → kg |
| `<HOP><NAME>` | Hop name | Parse out time suffix |
| `<HOP><AMOUNT>` | Hop weight | Convert oz → kg |
| `<HOP><TIME>` | Hop time | Parsed from hop name field |
| `<MASH_STEP><STEP_TEMP>` | "Mash at" | Convert °F → °C |
| `<MASH><SPARGE_TEMP>` | "Sparge at" | Convert °F → °C |
| `<NOTES>` | Pitching temp, attenuation, yeast | Capture extra metadata |
| `<ABV>` | "ABV" row | Percentage |

### Static defaults (from the blog's BeerSmith recipes)

| BeerXML tag | Value |
|-------------|-------|
| `<VERSION>` | 1 |
| `<TYPE>` | All Grain |
| `<BREWER>` | barclayperkins.blogspot.com |
| `<BATCH_SIZE>` | 22.7124707 |
| `<EFFICIENCY>` | 72.0 |
| `<FERMENTATION_STAGES>` | 2 |
| `<PRIMARY_AGE>` | 4.0 |
| `<PRIMARY_TEMP>` | 19.4444444 |
| `<SECONDARY_AGE>` | 10.0 |
| `<SECONDARY_TEMP>` | 19.4444444 |
| `<CARBONATION>` | 2.3 |
| `<MASH_STEP><STEP_TIME>` | 75.0 |
| `<MASH_STEP><TYPE>` | Infusion |
| `<MASH><GRAIN_TEMP>` | 22.2222222 |
| `<MASH><PH>` | 5.4 |

## Hop varieties

Across all 1,013 recipes there are exactly 15 distinct hop varieties (3,184 total hop additions)
once you normalise trailing "s" suffixes and strip out embedded alpha %:

| Hop variety | Additions | Recipes | Notes |
|-------------|-----------|---------|-------|
| Fuggles | 1,310 | 726 | Dominant English hop |
| Goldings | 1,257 | 676 | Includes EK Goldings |
| Cluster | 265 | 225 | American, common in wartime/post-war |
| Hallertau(er) | 158 | 115 | Continental, sometimes with "Mittelfrüh" |
| Saaz | 81 | 54 | Czech |
| Strisselspalt | 42 | 38 | Alsace |
| Styrian Goldings | 31 | 22 | Slovenian |
| Spalt | 19 | 19 | German |
| Brewer's Gold | 6 | 5 | English |
| Bramling Cross | 5 | 4 | English |
| Northern Brewer | 4 | 4 | English/German |
| Poperinge | 3 | 3 | Belgian |
| Alsace | 1 | 1 | French |
| Northdown | 1 | 1 | English |
| Lublin | 1 | 1 | Polish |

### Alpha acids are sometimes embedded in hop names

Some entries include alpha % inline, e.g.:
- `Goldings 5.5%` → name: Goldings, alpha: 5.5
- `Hallertauer 3.5%` → name: Hallertauer, alpha: 3.5
- `Cluster 7%` → name: Cluster, alpha: 7.0

These are valuable because they're the most specific alpha data we have for a given recipe.

## Historical Alpha Acid Data (from the blog)

The blog has published extensive historical hop alpha acid analyses, sourced from
Brewers' Society statistical handbooks and brewing science texts.

### 1940s data (1942–1943 crop analyses)

| Variety | Alpha resin (1942) | Alpha resin (1943) |
|---------|-------------------|-------------------|
| Fuggles | 5.75% | 4.97% |
| Goldings Varieties | 6.20% | 5.65% |
| Goldings | 6.33% | 5.27% |

Source: "Hops in 1944" blog post, citing wartime analyses.

### 1950s data (1953 Challenge Cup competition)

| Variety | Alpha resin range |
|---------|------------------|
| Northern Brewer | 7.95–9.02% |
| Brewers Gold | 7.08–8.88% |
| Pride of Kent | 7.07–8.04% |
| Early Promise | 4.38–7.71% |

Source: "New hop varieties in 1953" blog post.

### 1970s data (UK Brewers' Society annual averages)

| Variety | 1969 | 1970 | 1971 | 1972 | 1973 | 1974 | 1975 | 1976 | 1977 | 1978 | 1979 | 1980 |
|---------|------|------|------|------|------|------|------|------|------|------|------|------|
| Goldings | — | — | 4.5 | 4.2 | 5.2 | 4.9 | 4.8 | 5.6 | 4.6 | 5.2 | 4.5 | 4.7 |
| Fuggles | — | — | 3.7 | 4.1 | 4.4 | 4.4 | 4.2 | 4.5 | 3.9 | 4.6 | 3.9 | 4.2 |
| Northern Brewer | 7.1 | 6.7 | 6.1 | 6.5 | 7.6 | 6.9 | 7.1 | 7.5 | 6.9 | 7.5 | 7.5 | 7.4 |
| Bramling Cross | — | 6.2 | 5.0 | 4.7 | 6.4 | 5.6 | 5.6 | 6.8 | 4.8 | 5.7 | 5.5 | 5.5 |
| Bullion | 6.6 | 6.3 | 5.9 | 7.4 | 8.4 | 7.7 | 7.7 | 9.2 | 7.1 | 8.3 | 6.7 | 7.8 |
| Wye Northdown | — | — | 7.2 | 7.7 | 8.5 | 8.4 | 8.1 | 8.4 | 8.1 | 8.6 | 8.0 | 7.9 |
| Progress | — | 5.4 | 4.9 | 4.7 | 5.9 | 5.4 | 5.1 | 6.3 | 5.1 | 5.9 | 5.1 | 5.4 |
| WGV | — | — | 5.0 | 4.7 | 5.7 | 5.6 | 5.1 | 6.2 | 5.2 | 6.0 | 5.2 | 5.7 |
| Wye Challenger | — | — | 7.1 | 7.0 | 7.4 | 6.9 | 6.8 | 7.4 | 7.0 | 7.8 | 7.2 | 7.3 |
| Wye Target | — | — | — | — | 10.0 | 9.3 | 9.7 | 9.9 | 10.2 | 11.8 | 10.5 | 10.8 |

Sources: UK Brewers' Society Statistical Handbooks 1974, 1978, 1980.

### Modern reference data (2000, from Briggs et al.)

| Variety | Alpha acid range |
|---------|-----------------|
| Fuggle | 3.0–5.6% |
| Goldings | 4.4–6.7% |
| Bramling Cross | 6.0–7.8% |
| Northern Brewer | 6.5–10.0% |
| WGV | 5.4–7.7% |
| Wye Challenger | 6.5–8.5% |
| Wye Northdown | 6.8–9.6% |
| Wye Target | 9.9–12.6% |
| Progress | 6.0–7.5% |

Source: "Brewing: Science and Practice", Briggs et al., 2004, page 252 (cited on blog).

## How the alpha acids work

If a recipe's hop name includes an explicit alpha % (e.g. "Goldings 5.5%"), that gets used directly — it's the most specific value available, whether it was chosen deliberately or BeerSmith filled it in.

Otherwise, the year from the recipe title drives an era-based lookup using the historical data above:
- Pre-1940: based on the 1942 crop analyses (these varieties hadn't changed much before that)
- 1940s–1960s: 1942/1943 data still applies — the 1970s figures show values hadn't shifted dramatically yet
- 1970s–1980s: annual averages from the Brewers' Society tables
- Post-1980: modern reference ranges (midpoints from Briggs et al.)

For varieties without historical data (Cluster, Saaz, Strisselspalt, etc.) the fallback is modern midpoint values. These are mostly continental or American hops with better-documented alphas anyway.

### Era-adjusted alpha acid values used

| Hop | Pre-1940 | 1940s–1960s | 1970s | Modern fallback |
|-----|----------|------------|-------|-----------------|
| Fuggles | 5.5 | 5.0 | 4.2 | 4.5 |
| Goldings / EKG | 6.0 | 5.5 | 4.8 | 5.0 |
| Cluster | 7.0 | 7.0 | 7.0 | 7.0 |
| Hallertau(er) | 4.0 | 4.0 | 4.0 | 4.0 |
| Saaz | 3.5 | 3.5 | 3.5 | 3.75 |
| Strisselspalt | 3.5 | 3.5 | 3.5 | 3.5 |
| Styrian Goldings | 5.0 | 5.0 | 5.0 | 5.25 |
| Spalt | 4.5 | 4.5 | 4.5 | 4.5 |
| Northern Brewer | 8.0 | 8.0 | 7.0 | 8.0 |
| Bramling Cross | 6.0 | 6.0 | 5.5 | 6.5 |
| Brewer's Gold | 8.0 | 8.0 | 7.5 | 8.5 |
| WGV | 5.5 | 5.5 | 5.3 | 6.0 |
| Wye Target | — | — | 10.0 | 11.0 |
| Wye Challenger | — | — | 7.2 | 7.5 |
| Wye Northdown | — | — | 8.1 | 8.0 |

### How these compare to BeerSmith defaults

The [BeerSmith hop list](https://beersmith.com/hop-list/) publishes the default alpha acid values
used in BeerSmith's ingredient database. The blog uses these BeerSmith defaults for all recipes
regardless of era (confirmed by the BeerSmith exports showing EKG at 5.0% for 1805 and 1835 recipes).

| Hop | BeerSmith default | Pre-1940 | 1940s–60s | 1970s | Modern | Notes |
|-----|-------------------|-------------|--------------|-----------|------------|-------|
| Fuggles | **4.5%** | 5.5 | 5.0 | 4.2 | 4.5 | Modern matches |
| Goldings (EKG) | **5.0%** | 6.0 | 5.5 | 4.8 | 5.0 | Modern matches |
| Cluster | **7.0%** | 7.0 | 7.0 | 7.0 | 7.0 | All match |
| Hallertau(er) | **4.8%** (generic) / **4.0%** (Mittelfrüh) | 4.0 | 4.0 | 4.0 | 4.0 | Mittelfrüh matches |
| Saaz | **4.0%** | 3.5 | 3.5 | 3.5 | 3.75 | 0.25–0.5 low |
| Strisselspalt | **4.0%** | 3.5 | 3.5 | 3.5 | 3.5 | 0.5 low |
| Styrian Goldings | **5.4%** | 5.0 | 5.0 | 5.0 | 5.25 | ~0.15 low |
| Northern Brewer | **8.5%** | 8.0 | 8.0 | 7.0 | 8.0 | 0.5 low |
| Bramling Cross | **6.0%** | 6.0 | 6.0 | 5.5 | 6.5 | Pre-1940 matches |
| Brewer's Gold | **8.0%** | 8.0 | 8.0 | 7.5 | 8.5 | Pre-1940 matches |
| WGV | **6.0%** | 5.5 | 5.5 | 5.3 | 6.0 | Modern matches |
| Target | **11.0%** | — | — | 10.0 | 11.0 | Modern matches |
| Challenger | **7.5%** | — | — | 7.2 | 7.5 | Modern matches |
| Northdown | **8.5%** | — | — | 8.1 | 8.0 | 0.5 low |
| Spalt(er) | **4.5%** | 4.5 | 4.5 | 4.5 | 4.5 | All match |
| Lublin | **5.0%** | — | — | — | — | No era data |

The modern column lines up closely with BeerSmith defaults, which confirms the blog's IBU calculations
are based on those modern values. The biggest divergence is pre-1940 Fuggles and Goldings — both
are +1.0% higher than what BeerSmith uses.

### Sanity check: blog IBU

The blog's IBU value is useful as a sanity check — if the computed IBU (Tinseth) diverges more
than ~20% from what's on the blog, something's probably wrong with the parsing.

## Tinseth IBU Calculation

### BeerSmith's Tinseth implementation

Per [BeerSmith's blog](https://beersmith.com/blog/2021/09/23/hop-utilization-models-for-beer-brewing-compared/),
BeerSmith uses the standard Tinseth formula without modification:

```
Utilisation = bigness × boil_factor
  bigness    = 1.65 × 0.000125^(OG − 1.0)
  boil_factor = (1 − e^(−0.04 × time_min)) / 4.15

IBU = Utilisation × alpha_decimal × weight_oz × 7489 / volume_gal
```

Or equivalently in metric:

```
IBU = Utilisation × (alpha_pct / 100) × weight_kg × 1,000,000 / volume_L
```

The constant 7489 ≈ 1,000,000 × 28.3495 g/oz ÷ 3785.41 mL/gal — purely a unit conversion,
not a BeerSmith-specific adjustment.

### Volume denominator: batch volume, not post-boil

Testing against the blog's BeerSmith recipe exports:

| Volume used | Calc IBU | BeerSmith IBU | Diff |
|-------------|----------|---------------|------|
| Batch (22.71 L / 6.0 gal) | 109.7 | 91.5 | +19.9% |
| Post-boil (26.50 L / 7.0 gal) | 94.0 | 91.5 | +2.7% |
| Boil (31.84 L / 8.41 gal) | 78.3 | 91.5 | −14.4% |

**Post-boil volume** (batch + trub/chiller loss = 22.71 + 3.79 = 26.50 L) produces the closest match.
The remaining ~2.7% gap is consistent with BeerSmith's 4% cooling loss factor. This means
BeerSmith uses post-boil kettle volume as the Tinseth denominator, which is the standard
interpretation (Tinseth's original formula is based on finished wort volume in the kettle).

### Testing the era-adjusted alphas against the blog's IBU

Tried 9 recipes spanning 1885–1990 using era-specific alphas and both volume denominators to see
how far off they land from the blog's published IBU:

| Recipe | Year | Blog IBU | Batch vol | Post-boil | Best match |
|--------|------|----------|-----------|-----------|------------|
| Youngs Premium Lager | 1990 | 25 | 26.8 (+7%) | 23.0 (−8%) | Both close |
| Thomas Usher Export PA | 1885 | 96 | 81.9 (−15%) | 70.2 (−27%) | Batch |
| BP East India Porter | 1910 | 93 | 100.3 (+8%) | 85.9 (−8%) | Both close |
| Wm Younger XXXX | 1885 | 75 | 72.0 (−4%) | 61.7 (−18%) | Batch |
| Fullers Porter | 1887 | 43 | 55.5 (+29%) | 47.6 (+11%) | Post-boil |
| Perry XX | 1936 | 35 | 48.7 (+39%) | 41.8 (+19%) | Post-boil |
| Maclay Oat Malt Stout | 1966 | 21 | 23.4 (+11%) | 20.0 (−5%) | Post-boil |
| Adnams BLB | 1913 | 30 | 35.5 (+18%) | 30.4 (+2%) | Post-boil |
| Heineken Bok | 1911 | 17 | 15.1 (−11%) | 13.0 (−24%) | Batch |

With batch volume: mean absolute error 15.9%, 7/9 within 20%.
With post-boil volume: mean absolute error 13.1%, 6/9 within 20%.

Neither matches well because the blog uses BeerSmith's fixed defaults (EKG 5.0%, Fuggles ~4.5%) for
all eras. The BeerSmith exports confirm this — Goldings is 5.0% for both 1805 and 1835 recipes.

### What the script does

By default it uses BeerSmith's alpha defaults, so the recipes match what the blog published. The
`--experimental-hop-adjustment` flag switches to era-specific alphas instead. It's worth noting
that the blog's author himself says virtually no logs record hop additions — most timings are guesstimates —
and the hop quantities for non-Barclay Perkins breweries are estimates too. So the era adjustment
is a rough correction on already-approximate data. It moves things in the right direction but
don't mistake it for precision.

Either way, BeerSmith recalculates IBU from the ingredients when you import, and the blog's
reported IBU is saved in the notes for reference. If a hop name includes an explicit alpha %
(e.g. "Goldings 5.5%"), that always takes priority over any lookup.

## Ingredient lookup

The blog gives names and weights but not the brewing-science properties BeerXML needs, so there's a lookup database for:

### Fermentables

| Required field | Description | Example (Pale Malt UK) |
|----------------|-------------|------------------------|
| `<TYPE>` | Grain / Sugar / Extract / Adjunct | Grain |
| `<YIELD>` | Extract potential (%) | 78.0 |
| `<COLOR>` | Colour in SRM | 3.0 |
| `<ORIGIN>` | Country | United Kingdom |
| `<ADD_AFTER_BOIL>` | FALSE for grains | FALSE |

### Hops

| Required field | Description | Example (EKG) |
|----------------|-------------|---------------|
| `<ALPHA>` | Alpha acid % — use era-specific lookup | 5.0 |
| `<USE>` | Boil / Dry Hop / First Wort | Boil |
| `<TYPE>` | Bittering / Aroma / Both | Aroma |
| `<FORM>` | Pellet / Plug / Leaf | Pellet |
