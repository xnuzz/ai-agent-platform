"""Bulgaria market pack: who to target, what to look for, how to stay compliant, how to sell.

Everything Bulgaria-specific lives here so the rest of the agent stays country-neutral.

Market facts this encodes (checked 2026-11):
- Bulgaria adopted the euro on 2026-01-01; the lev stopped being legal tender on 2026-02-01 and mandatory dual
  BGN/EUR price display ended on 2026-08-08. Since then prices must be shown in euro: a small-business site that
  still lists prices only in "лв." is outdated (and a concrete, friendly reason to get in touch).
- Electronic Commerce Act (ЗЕТ, current version ДВ бр. 55/2026):
  * чл. 4, ал. 1: a business website must give permanent access to name, seat/address, phone and e-mail, and
    commercial-register details; ал. 2: shown prices must say whether taxes are included.
  * чл. 6: unsolicited commercial e-mail must be recognisable as such on arrival (ал. 1); to legal entities it is
    allowed unless the address is in the КЗП register (ал. 2-3); to consumers it needs prior consent (ал. 4).
- Only roughly half of Bulgarian small enterprises have a website (NSI/Eurostat; BG ranks at the bottom of the EU
  for business social-media use and e-sales), and many owner-run businesses use a Facebook page or a free
  subdomain instead - the core opportunity.
ponytail: static lists; refresh yearly (chains, free hosts, resort towns).
"""
from __future__ import annotations

import re

COUNTRY = "BG"

# ------------------------------------------------------------------ who to target
# Default niches when a BG task gives no categories: owner-run, local customers, recurring visits, a website or
# booking directly brings revenue, and they can afford EUR 500-2,000.
DEFAULT_CATEGORIES = ["Dentist", "Beauty salon", "Hair salon", "Auto repair", "Tyres", "Guest house", "Restaurant",
                      "Accountant", "Lawyer", "Real estate", "Physiotherapist", "Veterinarian", "Driving school",
                      "Furniture", "Car wash", "Massage", "Language school", "Photographer"]

# Bulgarian category words -> OSM tags (merged into discovery/osm.py CATEGORY_TAGS).
CATEGORY_TAGS: dict[str, list[str]] = {
    "зъболекар": ["amenity=dentist"], "стоматолог": ["amenity=dentist"], "дентален център": ["amenity=dentist"],
    "фризьор": ["shop=hairdresser"], "бръснар": ["shop=hairdresser"], "салон за красота": ["shop=beauty"],
    "козметичен салон": ["shop=beauty"], "маникюр": ["shop=beauty"], "масаж": ["shop=massage"],
    "автосервиз": ["shop=car_repair"], "сервиз": ["shop=car_repair"], "вулканизатор": ["shop=tyres"],
    "гуми": ["shop=tyres"], "автомивка": ["amenity=car_wash"], "автошкола": ["amenity=driving_school"],
    "хотел": ["tourism=hotel"], "семеен хотел": ["tourism=hotel"], "къща за гости": ["tourism=guest_house"],
    "апартаменти": ["tourism=apartment"], "ресторант": ["amenity=restaurant"], "механа": ["amenity=restaurant"],
    "кафене": ["amenity=cafe"], "пекарна": ["shop=bakery"], "сладкарница": ["shop=pastry"],
    "адвокат": ["office=lawyer"], "нотариус": ["office=notary"], "счетоводител": ["office=accountant"],
    "счетоводна къща": ["office=accountant"], "недвижими имоти": ["office=estate_agent"],
    "физиотерапия": ["healthcare=physiotherapist"], "рехабилитация": ["healthcare=physiotherapist"],
    "ветеринар": ["amenity=veterinary"], "ветеринарна клиника": ["amenity=veterinary"],
    "фитнес": ["leisure=fitness_centre"], "йога": ["leisure=fitness_centre"], "мебели": ["shop=furniture"],
    "мебели по поръчка": ["craft=carpenter", "shop=furniture"], "дърводелец": ["craft=carpenter"],
    "фотограф": ["craft=photographer", "shop=photo"], "цветарница": ["shop=florist"], "оптика": ["shop=optician"],
    "езикова школа": ["amenity=language_school"], "школа": ["amenity=language_school"],
    "лекар": ["amenity=doctors"], "клиника": ["amenity=clinic"], "медицински център": ["amenity=clinic"],
    "водопроводчик": ["craft=plumber"], "електротехник": ["craft=electrician"], "ремонти": ["craft=builder"],
    "строителна фирма": ["craft=builder"], "туристическа агенция": ["shop=travel_agency"],
    "химическо чистене": ["shop=dry_cleaning"], "татуировки": ["shop=tattoo"],
}
# English names for niches that the generic table lacks.
EXTRA_TAGS: dict[str, list[str]] = {
    "tyres": ["shop=tyres"], "tires": ["shop=tyres"], "car wash": ["amenity=car_wash"],
    "massage": ["shop=massage"], "language school": ["amenity=language_school"], "notary": ["office=notary"],
    "furniture": ["shop=furniture", "craft=carpenter"], "apartments": ["tourism=apartment"],
    "builder": ["craft=builder"], "construction": ["craft=builder"], "travel agency": ["shop=travel_agency"],
    "pastry": ["shop=pastry"],
}

