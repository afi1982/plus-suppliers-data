#!/usr/bin/env python3
"""Made-in-China harvest for the ספקים app (v2, Nov 1 2026): hundreds of plus-size women's products from VERIFIED suppliers.

Runs in GitHub Actions (plain HTTP, no keys, no login) and on Tab's box:
  python3 refresh_mic.py [--in suppliers.json|URL] [--out suppliers.json]
Steps: 14 item types x 4-6 plus-size phrasings x 3 pages of m.made-in-china.com search (36 cards a page)
 -> drop men/unisex/kids, non-clothing, other types, items that are not plus size
 -> read every remaining supplier's profile (member level, audit, SGS, est. year)
 -> keep VERIFIED only (Audited Supplier, Diamond/Gold member, or SGS)
 -> per type pick up to TARGET (6XL+ first, then supplier quality), max 3 per supplier per type, 8 per supplier overall
 -> read each picked product's page <head> for its size range / material (drops ones whose sizes stop under 4XL)
 -> replaces the source=="Made-in-China" products, keeps Alibaba ones; writes mic_status.json.
Never contacts, signs up with or pays anyone.
"""
import json, re, sys, os, time, datetime, html as H, urllib.parse
from concurrent.futures import ThreadPoolExecutor
import requests

UA = "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Mobile Safari/537.36"
HDR = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
RAW = "https://raw.githubusercontent.com/afi1982/plus-suppliers-data/main/suppliers.json"
PAGES = 3; TARGET = 60; CAP_SUP = 8; CAP_SUP_TYPE = 3; THREADS = 6
NOW = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
YEAR = datetime.datetime.utcnow().year

# id, cat (app category), Hebrew noun, title test (same as the app's TYPES.t), searches
TYPES = [
 ("dresses", "dresses", "שמלה", r"dres|gown|abaya|kaftan|caftan", ["plus size women dress", "plus size maxi dress", "plus size women long dress", "plus size casual dress women", "plus size evening dress women", "big size women dress 6XL"]),
 ("tops", "tees", "חולצה", r"\btops?\b|blouse|(^|[^t])shirt|\btees?\b|t-?shirt|tunic|cami|tank", ["plus size women t shirt", "plus size women blouse", "plus size women tops", "plus size tunic women", "plus size women shirt 6XL"]),
 ("jeans", "pants", "ג׳ינס", r"jean|denim", ["plus size women jeans", "plus size denim jeans women", "plus size high waist jeans", "big size women jeans", "plus size wide leg jeans women"]),
 ("pants", "pants", "מכנסיים", r"pant|trouser|jogger|capri|culotte|shorts", ["plus size women pants", "plus size wide leg pants women", "plus size women trousers", "plus size palazzo pants", "plus size women casual pants"]),
 ("skirts", "skirts", "חצאית", r"skirt", ["plus size women skirt", "plus size maxi skirt", "plus size midi skirt women", "plus size denim skirt"]),
 ("hoodies", "hoodies", "קפוצ׳ון", r"hoodie|sweatshirt", ["plus size women hoodie", "plus size women sweatshirt", "plus size oversized hoodie women", "plus size women hooded"]),
 ("knit", "knit", "סריג", r"sweater|cardigan|knit|pullover|jumper", ["plus size women sweater", "plus size women cardigan", "plus size knit sweater women", "plus size women pullover"]),
 ("jackets", "jackets", "ג׳קט", r"jacket|coat|blazer|parka|puffer|outerwear|windbreaker", ["plus size women jacket", "plus size women coat", "plus size women blazer", "plus size winter coat women", "plus size puffer jacket women"]),
 ("leggings", "leggings", "טייץ", r"legging|tights|yoga pant", ["plus size leggings", "plus size women leggings 6XL", "plus size yoga pants", "plus size high waist leggings"]),
 ("sport", "sport", "בגדי ספורט", r"sport|yoga|gym|active|fitness|workout|athletic|running|tracksuit|jogger", ["plus size activewear women", "plus size sportswear women", "plus size yoga set", "plus size gym wear women", "plus size tracksuit women"]),
 ("sets", "sets", "סט", r"\bsets?\b|piece|\bsuits?\b|tracksuit|outfit|co-?ord", ["plus size two piece set women", "plus size women 2 piece outfit", "plus size pants set women", "plus size women suit set"]),
 ("lingerie", "lingerie", "הלבשה תחתונה", r"lingerie|underwear|\bbras?\b|panties|shapewear", ["plus size lingerie", "plus size women underwear", "plus size bra", "plus size shapewear", "plus size panties women"]),
 ("swim", "swim", "בגד ים", r"swim|bikini|bathing", ["plus size swimsuit", "plus size swimwear women", "plus size one piece swimsuit", "plus size bikini", "plus size tankini"]),
 ("pajamas", "pajamas", "פיג׳מה", r"pajama|pyjama|sleepwear|nightgown|loungewear", ["plus size pajamas women", "plus size sleepwear", "plus size nightgown", "plus size loungewear women", "plus size robe women"]),
]
CATEGORIES = [{"id": "tees", "he": "חולצות וטישירטים"}, {"id": "shirts", "he": "חולצות מכופתרות"}, {"id": "dresses", "he": "שמלות"},
 {"id": "pants", "he": "מכנסיים"}, {"id": "sets", "he": "סטים"}, {"id": "knit", "he": "סריגים וקרדיגנים"}, {"id": "jackets", "he": "ג׳קטים ובלייזרים"},
 {"id": "skirts", "he": "חצאיות"}, {"id": "sport", "he": "בגדי ספורט"}, {"id": "hoodies", "he": "קפוצ׳ונים"}, {"id": "leggings", "he": "טייצים"},
 {"id": "lingerie", "he": "הלבשה תחתונה"}, {"id": "swim", "he": "בגדי ים"}, {"id": "pajamas", "he": "פיג׳מות"}]

