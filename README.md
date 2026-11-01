# plus-suppliers-data

Data for the **ספקים** Android app (women's plus-size supplier finder for Ofir Zarfati). The app reads
`suppliers.json` from this repo live, so new data reaches the phone without a new APK.

- **Made-in-China.com products** are refreshed automatically every 6 hours by `.github/workflows/refresh.yml`
  (`scripts/refresh_mic.py`, plain public pages, no keys, no login).
- **Alibaba.com products** are refreshed by Tab (Alibaba blocks automated reads from servers with a slider
  CAPTCHA, so they are read with a real browser session and committed here).
- Only suppliers that pass the quality gate are listed: verified/audited, 3+ years, rating 4.5+ (when rated),
  quality score 60+. Sizes: 5XL and up, or custom sizing stated; 6XL+ ranked first.

Nobody here contacts, signs up with, or pays suppliers. The app opens the supplier's own contact page.
