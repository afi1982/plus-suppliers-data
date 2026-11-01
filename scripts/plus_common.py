"""Shared helpers for suppliers.json: Hebrew wording, size ranks, quality/trend scores, merge."""
import re, math, datetime

CATEGORIES = [
    {"id": "tees", "he": "חולצות וטישירטים"}, {"id": "shirts", "he": "חולצות מכופתרות"},
    {"id": "dresses", "he": "שמלות"}, {"id": "pants", "he": "מכנסיים"}, {"id": "sets", "he": "סטים"},
    {"id": "knit", "he": "סריגים וקרדיגנים"}, {"id": "jackets", "he": "ג׳קטים ובלייזרים"},
    {"id": "skirts", "he": "חצאיות"}, {"id": "sport", "he": "בגדי ספורט"},
]
BAD_RE = re.compile(r"\bmen'?s?\b(?![^,]*women)|\bsexy\b|bodycon|evening|\bgown\b|wedding|lingerie|swimwear|swimsuit|bikini|underwear|\bbra\b|\bkids?\b|children|\bgirls?'?\b|maternity|nightgown|pajama|sleepwear|cosplay|costume|clubwear|night club", re.I)
WOMEN_RE = re.compile(r"women|woman|ladies|lady|female|womens", re.I)

def size_rank(lbl):
    s = re.sub(r"\(.*?\)", "", str(lbl)).upper().replace(" ", "")
    m = re.match(r"^(\d+)XL$", s)
    if m: return int(m.group(1))
    return {"XXXXXL": 5, "XXXXL": 4, "XXXL": 3, "XXL": 2, "XL": 1, "L": 0, "M": -1, "S": -2, "XS": -3, "XXS": -4}.get(s)

def rank_label(r):
    if r is None: return ""
    return {0: "L", 1: "XL"}.get(r, "%dXL" % r)

def cat_of(title, hint=None):
    t = title.lower()
    rules = [
        ("sport", r"yoga|gym|fitness|sportswear|activewear|athletic|tracksuit|jogger|leggings|running|workout|sports? (?:set|bra|suit)|sweatsuit"),
        ("sets", r"two[- ]piece|2[- ]?(?:piece|pcs)|\bset\b|\bsets\b|co-?ord|outfits?\b|suit set"),
        ("dresses", r"\bdress(?:es)?\b|abaya|kaftan"),
        ("skirts", r"\bskirts?\b"),
        ("jackets", r"blazer|jacket|coat|outerwear|trench|vest\b|parka|puffer"),
        ("knit", r"cardigan|sweater|pullover|knit(?:ted|wear)? top|jumper"),
        ("pants", r"\bpants\b|trousers|jeans|wide[- ]leg|palazzo|shorts\b|culottes|leggings"),
        ("shirts", r"button|blouse|shirts? (?:and|&) blouses|chiffon shirt|lapel shirt|\bshirt\b(?!.*t-?shirt)"),
        ("tees", r"t-?shirt|\btees?\b|tunic|\btops?\b|tank|camisole|hoodie|sweatshirt|polo"),
    ]
    for c, rx in rules:
        if re.search(rx, t): return c
    return hint or "tees"