MEN = re.compile(r"\b(men|mens|men's|man|male|unisex|boy|boys|kids|kid|children|child|baby|babies|toddler|infant|girls?|teen|maternity|pregnan\w*)\b", re.I)
NOT_CLOTH = re.compile(r"\b(fabric|fabrics|textile|yarn|machine|machinery|mannequin|hangers?|zippers?|packaging|poly ?bag|handbag|tote|backpack|shoes?|sandals?|slippers?|sneakers?|boots?|wigs?|dolls?|sewing|needle|thread|buttons?|lace trim|sticker|mug|phone case|curtain|bedding|sofa|cushion|pillow|jewelry|necklace|earrings?|bracelet|sunglasses|umbrella|socks?|hat|cap|gloves?|scarf|belt|mask|costume|cosplay|halloween|wedding|bridal|bride|polynesian|samoan|hawaiian|tongan|pet|dog|second[\s-]?hand|used|bales?|erotic|crotchless|fetish|bondage|open crotch|stock lots?)\b", re.I)
PLUS = re.compile(r"plus[\s-]?size|big[\s-]?size|large[\s-]?size|larger size|extra large|curvy|\bfat\b|chubby|full figure|\b(?:[4-9]|1[0-2])\s?xl\b|x{4,}l\b|\b[4-9]x\b|oversized?", re.I)
P_SIZE_N = re.compile(r"(?<![\w.])(\d{1,2})\s?X{1,2}L\b", re.I)
P_SIZE_X = re.compile(r"(?<!\w)(X{2,9})L\b", re.I)
P_SIZE_US = re.compile(r"(?<![\w.])([1-9])X\b")
P_CUSTOM = re.compile(r"custom(?:ized|izable|ised)?\s+siz|any size|size customi", re.I)

def size_rank(s):
    if not s: return 0
    r = 0
    for m in P_SIZE_N.finditer(s):
        n = int(m.group(1))
        if 1 <= n <= 12: r = max(r, n)
    for m in P_SIZE_X.finditer(s): r = max(r, len(m.group(1)))
    for m in P_SIZE_US.finditer(s): r = max(r, int(m.group(1)))
    return r

def text(h): return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()
def first(p, s, g=1):
    m = re.search(p, s, re.S); return m.group(g) if m else None

