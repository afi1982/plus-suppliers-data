#!/usr/bin/env python3
"""Refresh the Made-in-China.com part of suppliers.json (runs in GitHub Actions; plain HTTP, no keys, no login).

What it does:
  1. searches Made-in-China for plus-size women's items per category (6XL+ first),
  2. opens each product page and reads: title, price tiers, MOQ, sizes, material, colours, sample price,
     supplier name, audited status, years, member level, rating, review count, images, and the supplier's
     own "Send Inquiry" link,
  3. keeps only good suppliers (audited by a third party, 3+ years, rating 4.5+ when rated),
  4. replaces the previous Made-in-China products in suppliers.json (Alibaba products, refreshed by Tab's
     daily run, are left untouched), recomputes scores and the 'updated' stamp.
If fewer than MIN_KEEP products come back (site change or block), the previous Made-in-China products stay.
"""
import json, math, os, re, sys, time, datetime, random, collections
import urllib.parse
import requests
SESSION = requests.Session()
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "suppliers.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
MIN_KEEP = 5
MAX_PAGES = int(os.environ.get("MIC_MAX_PAGES", "70"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plus_common import he_title, he_colors, he_fabric, size_rank, rank_label, quality_score, finalize, BAD_RE, WOMEN_RE

QUERIES = [
    ("tees", "plus size women t shirt 6xl"), ("tees", "plus size women tops 7xl"),
    ("shirts", "plus size women blouse 6xl"), ("shirts", "plus size women shirt 7xl"),
    ("dresses", "plus size women dress 6xl"), ("dresses", "plus size women maxi dress 7xl"),
    ("pants", "plus size women pants 6xl"), ("pants", "plus size women wide leg pants 7xl"),
    ("sets", "plus size women two piece set 6xl"), ("knit", "plus size women cardigan 6xl"),
    ("knit", "plus size women sweater 6xl"), ("jackets", "plus size women blazer 6xl"),
    ("jackets", "plus size women coat 7xl"), ("skirts", "plus size women skirt 6xl"),
    ("sport", "plus size women leggings 6xl"), ("sport", "plus size women activewear 6xl"),
]

def get(url, tries=2):
    last = None
    for i in range(tries):
        try:
            r = SESSION.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=30)
            if r.status_code != 200: raise Exception("HTTP %d" % r.status_code)
            return r.text
        except Exception as e:
            last = e; time.sleep(2 + i * 3)
    raise last

def text_of(html):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?i)<br\s*/?>|</(div|p|li|tr|h\d|span|td|th|dd|dt|a|label|em|strong|b)>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    lines = [re.sub(r"\s+", " ", unescape(l)).strip() for l in h.split("\n")]
    return [l for l in lines if l]

def search(q):
    url = "https://www.made-in-china.com/multi-search/" + urllib.parse.quote(q.replace(" ", "+")) + "/F1/1.html"
    h = get(url)
    links = re.findall(r'href="(?:https:)?(//[a-z0-9\-]+\.en\.made-in-china\.com/product/[^"#?]+\.html)"', h)
    return list(dict.fromkeys("https:" + l for l in links))