GARMENTS = [
    (r"tracksuit|jogging suit|sweatsuit", "חליפת טרנינג"),
    (r"(?:yoga|gym|fitness|sports?|workout|active(?:wear)?) (?:set|suit)|activewear set", "סט ספורט"),
    (r"(?:two[- ]piece|2[- ]?(?:piece|pcs)|matching|co-?ord)[^,]*(?:pants|trousers)", "סט חולצה ומכנסיים"),
    (r"(?:two[- ]piece|2[- ]?(?:piece|pcs)|matching|co-?ord)[^,]*skirt", "סט חולצה וחצאית"),
    (r"two[- ]piece|2[- ]?(?:piece|pcs)|matching set|co-?ord|\bset\b|outfits?\b", "סט שני חלקים"),
    (r"shirt dress", "שמלה מכופתרת"), (r"maxi dress|long dress|maxi.*dress", "שמלת מקסי"), (r"midi dress|midi.*dress", "שמלת מידי"),
    (r"abaya", "עבאיה"), (r"kaftan", "קפטן"), (r"\bdress(?:es)?\b", "שמלה"),
    (r"maxi skirt|long skirt", "חצאית מקסי"), (r"midi skirt", "חצאית מידי"), (r"\bskirts?\b", "חצאית"),
    (r"blazer", "בלייזר"), (r"trench", "מעיל טרנץ׳"), (r"puffer|down jacket|padded", "מעיל פוך"), (r"\bcoats?\b", "מעיל"),
    (r"denim jacket|jean jacket", "ג׳קט ג׳ינס"), (r"jacket", "ג׳קט"), (r"\bvest\b", "וסט"),
    (r"cardigan", "קרדיגן"), (r"sweater|pullover|jumper", "סוודר"), (r"hoodie", "קפוצ׳ון"), (r"sweatshirt", "סווטשירט"),
    (r"leggings", "טייץ"), (r"jeans", "ג׳ינס"), (r"wide[- ]leg|palazzo", "מכנסיים רחבים"), (r"shorts", "מכנסיים קצרים"),
    (r"\bpants\b|trousers", "מכנסיים"),
    (r"button[- ]?(?:up|down)|button shirt", "חולצה מכופתרת"), (r"tunic", "טוניקה"), (r"blouse", "חולצה"),
    (r"polo", "חולצת פולו"), (r"t-?shirt|\btees?\b", "טישירט"), (r"tank top|camisole|\bvest top", "גופייה"),
    (r"\bshirt\b", "חולצה"), (r"\btops?\b", "חולצה"),
]
FEATURES = [
    (r"long sleeve", "שרוול ארוך"), (r"short sleeve", "שרוול קצר"), (r"3/4 sleeve|three quarter", "שרוול 3/4"),
    (r"sleeveless", "בלי שרוולים"), (r"puff sleeve", "שרוול נפוח"), (r"half[- ]sleeve", "חצי שרוול"),
    (r"v[- ]neck", "צווארון V"), (r"crew neck|round neck|o-neck", "צווארון עגול"), (r"turtle ?neck|mock ?neck", "צווארון גבוה"),
    (r"lapel", "צווארון חולצה"), (r"off[- ]shoulder", "חשוף כתפיים"),
    (r"high[- ]waist", "גזרה גבוהה"), (r"oversized?|loose", "גזרה רחבה"), (r"wide[- ]leg", "רגל רחבה"),
    (r"pleated", "קפלים"), (r"wrap", "מעטפת"), (r"belt|waistband|tie waist", "עם חגורה"), (r"pocket", "עם כיסים"),
    (r"zip", "רוכסן"), (r"hooded|with hood", "עם קפוצ׳ון"), (r"drawstring", "שרוך במותן"),
    (r"floral", "הדפס פרחוני"), (r"leopard|animal print", "הדפס חייתי"), (r"striped|stripe", "פסים"), (r"plaid|check", "משבצות"),
    (r"polka", "נקודות"), (r"sequin", "פאייטים"), (r"lace", "תחרה"), (r"embroider", "רקמה"), (r"\bprint(?:ed)?\b", "מודפס"),
    (r"solid|plain", "חלק"),
    (r"linen", "פשתן"), (r"cotton", "כותנה"), (r"denim", "דנים"), (r"chiffon", "שיפון"), (r"satin", "סאטן"), (r"knit", "סריג"),
    (r"faux fur", "פרווה מלאכותית"), (r"fleece", "פליז"), (r"velvet", "קטיפה"), (r"corduroy", "קורדרוי"), (r"leather|pu\b", "דמוי עור"),
    (r"bohemian|boho", "בוהו"), (r"office|\bwork\b|business", "למשרד"), (r"elegant", "אלגנטי"), (r"casual", "יומיומי"),
]

def he_title(title, max_rank=None, custom=False):
    t = title.lower(); g = None
    for rx, he in GARMENTS:
        if re.search(rx, t): g = he; break
    g = g or "פריט לבוש"
    feats = []
    for rx, he in FEATURES:
        if re.search(rx, t) and he not in feats and he not in g:
            if he in ("שרוול קצר", "שרוול ארוך") and any(x in feats for x in ("שרוול ארוך", "שרוול קצר", "שרוול 3/4")): continue
            if he == "מודפס" and any("הדפס" in x for x in feats): continue
            if he == "חלק" and any(x in feats for x in ("מודפס",)) : continue
            if he in ("אלגנטי", "יומיומי") and g.startswith(("שמלה", "שמלת", "חולצה", "חולצת", "חצאית", "טוניקה", "גופייה")): he = he + "ת"
            feats.append(he)
    feats = feats[:3]
    size = ("עד " + rank_label(max_rank)) if max_rank is not None and max_rank >= 3 else ""
    parts = [g] + feats + ([size] if size else []) + (["מידות בהתאמה"] if custom else [])
    return " · ".join(parts)