S = requests.Session(); S.headers.update(HDR)
def get(url, stop=None, tries=3):
    for a in range(tries):
        try:
            if stop:
                with S.get(url, timeout=25, stream=True) as r:
                    if r.status_code != 200: raise Exception("HTTP %d" % r.status_code)
                    buf = b""
                    for ch in r.iter_content(16384):
                        buf += ch
                        if any(s.encode() in buf for s in stop) or len(buf) > 400000: break
                    return buf.decode("utf-8", "replace")
            r = S.get(url, timeout=25)
            if r.status_code != 200: raise Exception("HTTP %d" % r.status_code)
            return r.text
        except Exception as e:
            err = str(e); time.sleep(2 + 3 * a)
    raise Exception(err)

def parse_search(h):
    out, seen = [], set()
    for b in h.split("J-item-wrap")[1:]:
        url = first(r'data-url="([^"]+)"', b)
        if not url: continue
        pid = first(r'"productId":"(\d+)"', b) or first(r"-(\d{6,})\.html", url)
        if not pid or pid in seen: continue
        seen.add(pid)
        title = text(first(r'class="pro-name"[^>]*>\s*<a[^>]*>(.*?)</a>', b)) or text(first(r'<img data-original="[^"]*"[^>]*?alt="([^"]*)"', b))
        if not title: continue
        img = first(r'(?:data-original|src)="(https://image\.made-in-china\.com/[^"]+)"', b)
        pm = re.search(r'class="pro-price-fob">(.*?)</span>\s*/?\s*([A-Za-z ]*)', b, re.S)
        ptxt, unit = (text(pm.group(1)), text(pm.group(2))) if pm else (text(first(r'class="pro-price">(.*?)</div>', b)), "")
        pmin = pmax = None
        if "$" in ptxt:
            nums = re.findall(r"([\d,]+(?:\.\d+)?)", ptxt[ptxt.index("$"):])
            if nums:
                pmin = float(nums[0].replace(",", "")); pmax = float(nums[1].replace(",", "")) if len(nums) > 1 else pmin
                if pmin < 0.5: pmin = pmax = None
        moqt = text(first(r'class="pro-moq">\s*<span>MOQ:</span>\s*([^<]+)<', b))
        mm = re.search(r"([\d,]+)", moqt or ""); moq = int(mm.group(1).replace(",", "")) if mm else None
        sm = re.search(r'class="company-name">\s*<a href="([^"]*)"[^>]*>(.*?)</a>', b, re.S)
        store, sup = (sm.group(1), text(sm.group(2))) if sm else (None, "")
        sub = first(r"company-([A-Za-z0-9_\-]+)", store or "")
        inq = first(r'href="(https://m\.made-in-china\.com/inquiry/send/product/[^"]+)"', b)
        out.append({"pid": pid, "title": title, "url": url, "img": img, "pmin": pmin, "pmax": pmax,
                    "unit": (unit or "").lower(), "moq": moq, "sup": sup, "sub": sub.lower() if sub else None,
                    "btype": text(first(r'class="business-type">(.*?)</p>', b)),
                    "loc": text(first(r'company-location">\s*<i[^>]*></i>(.*?)</span>', b)).replace(" ,", ","),
                    "audited": 'alt="Audited Supplier"' in b, "inq": H.unescape(inq) if inq else None,
                    "rank": size_rank(title), "custom": bool(P_CUSTOM.search(title))})
    return out

def parse_company(h):
    d = {"level": first(r'"memberLevel":"(\w*)"', h), "since": first(r'"memberSince":"(\d{4})"', h),
         "est": first(r'"establishment":"(\d{4})', h) or first(r"Year of Establishment\s*(?:<[^>]*>\s*)*:?\s*(?:<[^>]*>\s*)*(\d{4})", h),
         "sgs": first(r'"sgsMember":(true|false)', h) == "true", "aud": first(r'"showAuditLogo":(true|false)', h) == "true",
         "stars": first(r'"intStars":(\d)', h), "rating": None}
    if not d["level"]:
        free = "showroom-for-free" in h or "Account Registered in" in h
        d["level"] = "free" if free else None
        d["since"] = d["since"] or first(r"Account Registered in:\s*(?:<[^>]*>\s*)*(\d{4})", h)
        rt = first(r"Rating:\s*(?:<[^>]*>\s*)*([0-5](?:\.\d)?)/5", h); d["rating"] = float(rt) if rt else None
        if free: d["aud"] = False
    for k in ("since", "est", "stars"):
        d[k] = int(d[k]) if d[k] else None
    return d