# Chains and big brands are not small-business clients (OSM `brand*` tags catch most; this catches the rest).
# Exact names only (generic words: "Happy Dental", "Metro Dental", "Zora Beauty" are real small businesses).
CHAINS = {
    "lilly", "dm", "billa", "kaufland", "lidl", "fantastico", "фантастико", "t market", "t-market", "cba", "metro",
    "sopharmacy", "софармаси", "subra", "субра", "remedium", "ремедиум", "марешки", "аптеки марешки", "benu",
    "omv", "shell", "lukoil", "лукойл", "petrol", "петрол", "eko", "еко", "rompetrol", "mcdonald's", "kfc",
    "happy", "хепи", "happy bar & grill", "costa coffee", "starbucks", "aladin foods", "domino's", "telepizza",
    "jumbo", "джъмбо", "praktiker", "mr. bricolage", "technopolis", "технополис", "technomarket", "техномаркет",
    "zora", "jysk", "a1", "vivacom", "виваком", "yettel", "dsk", "банка дск", "unicredit", "уникредит",
    "postbank", "пощенска банка", "fibank", "first investment bank", "ubb", "обб", "econt", "еконт", "speedy",
    "спийди", "raffy", "рафи",
}
# Distinctive brands: also match "<brand> <branch>" ("BILLA Plovdiv", "Аптеки Марешки 12").
CHAIN_PREFIXES = ("billa", "kaufland", "lidl", "fantastico", "фантастико", "sopharmacy", "софармаси", "subra",
                  "субра", "remedium", "ремедиум", "марешки", "аптеки марешки", "technopolis", "технополис",
                  "technomarket", "техномаркет", "lukoil", "лукойл", "rompetrol", "mcdonald's", "starbucks",
                  "telepizza", "praktiker", "vivacom", "виваком", "yettel", "unicredit", "уникредит", "postbank",
                  "fibank", "econt", "еконт", "аптеки лили", "lilly drogerie", "happy bar")

# ------------------------------------------------------------------ what to look for
SOCIAL_HOSTS = ("facebook.com", "fb.com", "fb.me", "instagram.com", "instagr.am", "tiktok.com", "youtube.com",
                "linkedin.com", "wa.me", "linktr.ee", "business.site", "g.page", "google.com", "goo.gl",
                "maps.app.goo.gl", "olx.bg", "bazar.bg", "booking.com", "airbnb.", "pochivka.bg", "nasamnasam.com",
                "superdoc.bg", "zapazi.bg", "fresha.com", "booksy.com", "tripadvisor.", "start.bg", "zlatnite.bg",
                "goldenpages.bg")
FREE_HOSTS = ("hit.bg", "alle.bg", "data.bg", "dir.bg", "free.bg", "gbg.bg", "abv.bg", "blogspot.com",
              "wordpress.com", "wixsite.com", "weebly.com", "webnode.", "jimdofree.com", "jimdosite.com",
              "site123.me", "tripod.com", "ucoz.", "narod.ru", "github.io", "netlify.app", "vercel.app")