COLORS = {"black": "שחור", "white": "לבן", "red": "אדום", "blue": "כחול", "navy": "כחול נייבי", "navy blue": "כחול נייבי", "dark blue": "כחול כהה",
    "light blue": "תכלת", "sky blue": "תכלת", "green": "ירוק", "dark green": "ירוק כהה", "army green": "ירוק זית", "olive": "זית", "olive green": "זית",
    "moss green": "ירוק טחב", "yellow": "צהוב", "orange": "כתום", "pink": "ורוד", "dark pink": "ורוד כהה", "light pink": "ורוד בהיר", "rose": "ורוד עתיק",
    "purple": "סגול", "violet": "סגול", "lavender": "לבנדר", "gray": "אפור", "grey": "אפור", "dark gray": "אפור כהה", "light gray": "אפור בהיר",
    "brown": "חום", "coffee": "קפה", "khaki": "חאקי", "beige": "בז׳", "apricot": "משמש", "camel": "קאמל", "wine red": "יין", "wine": "יין",
    "burgundy": "בורדו", "champagne": "שמפניה", "gold": "זהב", "silver": "כסף", "cream": "שמנת", "off white": "אוף וויט", "ivory": "שנהב",
    "mint": "מנטה", "mint green": "מנטה", "rose red": "ורוד פוקסיה", "fuchsia": "פוקסיה", "royal blue": "כחול רויאל", "denim blue": "כחול ג׳ינס",
    "leopard": "מנומר", "floral": "פרחוני", "multicolor": "צבעוני", "caramel": "קרמל", "chocolate": "שוקולד", "mustard": "חרדל", "coral": "קורל",
    "peach": "אפרסק", "turquoise": "טורקיז", "teal": "טורקיז כהה", "light green": "ירוק בהיר", "dark grey": "אפור כהה", "light grey": "אפור בהיר",
    "melange": "מלאנז׳", "heather grey": "אפור מלאנז׳", "oatmeal": "שיבולת שועל", "taupe": "טאופ", "maroon": "בורדו", "dark brown": "חום כהה", "light brown": "חום בהיר"}

def he_colors(cols, more=0):
    out = []
    for c in cols:
        k = re.sub(r"\s+", " ", re.sub(r"[\d#()]+", " ", c)).strip().lower()
        he = COLORS.get(k)
        if he and he not in out: out.append(he)
    n_unknown = len([c for c in cols if COLORS.get(re.sub(r"\s+", " ", re.sub(r"[\d#()]+", " ", c)).strip().lower()) is None])
    extra = n_unknown + (more or 0)
    if extra and out: out.append("ועוד %d" % extra)
    elif extra and not out: out = ["%d צבעים" % extra]
    return out

FABRIC = [("polyester", "פוליאסטר"), ("cotton", "כותנה"), ("spandex", "ספנדקס"), ("elastane", "אלסטן"), ("viscose", "ויסקוזה"), ("rayon", "ויסקוזה"),
    ("linen", "פשתן"), ("nylon", "ניילון"), ("polyamide", "פוליאמיד"), ("acrylic", "אקריליק"), ("wool", "צמר"), ("modal", "מודאל"), ("bamboo", "במבוק"),
    ("silk", "משי"), ("satin", "סאטן"), ("chiffon", "שיפון"), ("denim", "דנים"), ("lyocell", "ליוסל"), ("tencel", "טנסל"), ("acetate", "אצטט"),
    ("fleece", "פליז"), ("velvet", "קטיפה"), ("lace", "תחרה"), ("knitted", "סריג"), ("woven", "ארוג"), ("tri blend", "תערובת כותנה-פוליאסטר-ריון"),
    ("leather", "עור"), ("pu", "דמוי עור"), ("faux fur", "פרווה מלאכותית"), ("mesh", "רשת"), ("crepe", "קרפ"), ("corduroy", "קורדרוי")]

def he_fabric(s):
    if not s: return ""
    low = s.lower(); out = []
    for m in re.finditer(r"(\d{1,3})\s*%\s*([a-z ]+)", low):
        name = m.group(2).strip()
        for en, he in FABRIC:
            if name.startswith(en): out.append("%s%% %s" % (m.group(1), he)); break
    if out: return " · ".join(out)
    for en, he in FABRIC:
        if re.search(r"\b" + re.escape(en) + r"\b", low) and he not in out: out.append(he)
    return " / ".join(out[:4])