def parse_specs(h):
    desc = text(first(r'(?i)<meta name="description" content="([^"]*)"', h))
    allt, size, mat, seen = [desc], None, None, set()
    for p in (r'\{"@type":"PropertyValue","name":"([^"]{1,40})","value":"([^"]{0,300})"\}', r'\{"key":"([^"]{1,40})","value":"([^"]{0,300})"'):
        for m in re.finditer(p, h):
            k, v = m.group(1), H.unescape(m.group(2))
            if (k, v) in seen: continue
            seen.add((k, v)); allt.append(k + ": " + v); kl = k.lower()
            if size is None and "size" in kl and "package" not in kl: size = v
            if mat is None and kl in ("material", "fabric"): mat = v
    a = "\n".join(allt)
    return {"rank": size_rank(a), "custom": bool(P_CUSTOM.search(a)), "size": size, "material": mat}

def verified(it, p):
    return bool(it["audited"] or (p and (p.get("aud") or p.get("sgs") or p.get("level") in ("diamond", "gold"))))

def years(p):
    if p and p.get("est") and 1950 < p["est"] <= YEAR: return YEAR - p["est"], "est"
    if p and p.get("since") and 1995 < p["since"] <= YEAR: return YEAR - p["since"], "since"
    return 0, None

def quality(it, p):
    q = 0; lv = (p or {}).get("level")
    if it["audited"] or (p or {}).get("aud"): q += 35
    q += 22 if lv == "diamond" else 14 if lv == "gold" else 0
    if (p or {}).get("sgs"): q += 6
    y, k = years(p); q += min(y, 15) * (1.6 if k == "est" else 1.0)
    if (p or {}).get("stars"): q += min(p["stars"], 5) * 2
    if "Manufacturer" in (it.get("btype") or ""): q += 4
    return max(0, min(100, round(q)))

