# Fetch Barclay Perkins - Historical British Beers

Convert Ron Pattinson's [Barclay Perkins blog](https://barclayperkins.blogspot.com/) "Let's Brew" recipes into BeerXML files that can be imported into BeerSmith and other brewing software.

The blog has over 1,000 scaled homebrew recipes covering everything from Victorian IPAs to wartime mild ales, transcribed from original brewing logs dating back to the 1800s. This project scrapes those recipes and produces proper BeerXML 1.0 files ready for brewing.

## Usage

```
python3 fetch-barclay-perkins.py                                # Default: fetch all, full notes
python3 fetch-barclay-perkins.py --limit 5                      # Test with 5 recipes
python3 fetch-barclay-perkins.py --notes minimal                # Stats only, no blog text
python3 fetch-barclay-perkins.py --combined                     # Single combined XML file
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--notes` | `full` | Notes detail: `full` (includes blog narrative) or `minimal` (stats only) |
| `--output` | `output` | Output directory |
| `--limit` | `0` (all) | Limit number of recipes fetched |
| `--start` | `1` | Start from a specific feed page index |
| `--combined` | off | Write all recipes to a single `recipes.xml` instead of individual files |
| `--year-first` | off | Put year at start of filenames (`1949_Youngs_Stout.xml` instead of `Youngs_Stout_1949.xml`) |
| `--experimental-hop-adjustment` | off | Use era-adjusted hop alpha acids instead of BeerSmith defaults (see below) |

### Output

Recipes are written as individual BeerXML files:

```
output/
  beerxml/
    Barclay_Perkins_Ale_4d_1935.xml
    William_Younger_No_3_Btlg_1949.xml
    ...
```

## What's in each recipe

- **Grain bill** from the original brewing log, classified into BeerXML fermentable types
- **Hop schedule** with weights from the brewing log
- **Mash profile** using the blog's BeerSmith settings, with per-recipe mash and sparge temperatures where the blog specifies them
- **Fermentation** defaults from the blog's BeerSmith profile (2-stage, 4 days primary, 10 days secondary)
- **Yeast** inferred from the brewery (e.g. WLP028 Edinburgh Ale for William Younger recipes)
- **Notes** including the blog's reported IBU/SRM/ABV, attenuation, pitching temperature, blog tags, and optionally the full narrative text from the post

## Ingredient assumptions

The blog recipes use ingredient names as they appear in original brewing logs, which don't always map cleanly to modern BeerXML fermentable names. The script classifies each ingredient into one of three tiers:

- **Confident match** — e.g. "pale malt" → Pale Malt (2 Row) UK, "No. 3 invert" → No. 3 Invert Sugar. No note in the recipe.
- **Inferred match** — genuinely ambiguous names where we've made a reasonable interpretation, e.g. "grits" → Corn Grits (could be rice or oat grits), "SA malt" → Pale Malt. Noted in the recipe's Assumptions section as `interpreted as ...`.
- **Unknown** — names we can't confidently map. These appear as `UNKNOWN: ...` in the recipe with a generic 70% yield fallback. Currently only two remain: "Beane's grist" (an obscure historical ingredient) and "Fuggles hop back" (a misclassified hop addition in the source data).

Assumptions are listed in each recipe's `<NOTES>` field under `--- Assumptions ---`.

## Experimental: era-adjusted hop alpha acids

The blog uses BeerSmith's modern default alpha acid values for all recipes regardless of era (e.g. Fuggles 4.5%, Goldings 5.0%). As noted in the author's books, the hop quantities come from the original logs but no attempt is made to account for how hops have changed over time. The author also points out that virtually no brewing logs record hop additions — most timings are estimates — and that getting a perfect match for 19th century malt is equally tricky.

With all those caveats in mind, the `--experimental-hop-adjustment` flag generates recipes with era-appropriate alpha acid values instead of BeerSmith defaults. Hop alpha levels have genuinely changed — Fuggles ranged from ~5.5% pre-1940 down to ~4.2% in the 1970s — but given the uncertainty in the underlying hop data, this is a rough directional correction rather than a precise one. Where the blog already specifies an alpha acid value for a hop, that value is used regardless of mode — the adjustment only applies to hops listed without a specific percentage.

When the flag is used, output goes into a separate subdirectory:

```
output/
  beerxml-experimental-hop-adjustment/
    Barclay_Perkins_Ale_4d_1935.xml
    William_Younger_No_3_Btlg_1949.xml
    ...
```

## Requirements

- Python 3.6+
- `curl` (used for fetching; no third-party Python packages required)

## Data source

All recipes are by [Ron Pattinson](https://barclayperkins.blogspot.com/), derived from original brewery records. The blog posts and recipe data remain his work. This tool simply converts them into a format suitable for brewing software.

His books on historical brewing are available at the [book shop](https://barclayperkins.blogspot.com/p/book-shop.html).