TOURIST_TOWNS = {
    "coast": ["варна", "varna", "бургас", "burgas", "несебър", "nessebar", "nesebar", "слънчев бряг", "sunny beach",
              "созопол", "sozopol", "златни пясъци", "golden sands", "балчик", "balchik", "приморско", "primorsko",
              "китен", "kiten", "поморие", "pomorie", "обзор", "obzor", "каварна", "kavarna", "свети влас",
              "sveti vlas", "царево", "tsarevo", "ахтопол", "ahtopol", "албена", "albena",
              "кранево", "kranevo", "шкорпиловци", "shkorpilovtsi", "равда", "ravda"],
    "ski": ["банско", "bansko", "боровец", "borovets", "пампорово", "pamporovo", "чепеларе", "chepelare",
            "добринище", "dobrinishte", "самоков", "samokov", "разлог", "razlog"],
}
ACCOMMODATION_RE = re.compile(r"hotel|guest ?house|apartment|хотел|къща за гости|апартамент|вила|villa|hostel|"
                              r"restaurant|ресторант|механа|\bbar\b|\bбар\b", re.I)

# A price: 25 лв / 1 250,50 лв. / 12.50 BGN - not a phone number before it, not registered capital.
BGN_PRICE_RE = re.compile(r"(?<![\d.,])\d{1,3}(?:[  .]?\d{3})*(?:[.,]\d{1,2})?[  ]?(?:лв\.?|лева|BGN)"
                          r"(?![а-яa-z])", re.I)
CAPITAL_RE = re.compile(r"капитал", re.I)
EUR_RE = re.compile(r"€|\bEUR\b|\beuro\b|\bевро\b(?!\s*\d)", re.I)  # not "Евро 5" (an engine emission standard)
COMPANY_INFO_RE = re.compile(r"ЕИК|БУЛСТАТ|\bUIC\b|ДДС|\bBG\d{9,10}\b|\b(?:Е?ООД|ЕАД|АД|ЕТ|E?OOD|EAD|Ltd\.?)\b",
                             re.I)
PRIVACY_RE = re.compile(r"поверителност|лични(те)?\s+данни|защита\s+на\s+(лични(те)?\s+)?данни|бисквитки|privacy|"
                        r"cookie|gdpr|politika|poveritelnost|lichni|danni", re.I)
BOOKING_RE = re.compile(r"запази(те)?\s+час|запиш(и|ете)\s+(се|час)|онлайн\s+(записване|резервация)|резерв(ац|ир)|"
                        r"superdoc|zapazi|schedulo", re.I)
BOOKING_CATEGORIES = re.compile(r"зъб|стомат|дентал|лекар|клиник|медицин|физио|рехаб|фризьор|бръснар|салон|"
                                r"козмет|маникюр|масаж|ресторант|механа|хотел|къща за гости|фитнес|йога|ветерин|"
                                r"автошкол|фотограф|оптик|автосервиз|вулканиз|tyre|car repair|car wash|автомивка",
                                re.I)
MOBILE_RE = re.compile(r"^(?:\+?359|0)8[789]\d{7}$|^(?:\+?359|0)9[89]\d{7}$")


def host_of(url: str) -> str:
    h = (url or "").lower().split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return h[4:] if h.startswith("www.") else h


def _matches_host(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == s or host.endswith("." + s) or (s.endswith(".") and s in host) for s in suffixes)


def is_social_only(url: str) -> bool:
    """The 'website' is a social / marketplace / maps page, not the business's own site."""
    return bool(url) and _matches_host(host_of(url), SOCIAL_HOSTS)


def is_free_host(url: str) -> bool:
    h = host_of(url)
    return any(h.endswith("." + s) or (s.endswith(".") and s in h) for s in FREE_HOSTS)


def is_chain(name: str, tags: dict | None = None) -> bool:
    tags = tags or {}
    if any(k in tags for k in ("brand", "brand:wikidata", "brand:wikipedia", "operator:wikidata")):
        return True
    n = re.sub(r"\s+", " ", (name or "").strip().lower()).replace("’", "'")
    return n in CHAINS or any(n == c or n.startswith(c + " ") for c in CHAIN_PREFIXES)