def resp_hours(s):
    m = re.search(r"(\d+)\s*h", s or "")
    return int(m.group(1)) if m else None

def quality_score(sup, prod):
    """0–100. Verified/audited, store rating, years, review volume, response, on-time dispatch, fabric stated, reorder rate."""
    q = 0.0
    if sup.get("verified"): q += 20
    r = sup.get("rating")
    if r: q += max(0, min(25, (r - 4.0) * 25))
    q += min(sup.get("years") or 0, 10) * 1.5
    n = sup.get("store_reviews") or sup.get("reviews") or 0
    q += min(15, math.log10(n + 1) / 3 * 15)
    h = resp_hours(sup.get("response_time"))
    if h is not None: q += 5 if h <= 3 else 3 if h <= 6 else 1
    ot = sup.get("ontime")
    if ot is not None: q += 10 if ot >= 95 else 7 if ot >= 90 else 4 if ot >= 80 else 0
    elif sup.get("platform") == "Made-in-China" and sup.get("member") == "Diamond": q += 5
    if prod.get("fabric_he") and "%" in prod.get("fabric_he", ""): q += 5
    elif prod.get("fabric_he"): q += 3
    if (prod.get("reorder") or 0) >= 30: q += 5
    elif (prod.get("reorder") or 0) >= 15: q += 2
    return int(round(min(100, q)))

def trend_score(p):
    t = 0.0
    t += min(40, math.log10((p.get("sold") or 0) + 1) * 13)
    t += min(15, (p.get("reorder") or 0) / 4)
    if p.get("hot_rank"): t += max(5, 25 - p["hot_rank"])
    t += min(10, math.log10((p.get("nrev") or 0) + 1) * 6)
    if re.search(r"2026|2027|new arrival|new design|new fashion|hot sale|hot selling|trend", p.get("title_en", ""), re.I): t += 10
    return int(round(min(100, t)))

def size_points(p):
    r = p.get("max_size_rank") or 0
    return 100 if r >= 7 else 90 if r >= 6 else (75 if p.get("custom_size") else 50 if r >= 5 else 25)

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "unknown"

MIN_QUALITY = 50