def parse_product(url, html, cat):
    L = text_of(html)
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    title = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip() if m else ""
    if not title: return None
    o = {"source": "Made-in-China", "url": url, "title_en": title, "cat_hint": cat}
    pid = re.search(r"/product/([A-Za-z0-9]+)/", url); o["id"] = "mic-" + (pid.group(1) if pid else str(abs(hash(url))))
    try: ti = L.index(title)
    except ValueError: ti = 0
    head = L[ti:ti + 90]
    joined = "\n".join(head)
    sup = {"platform": "Made-in-China"}
    for l in head[1:60]:
        if re.search(r"(CO\.,?\s*LTD\.?|Co\.,?\s*Ltd\.?|Company|Limited|Factory|Corporation|Inc\.?)$", l) and not l.startswith(("US$", "What")):
            sup["name"] = l; break
    sup["verified"] = "Audited by an independent third-party" in joined
    sup["verified_by"] = "Audited Supplier (בדיקת צד שלישי)" if sup["verified"] else None
    m = re.search(r"\n(\d+) yrs\n", joined)
    if m: sup["years"] = int(m.group(1))
    else:
        m = re.search(r"Member Since (\d{4})", joined); sup["years"] = (datetime.datetime.utcnow().year - int(m.group(1))) if m else None
    m = re.search(r"(Diamond|Gold|Silver) Member", joined); sup["member"] = m.group(1) if m else None
    m = re.search(r"\n(\d(?:\.\d)?)\n\((\d+) Reviews?\)", joined); sup["rating"] = float(m.group(1)) if m else None; sup["reviews"] = int(m.group(2)) if m else 0
    tiers = []
    for k in range(len(head) - 2):
        a, b, c = head[k], head[k + 1], head[k + 2]
        mm = re.match(r"^US\$\s?([\d.,]+)(?:\s*-\s*([\d.,]+))?$", a)
        if not mm: continue
        qb = re.match(r"^([\d,]+(?:\s*-\s*[\d,]+|\+))(?:\s*(pieces|piece|pcs|sets|set))?$", b, re.I)
        if qb:
            un = (qb.group(2) or c or "pieces").lower()
            tiers.append({"price": float(mm.group(1).replace(",", "")), "qty": qb.group(1) + (" sets" if un.startswith("set") else " pieces")})
        else:
            q = re.match(r"^([\d,]+) (Pieces|Piece|Sets|Set)$", b)
            if q and not tiers:
                tiers.append({"price": float(mm.group(1).replace(",", "")), "qty": q.group(1) + "+ " + q.group(2).lower()})
                if mm.group(2): tiers.append({"price": float(mm.group(2).replace(",", "")), "qty": q.group(1) + "+ " + q.group(2).lower()})
                break
    o["tiers"] = sorted(tiers, key=lambda t: -t["price"]) if len(tiers) == 2 and tiers[0]["qty"] == tiers[1]["qty"] else tiers
    if tiers:
        q = re.match(r"^([\d,]+)", tiers[0]["qty"]); o["moq"] = int(q.group(1).replace(",", ""))
        o["unit"] = "sets" if "set" in tiers[0]["qty"] else "pieces"
    m = re.search(r"US\$\s?([\d.]+)\s?/\s?(?:piece|set)\nRequest Sample", "\n".join(L), re.I); o["sample"] = ("Sample US$" + m.group(1)) if m else None
    attrs = {}
    for start in ("Product Attributes", "Basic Info."):
        if start in L:
            k = L.index(start) + 1
            while k + 1 < len(L) and L[k] not in ("View More", "Shipping", "Product Description") and len(attrs) < 40:
                attrs[L[k]] = L[k + 1]; k += 2
            break
    o["attrs"] = attrs
    full = "\n".join(L)
    chart = [size_rank(x) for x in re.findall(r"(?:Tag )?Size:\s*(\d{0,2}X{0,5}L)\b", full)]
    chart = [r for r in chart if r is not None]
    attr_sz = [size_rank(s) for s in re.findall(r"\b(\d{1,2}\s?XL|X{2,5}L|XL)\b", attrs.get("Size", ""), re.I)]
    attr_sz = [r for r in attr_sz if r is not None]
    title_sz = [size_rank(s) for s in re.findall(r"\b(\d{1,2}\s?XL|X{2,5}L)\b", title, re.I)]
    title_sz = [r for r in title_sz if r is not None]
    if chart: o["size_max"] = max(chart)
    elif attr_sz: o["size_max"] = max(attr_sz + title_sz)
    else: o["size_max"] = max(title_sz) if title_sz else None
    o["custom_size"] = False
    o["colors"] = [c.strip().title() for c in re.split(r"[,/;]", attrs.get("Color", "")) if c.strip() and c.strip().lower() not in ("customizable", "customized", "as picture", "/")][:12]
    mat = attrs.get("Material") or attrs.get("Fabric")
    o["material"] = mat if mat not in (None, "/", "") else None
    imgs = re.findall(r"(https://image\.made-in-china\.com/2f0j00[^\"'\s]+?\.(?:jpg|webp))", html)
    o["imgs"] = list(dict.fromkeys(imgs))[:6]
    m = re.search(r'href="(https://www\.made-in-china\.com/sendInquiry/prod_[^"]+)"', html)
    sup["contact_url"] = unescape(m.group(1)) if m else url
    m = re.search(r'href="(?:https:)?(//[a-z0-9\-]+\.en\.made-in-china\.com)/?"', html)
    sup["store"] = ("https:" + m.group(1) + "/") if m else None
    o["sup"] = sup
    o["checked"] = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    o["max_rank"] = o["size_max"]
    return o

def good(o):
    t = o["title_en"]; s = o["sup"]
    if BAD_RE.search(t) or not WOMEN_RE.search(t + " " + o["attrs"].get("Gender", "")): return False
    if re.search(r"used|second hand|bale|pre-owned|shapewear|lingerie|panties", t, re.I): return False
    if not s.get("verified") or (s.get("years") or 0) < 3: return False
    if s.get("rating") is not None and s["rating"] < 4.5: return False
    if not o["tiers"] or not o["imgs"] or not o["sup"].get("name"): return False
    if (o.get("size_max") or 0) < 5: return False
    return True

def main():
    data = json.load(open(DATA, encoding="utf-8"))
    seen, fresh = set(), []
    pages = 0; searches_ok = 0; errors = collections.Counter()
    for cat, q in QUERIES:
        try: links = search(q); searches_ok += 1
        except Exception as e: print("search failed", q, e); errors[str(e)[:40]] += 1; continue
        print(q, len(links))
        for u in links[:8]:
            if u in seen or pages >= MAX_PAGES: continue
            seen.add(u); pages += 1
            try:
                o = parse_product(u, get(u), cat)
            except Exception as e:
                print("  page failed", u[-50:], e); errors[str(e)[:40]] += 1; continue
            time.sleep(1.0 + random.random())
            if o and good(o):
                n_sup = sum(1 for f in fresh if f["sup"].get("name") == o["sup"].get("name"))
                if n_sup < 3: fresh.append(o); print("  +", o["title_en"][:70])
    print("made-in-china: kept", len(fresh), "of", pages, "pages")
    status = {"at": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z", "searches_ok": searches_ok, "searches": len(QUERIES),
              "pages": pages, "kept": len(fresh), "errors": dict(errors), "written": len(fresh) >= MIN_KEEP}
    json.dump(status, open(os.path.join(ROOT, "mic_status.json"), "w"), indent=1)
    if len(fresh) < MIN_KEEP:
        print("too few, keeping the previous Made-in-China products"); return 0
    finalize(data, fresh, source="Made-in-China")
    json.dump(data, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0

if __name__ == "__main__":
    sys.exit(main())