def normalize_phone(phone: str) -> str:
    """'032 123 456' / '+359 88 123 4567' -> '+35932123456' / '+359881234567' (first number only)."""
    first = re.split(r"[;,/|\n]|\s{2,}|\sили\s", (phone or "").strip())[0]
    digits = re.sub(r"[^\d+]", "", first.replace("(0)", ""))
    if digits.startswith("00359"):
        digits = "+" + digits[2:]
    elif digits.startswith("0") and len(digits) >= 8:
        digits = "+359" + digits[1:]
    elif digits.startswith("359"):
        digits = "+" + digits
    digits = re.sub(r"^\+3590", "+359", digits)
    return digits if re.fullmatch(r"\+359\d{8,9}", digits) else (phone or "").strip()


def is_mobile(phone: str) -> bool:
    """Bulgarian mobile numbers (087/088/089/098/099) - on a listing this usually means an owner-run business."""
    return bool(MOBILE_RE.match(normalize_phone(phone).replace("+", "")))


def season(city: str, category: str) -> str:
    """'coast' / 'ski' for accommodation & food businesses in resort towns, else ''."""
    if not ACCOMMODATION_RE.search(category or ""):
        return ""
    c = (city or "").lower().strip()
    for kind, towns in TOURIST_TOWNS.items():
        if any(re.search(rf"(^|[\s,(]){re.escape(t)}($|[\s,)])", c) for t in towns):
            return kind
    return ""


def page_findings(text: str, links: list[tuple[str, str]], charset: str) -> dict[str, dict]:
    """BG website checks on homepage (+ contact page) text -> {code: facts}."""
    out: dict[str, dict] = {}
    bgn = [m.group(0) for m in BGN_PRICE_RE.finditer(text)
           if not CAPITAL_RE.search(text[max(0, m.start() - 25):m.start()])]
    if bgn and not EUR_RE.search(text):
        out["PRICES_IN_BGN"] = {"examples": [b.strip() for b in bgn[:3]]}
    if not COMPANY_INFO_RE.search(text):
        out["MISSING_COMPANY_INFO"] = {"checked": "ЕИК/БУЛСТАТ, VAT number or legal form (ООД, ЕООД, АД, ЕТ)"}
    hay = " ".join(f"{h} {t}" for h, t in links)
    if not PRIVACY_RE.search(hay) and not PRIVACY_RE.search(text[-5000:]):
        out["NO_PRIVACY_POLICY"] = {"checked": "links to a privacy / cookie policy"}
    if charset.lower().replace("_", "-") in ("windows-1251", "cp1251"):
        out["OUTDATED_DESIGN"] = {"charset": charset}
    return out


# ------------------------------------------------------------------ compliance + selling
LEGAL_ENTITY_NOTE = ("Bulgaria (ЗЕТ чл. 6): unsolicited commercial e-mail to a legal entity is allowed unless the "
                     "address is in the КЗП register of addresses that refuse it - check kzp.bg (or add the "
                     "register to the suppression list) before sending; the subject marks the message as a "
                     "commercial communication (чл. 6, ал. 1). Agent assessment, not legal advice.")
PERSON_NOTE = ("Bulgaria (ЗЕТ чл. 6, ал. 4): this looks like a personal / free-mail address (likely a sole trader "
               "or a natural person); commercial e-mail to consumers needs prior consent. Phone the business "
               "instead, or confirm consent before sending.")
FREE_MAIL = ("abv.bg", "mail.bg", "gmail.com", "yahoo.com", "dir.bg", "hotmail.com", "outlook.com", "icloud.com")
SUBJECT_PREFIX = "Търговско предложение"   # чл. 6, ал. 1: recognisable as a commercial message on arrival

RECURRING = ("Recurring revenue to offer after launch (typical BG prices, excl. VAT): .bg domain ~EUR 25-35/year, "
             "hosting ~EUR 50-120/year, maintenance & small edits ~EUR 30-80/month.")
SEASON_TIPS = {
    "coast": ("Black Sea season runs June-September: pitch now so a site with direct booking is live by April-May; "
              "every direct booking avoids the Booking.com commission (typically 15% or more)."),
    "ski": ("Ski season runs December-March: pitch in summer/autumn so direct booking is live by November; every "
            "direct booking avoids the Booking.com commission (typically 15% or more)."),
}
EURO_TIP = ("Since 8 Aug 2026 prices must be shown in euro only - updating the price list is an easy, low-risk first "
            "job that opens the door to a bigger project.")