def finalize(data, fresh, source, min_quality=MIN_QUALITY):
    """Replace the products of `source` with `fresh` (already shaped by shape_product), rebuild suppliers, scores, stamp.
    Products of OTHER sources (e.g. the Made-in-China harvest, Nov 1 2026) keep their own quality/score and are not re-gated here."""
    prev = {p["id"]: p for p in data.get("products", [])}
    others = [p for p in data.get("products", []) if p.get("source") != source]
    sups = {k: v for k, v in data.get("suppliers", {}).items()}
    mine = []
    for o in fresh:
        p, sid, s = shape_product(o)
        if p["id"] in prev:
            p["first_seen"] = prev[p["id"]].get("first_seen", p["checked"])
            for k in ("title_he", "reviews", "note_he"):
                if prev[p["id"]].get(k + "_manual"): p[k] = prev[p["id"]][k]; p[k + "_manual"] = True
        old = sups.get(sid, {})
        s = {**old, **{k: v for k, v in s.items() if v not in (None, "", [])}}
        sups[sid] = s
        mine.append(p)
    for sid in {p["supplier"] for p in mine}:
        s = sups[sid]; ps = [p for p in mine if p["supplier"] == sid]
        s["quality"] = max(quality_score(s, p) for p in ps)
    for p in mine:
        s = sups[p["supplier"]]
        p["quality"] = quality_score(s, p)
        p["trend"] = trend_score(p)
        p["score"] = int(round(0.45 * p["quality"] + 0.30 * p["trend"] + 0.25 * size_points(p)))
    mine = [p for p in mine if p["quality"] >= min_quality]
    keep = others + mine
    used = {p["supplier"] for p in keep}
    sups = {k: v for k, v in sups.items() if k in used}
    keep.sort(key=lambda p: -(p.get("score") or 0))
    data["products"] = keep; data["suppliers"] = sups
    ids = {c["id"] for c in CATEGORIES}
    data["categories"] = CATEGORIES + [c for c in data.get("categories", []) if c.get("id") not in ids]
    data["updated"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    data.setdefault("sources", {})[source] = data["updated"]
    st = data.get("stats") or {}
    st.update({"products": len(keep), "suppliers": len(sups),
               "verified_suppliers": sum(1 for s in sups.values() if s.get("verified")),
               "big6": sum(1 for p in keep if (p.get("max_size_rank") or 0) >= 6),
               "custom": sum(1 for p in keep if p.get("custom_size"))})
    data["stats"] = st
    return data

def qty_he(q, unit):
    u = "סטים" if "set" in unit else "יח׳"
    q = q.replace(",", "")
    m = re.match(r"^[≥>]\s*(\d+)", q)
    if m: return "%s %s ומעלה" % (m.group(1), u)
    m = re.match(r"^(\d+)\s*-\s*(\d+)", q)
    if m: return "%s–%s %s" % (m.group(1), m.group(2), u)
    m = re.match(r"^(\d+)\+", q)
    if m: return "%s %s ומעלה" % (m.group(1), u)
    m = re.match(r"^(\d+)", q)
    return ("%s %s" % (m.group(1), u)) if m else q

def shape_product(o):
    """Raw scraped dict (Alibaba or Made-in-China) -> (product, supplier_id, supplier)."""
    s = dict(o["sup"]); s.setdefault("platform", o.get("source", "Alibaba"))
    sid = slug(s.get("name"))
    tiers = o.get("tiers") or []
    unit = o.get("unit") or "pieces"
    prices = [t["price"] for t in tiers]
    mr = o.get("max_rank")
    p = {
        "id": o["id"], "source": o.get("source", "Alibaba"), "cat": o.get("cat") or cat_of(o["title_en"], o.get("cat_hint")),
        "title_en": o["title_en"], "title_he": o.get("title_he") or he_title(o["title_en"], mr, o.get("custom_size")),
        "img": (o.get("imgs") or [""])[0], "imgs": (o.get("imgs") or [])[:6],
        "price_min": min(prices) if prices else None, "price_max": max(prices) if prices else None,
        "price_moq": (tiers[0]["price"] if tiers and not o.get("price_range_only") else (min(prices) if prices else None)),
        "contact_url": o.get("contact_url") or o["sup"].get("contact_url") or o["url"],
        "tiers": [] if o.get("price_range_only") else [{"qty_he": qty_he(t["qty"], unit), "price": t["price"]} for t in tiers],
        "moq": o.get("moq"), "unit": unit,
        "max_size": rank_label(mr) if mr is not None else "", "max_size_rank": mr,
        "custom_size": bool(o.get("custom_size")), "sizes_he": o.get("sizes_he", ""),
        "colors_he": o.get("colors_he") or he_colors(o.get("colors") or [], o.get("colors_more", 0)),
        "fabric_he": o.get("fabric_he") or he_fabric(o.get("material") or ""),
        "sample_he": o.get("sample_he", ""), "lead_he": o.get("lead_he", ""),
        "sold": o.get("sold"), "reorder": o.get("reorder"), "rating": o.get("rating"), "nrev": o.get("nrev") or 0,
        "reviews": o.get("reviews_he", []), "hot": o.get("hot_he", ""), "hot_rank": o.get("hot_rank"),
        "url": o["url"], "supplier": sid, "checked": o.get("checked"), "first_seen": o.get("checked"),
    }
    if p["source"] == "Made-in-China":
        if not p["sample_he"]: p["sample_he"] = (o.get("sample") or "").replace("Sample US$", "דוגמה: $") or "לבקש מהספק"
        if not p["lead_he"]: p["lead_he"] = "לשאול את הספק (לא צוין בדף)"
        if not p["sizes_he"] and mr is not None: p["sizes_he"] = "עד " + rank_label(mr) + " (לפי הדף)"
    sup = {
        "name": s.get("name"), "name_short": re.sub(r"\s*(Co\.,?\s*Ltd\.?|Company Limited|Limited|Co\.)\s*$", "", s.get("name") or "").strip(),
        "platform": s.get("platform"), "verified": bool(s.get("verified")), "verified_by": s.get("verified_by"),
        "years": s.get("years"), "rating": s.get("rating"), "reviews": s.get("store_reviews") or s.get("reviews"),
        "response_time": s.get("response_time"), "response_time_he": ("עד %d שעות" % resp_hours(s.get("response_time"))) if resp_hours(s.get("response_time")) else "",
        "response_rate": s.get("response_rate"), "ontime": s.get("ontime"),
        "trade_assurance": s.get("platform") == "Alibaba", "type_he": s.get("type_he", ""),
        "location": s.get("location"), "store_url": s.get("store"),
        "contact_url": s.get("contact_url"), "whatsapp": s.get("whatsapp"), "email": s.get("email"),
        "member": s.get("member"), "sub": s.get("sub"),
    }
    return p, sid, sup