# ---------- Hebrew title (rule-based; the English original is in the sheet) ----------
MODS = [  # gender-neutral wording, each shown as its own " · " item
 (r"\bmaxi\b", "מקסי"), (r"\bmidi\b", "מידי"), (r"\bmini\b", "מיני"),
 (r"evening|party|cocktail", "לערב"), (r"casual", "לכל יום"), (r"office|\bwork\b|business|formal", "למשרד"),
 (r"boho|bohemian", "בוהו"), (r"floral|flower", "הדפס פרחים"), (r"leopard", "הדפס מנומר"), (r"print", "בהדפס"), (r"stripe", "פסים"), (r"plaid|check", "משבצות"), (r"polka|\bdots?\b", "נקודות"),
 (r"lace", "תחרה"), (r"sequin", "פאייטים"), (r"satin|silk", "סאטן"), (r"linen", "פשתן"), (r"cotton", "כותנה"),
 (r"denim", "דנים"), (r"velvet", "קטיפה"), (r"chiffon", "שיפון"), (r"knit", "סריג"), (r"fleece", "פליז"), (r"faux fur|\bfur\b", "פרווה"), (r"leather|\bpu\b", "דמוי עור"),
 (r"high[\s-]?waist", "גזרה גבוהה"), (r"wide[\s-]?leg", "רגל רחבה"), (r"straight", "גזרה ישרה"), (r"skinny", "סקיני"), (r"flare|bootcut|bell bottom", "גזרה מתרחבת"), (r"stretch", "גמיש"),
 (r"ripped|distressed", "קרעים"), (r"pocket", "עם כיסים"), (r"tummy control|shaping|shaper", "מחטב בטן"), (r"push[\s-]?up", "פוש-אפ"), (r"wireless|wire[\s-]?free", "בלי חישוק"),
 (r"two[\s-]?piece|2[\s-]?piece|2\s?pcs", "2 חלקים"), (r"three[\s-]?piece|3[\s-]?piece|3\s?pcs", "3 חלקים"),
 (r"hooded|hoodie", "עם קפוצ׳ון"), (r"\bzip", "רוכסן"), (r"button", "עם כפתורים"), (r"v[\s-]?neck", "צווארון V"), (r"off[\s-]?shoulder", "חשוף כתפיים"),
 (r"short sleeve", "שרוול קצר"), (r"long sleeve", "שרוול ארוך"), (r"sleeveless", "בלי שרוולים"), (r"puff sleeve", "שרוול נפוח"),
 (r"winter|warm|thick", "לחורף"), (r"summer", "לקיץ"), (r"puffer|\bdown\b|padded", "מרופד"), (r"\bwrap\b", "מעטפת"),
 (r"modest|abaya|muslim", "צנוע"), (r"oversized?", "אוברסייז"), (r"yoga", "יוגה"), (r"gym|fitness|workout", "אימון"),
]
NOUN_EN = [  # more specific nouns first (overrides the type's default noun)
 (r"jumpsuit|romper", "אוברול"), (r"tracksuit|jogging suit", "טרנינג"), (r"blazer", "בלייזר"), (r"cardigan", "קרדיגן"), (r"\bcoat\b|parka|trench", "מעיל"),
 (r"\bvest\b|waistcoat", "וסט"), (r"tunic", "טוניקה"), (r"blouse", "חולצה מכופתרת" ), (r"t[\s-]?shirt|\btee\b", "טישירט"), (r"\btank\b|\bcami", "גופייה"),
 (r"sports? bra", "חזיית ספורט"), (r"\bbras?\b", "חזייה"), (r"panty|panties|brief", "תחתונים"), (r"shapewear|body shaper|shaper", "בגד מחטב"), (r"one[\s-]?piece swim", "בגד ים שלם"), (r"tankini", "טנקיני"), (r"bikini", "ביקיני"),
 (r"nightgown|nightdress|night dress|sleep dress", "כותונת לילה"), (r"\brobe\b|bathrobe", "חלוק"), (r"shorts\b", "מכנסיים קצרים"), (r"jogger", "ג׳וגר"),
]
def he_title(t, title, rank, custom):
    tid, cat, noun = t[0], t[1], t[2]
    for p, n in NOUN_EN:
        if re.search(p, title, re.I):
            # keep the type's own word first where the app matches by Hebrew prefix
            if tid in ("sets",): n = "סט " + n if n not in ("טרנינג", "אוברול") else n
            elif tid in ("sport",) and n not in ("טרנינג", "חזיית ספורט"): n = n + " ספורט"
            elif tid == "leggings": n = "טייץ"
            elif tid == "jeans": n = "ג׳ינס"
            elif tid == "pajamas" and n not in ("כותונת לילה", "חלוק"): n = "פיג׳מה"
            elif tid == "tops" and n not in ("טישירט", "טוניקה", "גופייה", "חולצה מכופתרת"): n = noun
            elif tid == "dresses": n = noun
            elif tid == "knit" and n not in ("קרדיגן", "וסט"): n = noun
            elif tid == "jackets" and n not in ("בלייזר", "מעיל", "וסט"): n = noun
            elif tid == "pants" and n not in ("מכנסיים קצרים", "ג׳וגר"): n = noun
            elif tid == "hoodies": n = noun
            elif tid == "skirts": n = noun
            elif tid == "swim" and n not in ("בגד ים שלם", "טנקיני", "ביקיני"): n = noun
            elif tid == "lingerie" and n not in ("חזייה", "תחתונים", "בגד מחטב", "חזיית ספורט"): n = noun
            noun = n; break
    if tid == "tops" and not noun.startswith(("חולצ", "טישירט", "טוניק", "גופי")): noun = "חולצה " + noun
    mods = []
    for p, w in MODS:
        if re.search(p, title, re.I) and w not in mods and w not in noun and noun not in w: mods.append(w)
        if len(mods) >= 3: break
    if tid in ("dresses", "skirts") and re.search(r"\blong\b(?! sleeve)", title, re.I) and "מקסי" not in mods: mods.insert(0, "ארוכה")
    s = " · ".join([noun] + mods[:3]) + " · מידות גדולות"
    if rank >= 4: s = s.replace(" · מידות גדולות", "") + " · עד %dXL" % rank
    if custom: s += " · מידות בהתאמה"
    return s

