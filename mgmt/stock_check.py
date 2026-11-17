# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 Louis Studios. Part of CyberCore: https://github.com/Louistuis/cybercore
"""Live JLC stock check of a BOM (run after jlc_files.py):  python3 stock_check.py [boards=5] [BOM.csv, default jlc/BOM.csv]
For every LCSC number: stock now, library type (basic / extended), and whether the stock covers boards x qty + JLC
attrition (+10 % or +5 pcs for small parts). Writes stock.csv next to the BOM. Exit 1 when a part is short or not found
(a failed lookup counts as not found). Same JLC parts API query as the status panel's check; BOM lines that
share an LCSC number are added up first."""
import collections, csv, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
BOARDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5
BOM = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(HERE, "jlc", "BOM.csv")

def jlc(code):
    body = json.dumps({"keyword": code, "currentPage": 1, "pageSize": 5})
    for _ in range(3):
        out = subprocess.run(["curl", "-s", "--max-time", "30", "-H", "Content-Type: application/json", "-A", "Mozilla/5.0", "-d", body,
                              "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"],
                             capture_output=True, text=True).stdout
        try:
            lst = (json.loads(out).get("data") or {}).get("componentPageInfo", {}).get("list") or []
            return next((c for c in lst if c.get("componentCode") == code), None)
        except ValueError:
            time.sleep(2)
    return None

lines = collections.OrderedDict()      # one row per LCSC number: BOM lines that share a part are added up
for r in csv.DictReader(open(BOM)):
    code = r["LCSC Part #"]
    if code in lines: lines[code]["Designator"] += "," + r["Designator"]; lines[code]["Comment"] += " / " + r["Comment"]
    else: lines[code] = dict(r)
rows, bad = [], []
for r in lines.values():
    code = r["LCSC Part #"]; refs = r["Designator"].split(","); per = len(refs)
    need = BOARDS * per; need += max(5, round(need * 0.1)) if per < 50 else round(need * 0.05)
    c = jlc(code)
    if not c:
        rows.append([code, r["Comment"], per, need, "", "", "NOT FOUND"]); bad.append(f"{code} {r['Comment']}: not found at JLC"); continue
    stock = c.get("stockCount") or 0; typ = c.get("componentLibraryType"); pref = c.get("preferredComponentFlag")
    status = "ok"
    if stock < need: status = "SHORT"; bad.append(f"{code} {r['Comment']} ({','.join(refs[:4])}): stock {stock} < need {need}")
    elif stock < 3 * need: status = "low"
    rows.append([code, r["Comment"], per, need, stock, ("basic" if typ == "base" else "preferred" if pref else "extended"), status])
    time.sleep(0.3)
with open(os.path.join(os.path.dirname(BOM), "stock.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["LCSC", "Part", "Per board", f"Need for {BOARDS}", "JLC stock", "Type", "Status"]); w.writerows(rows)
ext = sum(1 for x in rows if x[5] == "extended")
print(f"{len(rows)} BOM lines for {BOARDS} boards: {sum(1 for x in rows if x[6]=='ok')} ok, "
      f"{sum(1 for x in rows if x[6]=='low')} low (<3x need), {len(bad)} problem(s); {ext} extended parts (~$3 loading fee each)")
for x in rows:
    if x[6] == "low": print("LOW:", x[0], x[1], "stock", x[4], "need", x[3])
for b in bad: print("PROBLEM:", b)
sys.exit(1 if bad else 0)
