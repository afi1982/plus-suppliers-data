"""Verified size range from a Made-in-China product page (v1.5.6, Nov 5 2026).
Reads the size spec rows (ld+json PropertyValue / key-value), the page's size line, FAQ/highlight text and size-chart tables;
ignores the title, keywords, "plus size" phrases, package sizes and the related-products part of the page.
size_scan() returns (max rank, snippet); rank 0 = the page states no size range (unverified)."""

import re, html as H
SZ_TOK = r"(?:\d{1,2}\s?X{1,2}L|X{1,9}L|XS|S|M|L|XL|[2-9]X)"
def _rank_tok(tok):
    tok = tok.upper().replace(" ", "")
    m = re.match(r"^(\d{1,2})X{1,2}L$", tok)
    if m: n = int(m.group(1)); return n if 1 <= n <= 12 else 0
    m = re.match(r"^(X{1,9})L$", tok)
    if m: return len(m.group(1))
    m = re.match(r"^([2-9])X$", tok)
    if m: return int(m.group(1))
    return {"XS": -1, "S": -1, "M": -1, "L": 0}.get(tok, 0)
TOK_RE = re.compile(r"(?<![A-Za-z0-9])(" + SZ_TOK + r")(?![A-Za-z0-9])", re.I)
END_MARKS = ("Customers also viewed", "Related searches", "Recommended Suppliers", "You may also like", "People who viewed", "Related videos", "Find Similar Products", "Hot Products", "Related Products")
BAD_CTX = re.compile(r"package size|packing size|carton size|box size|bag size|size of (?:the )?(?:package|box|carton)", re.I)
def page_text(h, title=""):
    parts = []; props = []
    for m in re.finditer(r'\{"@type":"PropertyValue","name":"([^"]{1,40})","value":"([^"]{0,300})"\}|\{"key":"([^"]{1,40})","value":"([^"]{0,300})"', h):
        k = m.group(1) or m.group(3); v = m.group(2) if m.group(1) else m.group(4)
        parts.append(H.unescape(k) + ": " + H.unescape(v))
        if re.search(r"(?i)size", k) and not re.search(r"(?i)package|packing|carton|box", k):
            props.append(H.unescape(v))
    for m in re.finditer(r'"(?:value|text|a|q|content|desc)":"((?:[^"\\]|\\.){8,600})"', h):
        v = m.group(1)
        if re.search(r"(?i)siz|\dXL|XXL", v) and not v.startswith("http"): parts.append(H.unescape(v.replace('\\"', '"').replace("\\n", " ")))
    b = re.sub(r"(?is)<head.*?</head>|<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", h)
    b = re.sub(r"(?i)<br\s*/?>|</(?:td|th|li|tr|p|div|dt|dd|span|h\d)>", " | ", b)
    t = H.unescape(re.sub(r"<[^>]+>", " ", b))
    t = re.sub(r"[ \t\r\n\u00a0]+", " ", t)
    cut = len(t)
    for mk in END_MARKS:
        i = t.find(mk)
        if 0 <= i < cut: cut = i
    t = t[:cut] + " | " + " | ".join(dict.fromkeys(parts)) + " || SIZEPROPS: " + " ; ".join(dict.fromkeys(props))
    if title:
        t = t.replace(title, " ")
    return t
def size_scan(t):
    """Explicit size ranges/lists stated on the page body (spec rows, size line, size chart).
    Returns (max_rank or 0, snippet). Needs a size word next to a range or >=2 size tokens, or a chart with >=3 sizes."""
    best, snip = 0, ""
    if " || SIZEPROPS: " in t:
        t, sp = t.split(" || SIZEPROPS: ", 1)
        for v in sp.split(" ; "):
            toks = TOK_RE.findall(v)
            if toks and not re.search(r"(?i)\bcm\b|inch|kg", v[:20]):
                r = max(_rank_tok(x) for x in toks)
                if r > best or (r == best and not snip): best, snip = r, v.strip()[:60]
    # 1) "size(s)" followed within 60 chars by a range or a list of sizes
    for m in re.finditer(r"(?i)\bsizes?\b(?!\s*(?:chart|guide)?\s*customi)", t):
        ctx_before = t[max(0, m.start() - 25):m.start()]
        if re.search(r"(?i)plus\s*$|big\s*$|large\s*$|package\s*$|packing\s*$|carton\s*$|box\s*$|full\s*$|one\s*$|free\s*$|any\s*$", ctx_before): continue
        seg = t[m.end():m.end() + 70]
        seg = re.split(r"(?i)\b(?:color|colour|material|fabric|weight|moq|price|style|feature|season|pattern|logo|sample|package)\b", seg)[0]
        toks = [x for x in TOK_RE.findall(seg)]
        rng = re.search(r"(?i)(" + SZ_TOK + r")\s?(?:-|–|~|to)\s?(" + SZ_TOK + r")(?![A-Za-z0-9])", seg)
        if rng or len(set(x.upper().replace(" ", "") for x in toks)) >= 2:
            r = max(_rank_tok(x) for x in toks) if toks else 0
            if rng: r = max(r, _rank_tok(rng.group(2)))
            if r > best: best, snip = r, (t[m.start():m.end() + 70].split("|")[0] + " " + seg[:40]).strip()[:80]
            elif not snip and r: snip = seg[:40]
    for m in re.finditer(r"(?i)\bsizes\b", t):
        seg = t[max(0, m.start() - 45):m.start()]
        seg = re.split(r"(?i)plus|big|large|\|", seg)[-1]
        toks = TOK_RE.findall(seg)
        if len(set(x.upper() for x in toks)) >= 2 or re.search(SZ_TOK + r"\s?(?:-|–|~|to)\s?" + SZ_TOK, seg):
            r = max(_rank_tok(x) for x in toks)
            if r > best: best, snip = r, seg.strip()[:60]
    # 2) size chart: >=3 distinct size labels separated by cells within a short window
    for m in re.finditer(r"(?:(?<![A-Za-z0-9])" + SZ_TOK + r"(?![A-Za-z0-9])\s*\|\s*(?:[\d.\-~/ ]+\|\s*){0,8}){3,}", t):
        toks = set(x.upper().replace(" ", "") for x in TOK_RE.findall(m.group(0)))
        if len(toks) >= 3:
            r = max(_rank_tok(x) for x in toks)
            if r > best: best, snip = r, "טבלת מידות: " + " ".join(sorted(toks, key=_rank_tok))[:60]
    return best, snip
CUSTOM_RE = re.compile(r"custom(?:ized|izable|ised)?\s+siz|any size|size customi|make any size|sizes? can be customi", re.I)
