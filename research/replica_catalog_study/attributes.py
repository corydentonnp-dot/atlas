"""Attribute extraction from listing titles and detail-page text.

Replica catalog listings pack most design information into the product title
(e.g. brand, model family, reference, diameter, dial color, movement). These
extractors turn that free text into the structured research schema. All
functions are pure and unit-testable.
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------
# Brand lexicon: canonical brand -> alias patterns (case-insensitive).
# --------------------------------------------------------------------------
BRAND_ALIASES: dict[str, list[str]] = {
    "Rolex": [r"\brolex\b"],
    "Omega": [r"\bomega\b"],
    "Patek Philippe": [r"\bpatek(?:\s+philippe)?\b", r"\bpp\b(?=.*\b(nautilus|aquanaut))"],
    "Audemars Piguet": [r"\baudemars(?:\s+piguet)?\b", r"\bap\b(?=.*\broyal\s+oak\b)"],
    "Panerai": [r"\bpanerai\b", r"\bofficine\s+panerai\b", r"\bpam\s?\d+"],
    "Hublot": [r"\bhublot\b"],
    "IWC": [r"\biwc\b", r"\bschaffhausen\b"],
    "Cartier": [r"\bcartier\b"],
    "Breitling": [r"\bbreitling\b"],
    "TAG Heuer": [r"\btag\s*heuer\b", r"\bheuer\b"],
    "Tudor": [r"\btudor\b"],
    "Richard Mille": [r"\brichard\s+mille\b", r"\brm[\s-]?\d{2,3}\b"],
    "Vacheron Constantin": [r"\bvacheron(?:\s+constantin)?\b"],
    "A. Lange & Söhne": [r"\ba\.?\s*lange\b", r"\blange\s*&\s*s(?:o|ö)hne\b"],
    "Jaeger-LeCoultre": [r"\bjaeger\b", r"\bjlc\b", r"\blecoultre\b"],
    "Blancpain": [r"\bblancpain\b"],
    "Breguet": [r"\bbreguet\b"],
    "Chopard": [r"\bchopard\b"],
    "Franck Muller": [r"\bfranck\s+muller\b"],
    "Longines": [r"\blongines\b"],
    "Zenith": [r"\bzenith\b"],
    "Girard-Perregaux": [r"\bgirard\b"],
    "Ulysse Nardin": [r"\bulysse\b"],
    "Glashütte Original": [r"\bglash(?:u|ü)tte\b"],
    "Piaget": [r"\bpiaget\b"],
    "Bell & Ross": [r"\bbell\s*&\s*ross\b", r"\bbr[\s-]?0[135]\b"],
    "Bvlgari": [r"\bb[vu]lgari\b"],
    "Montblanc": [r"\bmont\s?blanc\b"],
    "Rado": [r"\brado\b"],
    "Roger Dubuis": [r"\broger\s+dubuis\b"],
    "Parmigiani": [r"\bparmigiani\b"],
    "H. Moser & Cie": [r"\bmoser\b"],
    "Grand Seiko": [r"\bgrand\s+seiko\b"],
    "Seiko": [r"\bseiko\b"],
    "Oris": [r"\boris\b"],
    "Sinn": [r"\bsinn\b"],
    "Corum": [r"\bcorum\b"],
    "Graham": [r"\bgraham\b"],
    "Porsche Design": [r"\bporsche\b"],
    "U-Boat": [r"\bu-?boat\b"],
    "Jacob & Co": [r"\bjacob\s*(?:&|and)\s*co\b"],
    "Hermès": [r"\bherm(?:e|è)s\b"],
    "Chanel": [r"\bchanel\b"],
    "Dior": [r"\bdior\b"],
    "Louis Vuitton": [r"\blouis\s+vuitton\b"],
    "Gucci": [r"\bgucci\b"],
    "Versace": [r"\bversace\b"],
    "Nomos": [r"\bnomos\b"],
    "Maurice Lacroix": [r"\bmaurice\s+lacroix\b"],
    "Baume & Mercier": [r"\bbaume\b"],
    "Raymond Weil": [r"\braymond\s+weil\b"],
    "MB&F": [r"\bmb&f\b"],
    "Greubel Forsey": [r"\bgreubel\b"],
}

# --------------------------------------------------------------------------
# Model families per brand: canonical family -> alias patterns.
# --------------------------------------------------------------------------
MODEL_FAMILIES: dict[str, dict[str, list[str]]] = {
    "Rolex": {
        "Submariner": [r"\bsubmariner\b", r"\bsub\b"],
        "Daytona": [r"\bdaytona\b", r"\bcosmograph\b"],
        "Datejust": [r"\bdatejust\b", r"\bdate\s?just\b"],
        "Day-Date": [r"\bday[\s-]?date\b", r"\bpresident\b"],
        "GMT-Master": [r"\bgmt[\s-]?master\b"],
        "Explorer": [r"\bexplorer\b"],
        "Sea-Dweller": [r"\bsea[\s-]?dweller\b"],
        "Deepsea": [r"\bdeep\s?sea\b"],
        "Yacht-Master": [r"\byacht[\s-]?master\b"],
        "Oyster Perpetual": [r"\boyster\s+perpetual\b"],
        "Milgauss": [r"\bmilgauss\b"],
        "Air-King": [r"\bair[\s-]?king\b"],
        "Sky-Dweller": [r"\bsky[\s-]?dweller\b"],
        "Cellini": [r"\bcellini\b"],
        "1908": [r"\b1908\b"],
    },
    "Omega": {
        "Speedmaster": [r"\bspeedmaster\b", r"\bmoonwatch\b"],
        "Seamaster Diver 300M": [r"\bdiver\s*300\b", r"\bseamaster\s*300m\b"],
        "Seamaster Planet Ocean": [r"\bplanet\s+ocean\b"],
        "Seamaster Aqua Terra": [r"\baqua\s+terra\b"],
        "Seamaster": [r"\bseamaster\b"],
        "Constellation": [r"\bconstellation\b"],
        "De Ville": [r"\bde\s?ville\b"],
        "Railmaster": [r"\brailmaster\b"],
    },
    "Patek Philippe": {
        "Nautilus": [r"\bnautilus\b"],
        "Aquanaut": [r"\baquanaut\b"],
        "Calatrava": [r"\bcalatrava\b"],
        "Perpetual Calendar": [r"\bperpetual\s+calendar\b"],
        "Grand Complications": [r"\bgrand\s+complication"],
        "Golden Ellipse": [r"\bellipse\b"],
        "Gondolo": [r"\bgondolo\b"],
    },
    "Audemars Piguet": {
        "Royal Oak Offshore": [r"\boffshore\b"],
        "Royal Oak Concept": [r"\bconcept\b"],
        "Royal Oak": [r"\broyal\s+oak\b"],
        "Code 11.59": [r"\bcode\s*11\.?59\b"],
    },
    "Panerai": {
        "Luminor": [r"\bluminor\b"],
        "Radiomir": [r"\bradiomir\b"],
        "Submersible": [r"\bsubmersible\b"],
    },
    "Cartier": {
        "Santos": [r"\bsantos\b"],
        "Tank": [r"\btank\b"],
        "Ballon Bleu": [r"\bballon\s+bleu\b"],
        "Panthère": [r"\bpanth(?:e|è)re\b"],
        "Pasha": [r"\bpasha\b"],
        "Drive": [r"\bdrive\b"],
        "Ronde": [r"\bronde\b"],
        "Cle": [r"\bcl(?:e|é)\b"],
    },
    "IWC": {
        "Portugieser": [r"\bportugieser\b", r"\bportuguese\b"],
        "Big Pilot": [r"\bbig\s+pilot\b"],
        "Pilot": [r"\bpilot'?s?\b", r"\bmark\s+x{0,3}v?i{0,3}\b", r"\btop\s?gun\b"],
        "Portofino": [r"\bportofino\b"],
        "Aquatimer": [r"\baquatimer\b"],
        "Ingenieur": [r"\bingenieur\b"],
        "Da Vinci": [r"\bda\s?vinci\b"],
    },
    "Hublot": {
        "Big Bang": [r"\bbig\s+bang\b"],
        "Classic Fusion": [r"\bclassic\s+fusion\b"],
        "Spirit of Big Bang": [r"\bspirit\s+of\b"],
        "MP": [r"\bmp[\s-]?\d{2}\b"],
    },
    "Breitling": {
        "Navitimer": [r"\bnavitimer\b"],
        "Superocean": [r"\bsuper\s?ocean\b"],
        "Avenger": [r"\bavenger\b"],
        "Chronomat": [r"\bchronomat\b"],
        "Premier": [r"\bpremier\b"],
        "Endurance Pro": [r"\bendurance\b"],
    },
    "TAG Heuer": {
        "Carrera": [r"\bcarrera\b"],
        "Monaco": [r"\bmonaco\b"],
        "Aquaracer": [r"\baquaracer\b"],
        "Autavia": [r"\bautavia\b"],
        "Formula 1": [r"\bformula\s*1\b"],
    },
    "Tudor": {
        "Black Bay": [r"\bblack\s+bay\b", r"\bbb58\b"],
        "Pelagos": [r"\bpelagos\b"],
        "Royal": [r"\btudor\s+royal\b"],
        "1926": [r"\b1926\b"],
        "Ranger": [r"\branger\b"],
    },
    "Vacheron Constantin": {
        "Overseas": [r"\boverseas\b"],
        "Patrimony": [r"\bpatrimony\b"],
        "Traditionnelle": [r"\btraditionnelle\b"],
        "Historiques": [r"\bhistoriques\b", r"\b222\b"],
        "Fiftysix": [r"\bfifty\s?six\b"],
    },
    "Jaeger-LeCoultre": {
        "Reverso": [r"\breverso\b"],
        "Master": [r"\bmaster\b"],
        "Polaris": [r"\bpolaris\b"],
    },
    "Blancpain": {
        "Fifty Fathoms": [r"\bfifty\s+fathoms\b"],
        "Villeret": [r"\bvilleret\b"],
    },
    "Richard Mille": {
        "RM": [r"\brm[\s-]?\d{2,3}\b"],
    },
    "Franck Muller": {
        "Vanguard": [r"\bvanguard\b"],
        "Cintrée Curvex": [r"\bcurvex\b", r"\bcintr(?:e|é)e\b"],
        "Crazy Hours": [r"\bcrazy\s+hours\b"],
    },
    "Longines": {
        "Master Collection": [r"\bmaster\b"],
        "HydroConquest": [r"\bhydro\s?conquest\b"],
        "Conquest": [r"\bconquest\b"],
        "Spirit": [r"\bspirit\b"],
        "Legend Diver": [r"\blegend\s+diver\b"],
    },
    "Zenith": {
        "El Primero": [r"\bel\s+primero\b"],
        "Chronomaster": [r"\bchronomaster\b"],
        "Defy": [r"\bdefy\b"],
        "Pilot": [r"\bpilot\b"],
    },
    "Bvlgari": {
        "Octo": [r"\bocto\b"],
        "Serpenti": [r"\bserpenti\b"],
        "Diagono": [r"\bdiagono\b"],
    },
}

# --------------------------------------------------------------------------
# Case shapes. Round is the overwhelming default; only claim a non-round
# shape on positive evidence (keyword or model family known to be non-round).
# --------------------------------------------------------------------------
SHAPE_KEYWORDS: dict[str, list[str]] = {
    "tonneau": [r"\btonneau\b", r"\bbarrel[\s-]shaped\b"],
    "rectangular": [r"\brectangular\b", r"\brectangle\b"],
    "square": [r"\bsquare\b"],
    "cushion": [r"\bcushion\b"],
    "octagonal": [r"\boctagon(?:al)?\b"],
    "oval": [r"\boval\b"],
    "round": [r"\bround\b"],
}

FAMILY_SHAPES: dict[tuple[str, str], str] = {
    ("Cartier", "Tank"): "rectangular",
    ("Cartier", "Santos"): "square",
    ("Cartier", "Panthère"): "square",
    ("Jaeger-LeCoultre", "Reverso"): "rectangular",
    ("Audemars Piguet", "Royal Oak"): "octagonal",
    ("Audemars Piguet", "Royal Oak Offshore"): "octagonal",
    ("Richard Mille", "RM"): "tonneau",
    ("Franck Muller", "Cintrée Curvex"): "tonneau",
    ("Franck Muller", "Vanguard"): "tonneau",
    ("TAG Heuer", "Monaco"): "square",
    ("Panerai", "Luminor"): "cushion",
    ("Panerai", "Radiomir"): "cushion",
    ("Panerai", "Submersible"): "cushion",
    ("Bvlgari", "Octo"): "octagonal",
    ("Patek Philippe", "Gondolo"): "rectangular",
    ("Patek Philippe", "Golden Ellipse"): "oval",
    ("Rolex", "Cellini"): "round",
}

CASE_MATERIALS: dict[str, list[str]] = {
    "stainless steel": [r"\bstainless\b", r"\b904\s?l\b", r"\b316\s?l\b", r"\bss\b", r"\bsteel\b"],
    "yellow gold": [r"\byellow\s+gold\b", r"\byg\b", r"\b18k\s+gold\b"],
    "rose gold": [r"\brose\s+gold\b", r"\beverose\b", r"\bpink\s+gold\b", r"\brg\b"],
    "white gold": [r"\bwhite\s+gold\b", r"\bwg\b"],
    "two-tone": [r"\btwo[\s-]?tone\b", r"\bwrapped\b", r"\brolesor\b", r"\bss/gold\b"],
    "titanium": [r"\btitanium\b", r"\btitanio\b"],
    "ceramic": [r"\bceramic\s+case\b", r"\bfull\s+ceramic\b"],
    "platinum": [r"\bplatinum\b", r"\b950\b"],
    "bronze": [r"\bbronze\b", r"\bbronzo\b"],
    "carbon": [r"\bcarbon\b", r"\bcarbotech\b", r"\bntpt\b"],
    "pvd/dlc": [r"\bpvd\b", r"\bdlc\b", r"\bblacksteel\b"],
    "sapphire": [r"\bsapphire\s+case\b", r"\bfull\s+sapphire\b"],
}

DIAL_COLORS = [
    "ice blue", "tiffany", "mother of pearl", "meteorite", "salmon", "champagne",
    "chocolate", "anthracite", "rhodium", "slate", "olive", "turquoise",
    "black", "white", "blue", "green", "silver", "grey", "gray", "gold",
    "brown", "purple", "pink", "red", "yellow", "orange", "cream", "ivory",
]

DIAL_CHARACTERISTICS: dict[str, list[str]] = {
    "sunburst": [r"\bsunburst\b", r"\bsunray\b"],
    "skeleton": [r"\bskeleton(?:ized)?\b", r"\bopenwork(?:ed)?\b", r"\bhollow\b"],
    "gem-set": [r"\bdiamond\b", r"\bgem[\s-]?set\b", r"\bpav(?:e|é)\b", r"\bbaguette\b",
                r"\biced\b", r"\brainbow\b"],
    "roman numerals": [r"\broman\b"],
    "arabic numerals": [r"\barabic\b", r"\bcalifornia\b"],
    "tapisserie": [r"\btapisserie\b", r"\bwaffle\b"],
    "guilloché": [r"\bguilloch(?:e|é)\b"],
    "panda": [r"\bpanda\b"],
    "textured": [r"\btextured\b", r"\bhobnail\b", r"\bhoneycomb\b", r"\blinen\b",
                 r"\bpalm\b", r"\bfluted\s+motif\b"],
    "luminous": [r"\bluminous\b", r"\blume\b", r"\bchromalight\b", r"\bsuper\s?luminova\b"],
    "enamel": [r"\benamel\b"],
    "lacquer": [r"\blacquer(?:ed)?\b"],
}

COMPLICATIONS: dict[str, list[str]] = {
    "chronograph": [r"\bchronograph\b", r"\bchrono\b", r"\bflyback\b"],
    "gmt/dual time": [r"\bgmt\b", r"\bdual\s+time\b", r"\btwo\s+time\s+zone", r"\butc\b"],
    "world time": [r"\bworld\s?tim(?:e|er)\b"],
    "moonphase": [r"\bmoon\s?phase\b", r"\bmoon\b"],
    "tourbillon": [r"\btourbillon\b"],
    "perpetual calendar": [r"\bperpetual\s+calendar\b", r"\bqp\b"],
    "annual calendar": [r"\bannual\s+calendar\b"],
    "complete calendar": [r"\btriple\s+calendar\b", r"\bcomplete\s+calendar\b"],
    "day-date": [r"\bday[\s-]date\b"],
    "date": [r"\bdate\b", r"\bdatejust\b"],
    "power reserve": [r"\bpower\s+reserve\b", r"\breserve\s+de\s+marche\b"],
    "minute repeater": [r"\brepeater\b"],
    "alarm": [r"\balarm\b"],
    "regatta timer": [r"\bregatta\b"],
    "equation of time": [r"\bequation\s+of\s+time\b"],
    "diving bezel": [r"\bdive\s+bezel\b", r"\bunidirectional\b"],
}

BRACELET_TYPES: dict[str, list[str]] = {
    "oyster bracelet": [r"\boyster\s+(?:bracelet|band)\b"],
    "jubilee bracelet": [r"\bjubilee\b"],
    "president bracelet": [r"\bpresident\s+(?:bracelet|band)\b"],
    "metal bracelet": [r"\bbracelet\b", r"\bss\s+band\b", r"\bsteel\s+band\b",
                       r"\bmetal\s+band\b", r"\btitanium\s+band\b"],
    "leather strap": [r"\bleather\b", r"\balligator\b", r"\bcroco", r"\bcalfskin\b",
                      r"\bcordovan\b"],
    "rubber strap": [r"\brubber\b", r"\bsilicone\b", r"\bcaoutchouc\b", r"\boysterflex\b"],
    "nato/fabric strap": [r"\bnato\b", r"\bcanvas\b", r"\bfabric\b", r"\btextile\b",
                          r"\bvelcro\b"],
    "mesh bracelet": [r"\bmesh\b", r"\bmilanese\b"],
    "ceramic bracelet": [r"\bceramic\s+(?:bracelet|band)\b"],
}

MOVEMENT_CATEGORIES: dict[str, list[str]] = {
    "quartz": [r"\bquartz\b", r"\bronda\b", r"\beta\s+25\d\d\b"],
    "manual wind": [r"\bmanual\b", r"\bhand[\s-]?wind(?:ing)?\b", r"\bhand\s+wound\b"],
    "automatic": [r"\bautomatic\b", r"\bself[\s-]?winding\b", r"\bauto\b"],
}

# Clone/base movement identifiers (used to refine movement classification).
MOVEMENT_BASES: dict[str, list[str]] = {
    "clone of genuine caliber": [
        r"\b(?:sa|a|vr|vs|dd)?[\s-]?3135\b", r"\b3235\b", r"\b3186\b", r"\b3285\b",
        r"\b4130\b", r"\b4131\b", r"\b2836-2\b", r"\b3255\b", r"\b2824-2\b",
        r"\b8500\b", r"\b8800\b", r"\b8900\b", r"\b9300\b", r"\b9900\b", r"\b3861\b",
        r"\b1861\b", r"\bcal\.?\s*324\b", r"\b324\s?sc\b", r"\b26-330\b", r"\b5134\b",
        r"\b3120\b", r"\b3126\b", r"\bp\.9(?:00[01]|010)\b", r"\bmiyota\s+82",
        r"\bclone\b", r"\bsuper\s?clone\b",
    ],
    "ETA/Sellita base": [r"\beta\b", r"\bsellita\b", r"\bsw[\s-]?[23]00\b", r"\b2836\b",
                         r"\b2824\b", r"\b7750\b", r"\b6497\b", r"\b6498\b"],
    "Miyota base": [r"\bmiyota\b", r"\b9015\b", r"\b8215\b"],
    "Seagull/Asian base": [r"\bseagull\b", r"\bsea-?gull\b", r"\basian\b", r"\bst21\d\d\b",
                           r"\bdg28\d\d\b"],
}

_MM = r"(\d{2}(?:[.,]\d{1,2})?)\s*(?:mm|㎜)"
DIAMETER_RE = re.compile(
    r"(?:case\s*(?:size|diameter|width)\s*[:：]?\s*)?" + _MM, re.IGNORECASE
)
DIAMETER_LABELED_RE = re.compile(
    r"(?:diameter|case\s*size|case\s*width|size)\s*[:：]?\s*" + _MM, re.IGNORECASE
)
THICKNESS_RE = re.compile(
    r"(?:thick(?:ness)?|height)\s*[:：]?\s*" + _MM + r"|" + _MM + r"\s*thick", re.IGNORECASE
)
DIMENSION_PAIR_RE = re.compile(
    r"(\d{2}(?:[.,]\d{1,2})?)\s*[x×*]\s*(\d{2}(?:[.,]\d{1,2})?)\s*mm", re.IGNORECASE
)

# Reference numbers, e.g. 116610LN, 126334, PAM01312, 15400ST, 5711/1A, 311.30.42.30
REFERENCE_RE = re.compile(
    r"\b("
    r"pam\s?0?\d{3,5}"
    r"|rm[\s-]?\d{2,3}(?:-\d{2})?"
    r"|\d{4,6}\s?[a-z]{1,4}(?:\b|(?=\d))"
    r"|\d{4,6}/\d{1,4}[a-z]{0,3}(?:-\d{3,4})?"
    r"|\d{3}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{3}"
    r"|iw\d{6}"
    r"|m\d{5}-\d{4}"
    r"|\d{5,6}"
    r")\b",
    re.IGNORECASE,
)

PRICE_RE = re.compile(r"(?:us?\$|\$|usd\s?)\s?([\d,]+(?:\.\d{2})?)", re.IGNORECASE)

YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-2]\d)\s*(?:model|version|edition|release|new)\b|"
                     r"\b(?:new|released?|updated?)\s*(?:in\s+)?(19[5-9]\d|20[0-2]\d)\b",
                     re.IGNORECASE)


def _match_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def extract_brand(text: str) -> str | None:
    for brand, patterns in BRAND_ALIASES.items():
        if _match_any(text, patterns):
            return brand
    return None


def extract_model_family(text: str, brand: str | None) -> str | None:
    if brand and brand in MODEL_FAMILIES:
        for family, patterns in MODEL_FAMILIES[brand].items():
            if _match_any(text, patterns):
                return family
    return None


def extract_reference(text: str) -> str | None:
    # Strip diameter/price-looking tokens first to reduce false positives.
    cleaned = DIAMETER_RE.sub(" ", text)
    cleaned = PRICE_RE.sub(" ", cleaned)
    m = REFERENCE_RE.search(cleaned)
    return m.group(1).upper().replace(" ", "") if m else None


def extract_diameter_mm(text: str) -> float | None:
    m = DIAMETER_LABELED_RE.search(text)
    if not m:
        pair = DIMENSION_PAIR_RE.search(text)
        if pair:
            return _plausible_diameter(pair.group(1))
        m = DIAMETER_RE.search(text)
    if not m:
        return None
    return _plausible_diameter(m.group(1))


def _plausible_diameter(raw: str) -> float | None:
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    return value if 18.0 <= value <= 60.0 else None


def extract_thickness_mm(text: str) -> float | None:
    m = THICKNESS_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    return value if 3.0 <= value <= 25.0 else None


def extract_case_shape(text: str, brand: str | None, family: str | None) -> str | None:
    for shape, patterns in SHAPE_KEYWORDS.items():
        if _match_any(text, patterns):
            return shape
    if brand and family and (brand, family) in FAMILY_SHAPES:
        return FAMILY_SHAPES[(brand, family)]
    if brand and family:
        return "round"  # known family with no non-round evidence
    return None


def extract_case_material(text: str) -> str | None:
    # Two-tone first (it would otherwise also match steel/gold), then golds
    # before generic steel.
    order = ["two-tone", "rose gold", "yellow gold", "white gold", "platinum",
             "titanium", "bronze", "carbon", "sapphire", "ceramic", "pvd/dlc",
             "stainless steel"]
    for material in order:
        if _match_any(text, CASE_MATERIALS[material]):
            return material
    return None


def extract_dial_color(text: str) -> str | None:
    lowered = text.lower()
    # Prefer a color that appears immediately before "dial"/"face".
    m = re.search(r"([a-zéè ]{3,20})\s+(?:dial|face)\b", lowered)
    if m:
        segment = m.group(1)
        for color in DIAL_COLORS:
            if color in segment:
                return "grey" if color == "gray" else color
    for color in DIAL_COLORS:
        if re.search(rf"\b{re.escape(color)}\b", lowered):
            return "grey" if color == "gray" else color
    return None


def extract_dial_characteristics(text: str) -> list[str]:
    return sorted(k for k, pats in DIAL_CHARACTERISTICS.items() if _match_any(text, pats))


def extract_complications(text: str) -> list[str]:
    found = {k for k, pats in COMPLICATIONS.items() if _match_any(text, pats)}
    if "day-date" in found:
        found.discard("date")
    if "perpetual calendar" in found or "annual calendar" in found:
        found.discard("date")
    return sorted(found)


def extract_bracelet_type(text: str) -> str | None:
    order = ["oyster bracelet", "jubilee bracelet", "president bracelet",
             "ceramic bracelet", "mesh bracelet", "rubber strap",
             "nato/fabric strap", "leather strap", "metal bracelet"]
    for kind in order:
        if _match_any(text, BRACELET_TYPES[kind]):
            return kind
    return None


def extract_movement(text: str) -> tuple[str | None, str | None]:
    """Return (movement_category, movement_base)."""
    base = None
    for kind, patterns in MOVEMENT_BASES.items():
        if _match_any(text, patterns):
            base = kind
            break
    category = None
    for kind in ("quartz", "manual wind", "automatic"):
        if _match_any(text, MOVEMENT_CATEGORIES[kind]):
            category = kind
            break
    if category is None and base in ("clone of genuine caliber", "ETA/Sellita base",
                                     "Miyota base", "Seagull/Asian base"):
        category = "automatic"  # dominant default for mechanical clone bases
    return category, base


def extract_price_usd(text: str) -> float | None:
    m = PRICE_RE.search(text)
    if not m:
        return None
    try:
        value = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return value if 0 < value < 100_000 else None


def extract_listed_year(text: str) -> int | None:
    m = YEAR_RE.search(text)
    if not m:
        return None
    return int(m.group(1) or m.group(2))