MAT = [(r"cotton", "כותנה"), (r"polyester", "פוליאסטר"), (r"spandex|elastane|lycra", "ספנדקס"), (r"nylon|polyamide", "ניילון"), (r"viscose|rayon", "ויסקוזה"),
       (r"linen", "פשתן"), (r"denim", "דנים"), (r"modal", "מודאל"), (r"silk", "משי"), (r"wool", "צמר"), (r"acrylic", "אקריליק"), (r"chiffon", "שיפון"), (r"lace", "תחרה"), (r"bamboo", "במבוק")]
def fabric_he(m):
    if not m: return ""
    w = [he for p, he in MAT if re.search(p, m, re.I)]
    pc = re.findall(r"(\d{1,3})\s?%", m)
    return " / ".join(dict.fromkeys(w)) + ((" (" + m[:40] + ")") if pc and w else "") if w else m[:50]

def short_name(n):
    return re.sub(r"[\s,.]*(co\.?,?\s*ltd\.?|company limited|limited|co\.?|ltd\.?|inc\.?|llc)\.?$", "", n or "", flags=re.I).strip(" ,.")

def main():
    a = sys.argv[1:]
    src = a[a.index("--in") + 1] if "--in" in a else (RAW if not os.path.exists("suppliers.json") else "suppliers.json")
    out = a[a.index("--out") + 1] if "--out" in a else "suppliers.json"
    data = json.loads(requests.get(src + "?t=%d" % time.time(), timeout=30).text) if src.startswith("http") else json.load(open(src, encoding="utf-8"))
    old = {p["id"]: p for p in data["products"]}
    st = {"started": NOW, "searches": 0, "searches_ok": 0, "errors": [], "raw": 0}
    jobs = [(t, q, pg) for t in TYPES for q in t[4] for pg in range(1, PAGES + 1)]
    def srch(j):
        t, q, pg = j
        u = "https://m.made-in-china.com/search/product?word=" + urllib.parse.quote_plus(q) + ("&page=%d" % pg if pg > 1 else "")
        try: return j, parse_search(get(u)), None
        except Exception as e: return j, [], str(e)
    cands = {t[0]: [] for t in TYPES}; drops = {}
    seen_type = set()
    with ThreadPoolExecutor(THREADS) as ex:
        for (t, q, pg), items, err in ex.map(srch, jobs):
            st["searches"] += 1
            if err: st["errors"].append("%s p%d: %s" % (q, pg, err[:80])); continue
            st["searches_ok"] += 1; st["raw"] += len(items)
            tre = re.compile(t[3], re.I)
            for it in items:
                k = (t[0], it["pid"])
                if k in seen_type: continue
                seen_type.add(k)
                ti = it["title"]
                why = ("men_kids" if MEN.search(ti) else "not_clothing" if NOT_CLOTH.search(ti) else
                       "other_type" if not tre.search(ti) else "not_plus" if not PLUS.search(ti) and it["rank"] < 4 and not it["custom"] else
                       "small_sizes" if 0 < it["rank"] < 4 and not re.search(r"plus|big|large|curvy|fat", ti, re.I) else
                       "no_supplier" if not it["sub"] else "")
                if why: drops[why] = drops.get(why, 0) + 1; continue
                cands[t[0]].append(it)
    print("searches", st["searches_ok"], "/", st["searches"], "raw", st["raw"], "drops", drops, flush=True)
    subs = sorted({it["sub"] for v in cands.values() for it in v})
    def prof(sub):
        try: return sub, parse_company(get("https://m.made-in-china.com/company-%s/" % sub, stop=['"companySymbol"', "The Selected Suppliers"])), None
        except Exception as e: return sub, None, str(e)
    P = {}
    with ThreadPoolExecutor(THREADS) as ex:
        for sub, p, err in ex.map(prof, subs):
            if err: st["errors"].append("profile %s: %s" % (sub, err[:60]))
            P[sub] = p
    print("suppliers", len(subs), "profiles ok", sum(1 for v in P.values() if v), flush=True)
    # verified + quality
    pool = {}
    for tid, v in cands.items():
        keep = []
        for it in v:
            p = P.get(it["sub"])
            if not verified(it, p): drops["unverified"] = drops.get("unverified", 0) + 1; continue
            it["q"] = quality(it, p); keep.append(it)
        keep.sort(key=lambda it: (-(min(it["rank"], 8) >= 6 or it["custom"]), -it["q"], -min(it["rank"], 8)))
        pool[tid] = keep
    # pick: round 1 over-select (1.5x) for the size check, per-supplier caps
    def pick(limit, exclude=set()):
        per_sup, chosen, taken, tsig = {}, {t[0]: [] for t in TYPES}, set(), set()
        for tid, v in pool.items():
            pst = {}
            for it in v:
                if len(chosen[tid]) >= limit: break
                if it["pid"] in taken or it["pid"] in exclude: continue
                sig = (it["sub"], re.sub(r"\W+", "", it["title"].lower())[:40])
                if sig in tsig: continue
                if per_sup.get(it["sub"], 0) >= CAP_SUP or pst.get(it["sub"], 0) >= CAP_SUP_TYPE: continue
                per_sup[it["sub"]] = per_sup.get(it["sub"], 0) + 1; pst[it["sub"]] = pst.get(it["sub"], 0) + 1
                chosen[tid].append(it); taken.add(it["pid"]); tsig.add(sig)
        return chosen
    over = pick(int(TARGET * 1.5))
    allp = [it for v in over.values() for it in v]
    def spec(it):
        try: return it["pid"], parse_specs(get(it["url"], stop=["</head>"]))
        except Exception: return it["pid"], None
    SP = {}
    with ThreadPoolExecutor(THREADS) as ex:
        for pid, s in ex.map(spec, allp): SP[pid] = s
    bad = set()
    for it in allp:
        s = SP.get(it["pid"])
        if s:
            it["rank"] = max(it["rank"], s["rank"]); it["custom"] = it["custom"] or s["custom"]
            it["size_txt"] = s["size"]; it["material"] = s["material"]
            if 0 < it["rank"] < 4 and not it["custom"]: bad.add(it["pid"])
    drops["small_sizes_page"] = len(bad)
    for tid in pool:  # re-rank with the page sizes
        pool[tid].sort(key=lambda it: (-(min(it["rank"], 8) >= 6 or it["custom"]), -it["q"], -min(it["rank"], 8)))
    final = pick(TARGET, exclude=bad)
    # build products + suppliers
    tdef = {t[0]: t for t in TYPES}
    prods, sups = [], {}
    for tid, v in final.items():
        t = tdef[tid]
        for it in v:
            p = P.get(it["sub"]) or {}
            skey = "mic-" + it["sub"]
            y, yk = years(p)
            lv = p.get("level")
            badge = [b for b in ["Audited Supplier" if (it["audited"] or p.get("aud")) else "", {"diamond": "Diamond Member", "gold": "Gold Member"}.get(lv, ""), "SGS" if p.get("sgs") else ""] if b]
            badge_he = [b for b in ["מבוקר ע״י צד ג׳" if (it["audited"] or p.get("aud")) else "", {"diamond": "💎 חבר יהלום", "gold": "חבר זהב"}.get(lv, ""), "SGS" if p.get("sgs") else ""] if b]
            if skey not in sups:
                sups[skey] = {k: v for k, v in {"name": it["sup"], "name_short": short_name(it["sup"]), "platform": "Made-in-China", "verified": True,
                    "verified_by": " · ".join(badge_he) + " (Made-in-China)", "badge": " · ".join(badge), "member": {"diamond": "Diamond", "gold": "Gold"}.get(lv),
                    "years": y or None, "years_kind": yk, "est": p.get("est"), "type_he": "יצרן / מפעל" if "Manufacturer" in it["btype"] else ("חברת סחר" if it["btype"] else None),
                    "location": it["loc"] or None, "store_url": "https://m.made-in-china.com/company-%s/" % it["sub"], "contact_url": it["inq"], "quality": it["q"]}.items() if v not in (None, "")}
            rank = min(it["rank"], 12)
            img = it["img"] or ""
            full = re.sub(r"/\d{3}f0j00", "/2f0j00", img).replace(".webp", ".jpg") if img else ""
            sizes = (it.get("size_txt") or "")[:60]
            if not re.search(r"\dXL|XXL|XL", sizes, re.I): sizes = ""
            trend = 40 if re.search(r"\b202[56]\b|new arrival|new design|trend|fashion", it["title"], re.I) else 20
            sizep = 100 if rank >= 6 or it["custom"] else rank * 15
            pr = {"id": "mic-" + it["pid"], "source": "Made-in-China", "cat": t[1], "type": tid,
                  "title_en": it["title"], "title_he": he_title(t, it["title"], rank, it["custom"]),
                  "img": img, "imgs": [full] if full else [], "price_min": it["pmin"], "price_max": it["pmax"], "price_moq": it["pmax"],
                  "moq": it["moq"], "unit": "sets" if re.search(r"set", it["unit"] or "") else "pieces",
                  "max_size": ("%dXL" % rank) if rank >= 2 else None, "max_size_rank": rank or None, "custom_size": it["custom"] or None,
                  "sizes_he": (sizes + " (לפי דף המוצר; לבקש טבלה בס״מ)") if sizes else None,
                  "fabric_he": fabric_he(it.get("material")) or None, "url": it["url"], "contact_url": it["inq"], "supplier": skey,
                  "badge": " · ".join(badge_he), "years": y or None,
                  "checked": NOW, "first_seen": (old.get("mic-" + it["pid"]) or {}).get("first_seen", NOW),
                  "quality": it["q"], "trend": trend, "score": round(0.45 * it["q"] + 0.30 * trend + 0.25 * sizep)}
            prods.append({k: v for k, v in pr.items() if v not in (None, "", [])})
    st["kept"] = len(prods); st["suppliers"] = len(sups); st["per_type"] = {k: len(v) for k, v in final.items()}; st["drops"] = drops
    st["errors"] = st["errors"][:30]; st["finished"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    print(json.dumps({k: st[k] for k in ("searches_ok", "kept", "suppliers", "per_type", "drops")}), flush=True)
    if len(prods) < 150:
        print("too few kept — leaving the file unchanged"); json.dump(st, open(os.path.join(os.path.dirname(out) or ".", "mic_status.json"), "w"), indent=1); return 1
    # other sources (the Alibaba list) stay only when their supplier is verified (Ofir, Nov 1: "כל הספקים חייבים להיות מאומתים")
    keep = [p for p in data["products"] if p.get("source") != "Made-in-China" and (data["suppliers"].get(p.get("supplier")) or {}).get("verified")]
    st["other_kept"] = len(keep)
    used = {p["supplier"] for p in keep}
    data["products"] = sorted(keep + prods, key=lambda p: -(p.get("score") or 0))
    data["suppliers"] = {k: v for k, v in data["suppliers"].items() if k in used}
    data["suppliers"].update(sups)
    data["categories"] = CATEGORIES
    data["sources"]["Made-in-China"] = NOW
    data["updated"] = NOW; data["version"] = 2
    allsup = {p["supplier"] for p in data["products"]}
    data["stats"] = {"products": len(data["products"]), "suppliers": len(allsup),
                     "verified_suppliers": sum(1 for s in allsup if data["suppliers"].get(s, {}).get("verified")),
                     "big6": sum(1 for p in data["products"] if (p.get("max_size_rank") or 0) >= 6), "custom": sum(1 for p in data["products"] if p.get("custom_size")),
                     "per_type": st["per_type"]}
    json.dump(data, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(st, open(os.path.join(os.path.dirname(out) or ".", "mic_status.json"), "w"), indent=1)
    print("wrote", out, os.path.getsize(out), data["stats"])
    return 0

if __name__ == "__main__":
    sys.exit(main())
