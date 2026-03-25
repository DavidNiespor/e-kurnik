# -*- coding: utf-8 -*-
"""
fixes_v6.py — naprawia i dodaje:
1. Dashboard — kafelki poidła/karmidła/pasza widoczne od razu
2. Wykresy /analityka — po polsku, działające
3. Wydatki — wybór składników paszy z podpowiedzią ilości na rok
4. Pasza — sezon stosowania receptury, info ile składnika na rok
5. Import xlsx — naprawiony import sprzedaży
Dodaj w app.py: from fixes_v6 import register_v6; register_v6(app)
"""
from flask import request, redirect, flash, session, jsonify
from markupsafe import Markup
from flask import render_template_string
from datetime import datetime, date, timedelta
import json

def register_v6(app):
    from db import get_db, get_setting, save_setting
    from auth import farm_required, login_required, current_user
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    def _init():
        db = get_db()
        # Dodaj kolumnę sezon_stosowania do receptura jeśli brak
        for col, tbl in [("sezon_stosowania","receptura"), ("miesiac_od","receptura"), ("miesiac_do","receptura")]:
            try:
                db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} TEXT DEFAULT ''")
                db.commit()
            except Exception:
                pass
        db.close()
    _init()

    # ══════════════════════════════════════════════════════════════════════
    # 1. DASHBOARD — kafelki czynności wbudowane
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/dashboard-czynnosci", methods=["POST"])
    @farm_required
    def dashboard_czynnosci_zapisz():
        g = gid()
        db = get_db()
        d = date.today().isoformat()
        cz = request.form.getlist("cz")
        nota = request.form.get("nota","")
        dane = json.dumps(cz)
        ex = db.execute("SELECT id FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?", (g,d)).fetchone()
        if ex:
            db.execute("UPDATE dzienne_czynnosci SET czynnosci=?,notatka=? WHERE id=?", (dane,nota,ex["id"]))
        else:
            db.execute("INSERT INTO dzienne_czynnosci(gospodarstwo_id,data,czynnosci,notatka) VALUES(?,?,?,?)", (g,d,dane,nota))
        db.commit(); db.close()
        return redirect("/")

    # ══════════════════════════════════════════════════════════════════════
    # 2. WYKRESY — polska wersja z Chart.js
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/analityka")
    @farm_required
    def analityka():
        g = gid()
        db = get_db()
        kur = db.execute(
            "SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",
            (g,)
        ).fetchone()["s"] or 1

        # Ostatnie 90 dni produkcji
        prod = db.execute(
            "SELECT data, jaja_zebrane, jaja_sprzedane, pasza_wydana_kg, "
            "ROUND(CAST(jaja_zebrane AS REAL)/?*100,1) as niesnosc "
            "FROM produkcja WHERE gospodarstwo_id=? "
            "ORDER BY data DESC LIMIT 90", (kur, g)
        ).fetchall()

        # Wydatki per kategoria - ostatnie 12 miesięcy
        wyd_kat = db.execute(
            "SELECT kategoria, SUM(wartosc_total) as suma "
            "FROM wydatki WHERE gospodarstwo_id=? "
            "AND data >= date('now','-12 months') "
            "GROUP BY kategoria ORDER BY suma DESC", (g,)
        ).fetchall()

        # Miesięczne przychody vs wydatki
        mies = db.execute(
            "SELECT strftime('%Y-%m',data) as m, "
            "SUM(jaja_sprzedane*cena_sprzedazy) as przychod "
            "FROM produkcja WHERE gospodarstwo_id=? "
            "AND data >= date('now','-12 months') "
            "GROUP BY m ORDER BY m", (g,)
        ).fetchall()
        mies_wyd = db.execute(
            "SELECT strftime('%Y-%m',data) as m, SUM(wartosc_total) as wydatki "
            "FROM wydatki WHERE gospodarstwo_id=? "
            "AND data >= date('now','-12 months') "
            "GROUP BY m ORDER BY m", (g,)
        ).fetchall()
        db.close()

        # Przygotuj dane JSON dla wykresów
        prod_odwr = list(reversed(prod))
        daty   = [r["data"] for r in prod_odwr]
        niesn  = [r["niesnosc"] for r in prod_odwr]
        zebrane= [r["jaja_zebrane"] for r in prod_odwr]
        pasza  = [r["pasza_wydana_kg"] for r in prod_odwr]

        wyd_labels = [r["kategoria"] for r in wyd_kat]
        wyd_vals   = [round(r["suma"],2) for r in wyd_kat]

        # Połącz przychody i wydatki per miesiąc
        mies_dict  = {r["m"]: round(r["przychod"] or 0,2) for r in mies}
        wydatki_dict= {r["m"]: round(r["wydatki"] or 0,2) for r in mies_wyd}
        all_mies = sorted(set(list(mies_dict.keys()) + list(wydatki_dict.keys())))
        prz_vals = [mies_dict.get(m,0) for m in all_mies]
        wyd_vals2= [wydatki_dict.get(m,0) for m in all_mies]
        zysk_vals= [round(p-w,2) for p,w in zip(prz_vals,wyd_vals2)]

        # Polskie nazwy miesięcy
        def _pl_mies(ym):
            mn = ["","Sty","Lut","Mar","Kwi","Maj","Cze","Lip","Sie","Wrz","Paź","Lis","Gru"]
            try:
                y,m = ym.split("-"); return mn[int(m)]+" '"+y[2:]
            except: return ym

        mies_labels = [_pl_mies(m) for m in all_mies]

        colors = {
            "Zboże/pasza":"#534AB7","Witaminy/suplementy":"#1D9E75",
            "Weterynarz":"#D85A30","Wyposażenie":"#BA7517",
            "Prąd/gaz":"#185FA5","Ściółka":"#888780","Inne":"#9a9890"
        }
        wyd_colors = [colors.get(l,"#AFA9EC") for l in wyd_labels]

        html = (
            '<h1>Wykresy i analityka</h1>'
            '<div class="card">'
            '<b>Nieśność i zebrane jaja — ostatnie 90 dni</b>'
            '<canvas id="ch1" height="80"></canvas>'
            '</div>'
            '<div class="g2">'
            '<div class="card">'
            '<b>Wydatki wg kategorii — 12 miesięcy</b>'
            '<canvas id="ch2" height="160"></canvas>'
            '</div>'
            '<div class="card">'
            '<b>Przychody vs wydatki — 12 miesięcy</b>'
            '<canvas id="ch3" height="160"></canvas>'
            '</div>'
            '</div>'
            '<div class="card">'
            '<b>Zużycie paszy — ostatnie 90 dni (kg)</b>'
            '<canvas id="ch4" height="70"></canvas>'
            '</div>'
            '<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>'
            '<script>'
            'const DATY=' + json.dumps(daty) + ';'
            'const NIESN=' + json.dumps(niesn) + ';'
            'const ZEBR=' + json.dumps(zebrane) + ';'
            'const PASZA=' + json.dumps(pasza) + ';'
            'const WYD_L=' + json.dumps(wyd_labels) + ';'
            'const WYD_V=' + json.dumps(wyd_vals) + ';'
            'const WYD_C=' + json.dumps(wyd_colors) + ';'
            'const MIES_L=' + json.dumps(mies_labels) + ';'
            'const PRZ_V=' + json.dumps(prz_vals) + ';'
            'const WYD_V2=' + json.dumps(wyd_vals2) + ';'
            'const ZYSK_V=' + json.dumps(zysk_vals) + ';'
            '''
const FONT = {family:"system-ui,sans-serif", size:12};
const GRID = {color:"rgba(0,0,0,0.06)"};
Chart.defaults.font = FONT;

new Chart(document.getElementById("ch1"),{
  type:"line",
  data:{labels:DATY,datasets:[
    {label:"Nieśność %",data:NIESN,borderColor:"#534AB7",backgroundColor:"rgba(83,74,183,0.08)",
     tension:0.3,pointRadius:2,yAxisID:"y1"},
    {label:"Zebrane szt.",data:ZEBR,borderColor:"#1D9E75",backgroundColor:"rgba(29,158,117,0.08)",
     tension:0.3,pointRadius:2,yAxisID:"y2"}
  ]},
  options:{responsive:true,interaction:{mode:"index"},
    scales:{
      y1:{position:"left",title:{display:true,text:"Nieśność (%)"},grid:GRID},
      y2:{position:"right",title:{display:true,text:"Jaja (szt.)"},grid:{drawOnChartArea:false}}
    },
    plugins:{legend:{labels:{font:FONT}}}}
});

new Chart(document.getElementById("ch2"),{
  type:"doughnut",
  data:{labels:WYD_L,datasets:[{data:WYD_V,backgroundColor:WYD_C,borderWidth:2}]},
  options:{responsive:true,plugins:{legend:{position:"right",labels:{font:FONT,boxWidth:12}}}}
});

new Chart(document.getElementById("ch3"),{
  type:"bar",
  data:{labels:MIES_L,datasets:[
    {label:"Przychód",data:PRZ_V,backgroundColor:"rgba(29,158,117,0.7)"},
    {label:"Wydatki",data:WYD_V2,backgroundColor:"rgba(216,90,48,0.7)"},
    {label:"Zysk",data:ZYSK_V,type:"line",borderColor:"#534AB7",
     backgroundColor:"rgba(83,74,183,0.1)",tension:0.3,pointRadius:3}
  ]},
  options:{responsive:true,scales:{y:{grid:GRID}},
    plugins:{legend:{labels:{font:FONT}}}}
});

new Chart(document.getElementById("ch4"),{
  type:"bar",
  data:{labels:DATY,datasets:[
    {label:"Pasza (kg)",data:PASZA,backgroundColor:"rgba(186,117,23,0.6)",borderRadius:3}
  ]},
  options:{responsive:true,scales:{y:{grid:GRID,title:{display:true,text:"kg"}}},
    plugins:{legend:{labels:{font:FONT}}}}
});
'''
            '</script>'
        )
        return R(html, "ana")

    # ══════════════════════════════════════════════════════════════════════
    # 3. WYDATKI — wybór składników z podpowiedzią rocznego zużycia
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/api/skladnik-info")
    @farm_required
    def api_skladnik_info():
        """Zwraca info o składniku: cena, kategoria, przewidywane roczne zużycie."""
        g = gid()
        nazwa = request.args.get("nazwa","")
        db = get_db()

        # Aktywna receptura
        rec = db.execute(
            "SELECT r.id FROM receptura r "
            "WHERE r.gospodarstwo_id=? AND r.aktywna=1 LIMIT 1", (g,)
        ).fetchone()

        # Liczba kur i dzienne zużycie paszy
        kur = db.execute(
            "SELECT COALESCE(SUM(liczba),0) as s FROM stado "
            "WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'", (g,)
        ).fetchone()["s"] or 15
        pdz = float(get_setting("pasza_dzienna_kg","6",g))
        kg_rok = pdz * 365  # kg paszy rocznie

        # Procent składnika w aktywnej recepturze
        procent = 0
        if rec:
            skl = db.execute(
                "SELECT rs.procent FROM receptura_skladnik rs "
                "JOIN stan_magazynu sm ON rs.magazyn_id=sm.id "
                "WHERE rs.receptura_id=? AND LOWER(sm.nazwa)=LOWER(?)",
                (rec["id"], nazwa)
            ).fetchone()
            if skl:
                procent = float(skl["procent"] or 0)

        kg_na_rok = round(kg_rok * procent, 1)
        kg_na_miesiac = round(kg_na_rok / 12, 1)

        # Cena z bazy składników lub magazynu
        cena = 0
        from_baza = db.execute(
            "SELECT cena_pln_t FROM skladniki_baza WHERE LOWER(nazwa)=LOWER(?)", (nazwa,)
        ).fetchone()
        if from_baza:
            cena = round(from_baza["cena_pln_t"] / 1000, 3)
        else:
            from_mag = db.execute(
                "SELECT cena_aktualna FROM stan_magazynu "
                "WHERE gospodarstwo_id=? AND LOWER(nazwa)=LOWER(?)", (g, nazwa)
            ).fetchone()
            if from_mag:
                cena = round(from_mag["cena_aktualna"] or 0, 3)

        # Kategoria
        kat = "Zboże/pasza"
        from_baza2 = db.execute(
            "SELECT kategoria FROM skladniki_baza WHERE LOWER(nazwa)=LOWER(?)", (nazwa,)
        ).fetchone()
        if from_baza2:
            k = from_baza2["kategoria"]
            if k in ("premiks","mineralne","naturalny_dodatek"):
                kat = "Witaminy/suplementy"

        db.close()

        return jsonify({
            "nazwa": nazwa,
            "cena": cena,
            "kategoria": kat,
            "procent_w_recepturze": procent,
            "kg_na_rok": kg_na_rok,
            "kg_na_miesiac": kg_na_miesiac,
            "kg_paszy_rok": round(kg_rok, 0),
            "info": f"{procent*100:.1f}% receptury → {kg_na_rok} kg/rok ({kg_na_miesiac} kg/mies.)" if procent > 0 else ""
        })

    @app.route("/api/wszystkie-skladniki")
    @farm_required
    def api_wszystkie_skladniki():
        """Lista wszystkich składników z bazy + magazynu dla autouzupełniania."""
        g = gid()
        db = get_db()
        z_bazy = db.execute(
            "SELECT nazwa, kategoria, cena_pln_t/1000.0 as cena FROM skladniki_baza WHERE aktywny=1 ORDER BY nazwa"
        ).fetchall()
        z_mag = db.execute(
            "SELECT nazwa, kategoria, cena_aktualna as cena FROM stan_magazynu "
            "WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)
        ).fetchall()
        db.close()
        seen = set()
        wynik = []
        for r in list(z_bazy) + list(z_mag):
            if r["nazwa"] not in seen:
                seen.add(r["nazwa"])
                wynik.append({"nazwa": r["nazwa"], "kategoria": r["kategoria"] or "", "cena": round(float(r["cena"] or 0), 3)})
        return jsonify(wynik)

    # ══════════════════════════════════════════════════════════════════════
    # 4. PASZA — sezon stosowania receptury + info o składnikach
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/pasza/receptura/<int:rid>/sezon", methods=["POST"])
    @farm_required
    def pasza_receptura_sezon(rid):
        g = gid()
        db = get_db()
        db.execute(
            "UPDATE receptura SET sezon=?,miesiac_od=?,miesiac_do=?,sezon_stosowania=? "
            "WHERE id=? AND gospodarstwo_id=?",
            (request.form.get("sezon","caly_rok"),
             request.form.get("miesiac_od",""),
             request.form.get("miesiac_do",""),
             request.form.get("sezon_stosowania",""),
             rid, g)
        )
        db.commit(); db.close()
        flash("Sezon receptury zapisany.")
        return redirect("/pasza/receptury")

    @app.route("/pasza/skladniki-roczne")
    @farm_required
    def pasza_skladniki_roczne():
        """Ile każdego składnika potrzeba na rok przy aktywnej recepturze."""
        g = gid()
        db = get_db()
        pdz = float(gs("pasza_dzienna_kg","6"))
        kg_rok = pdz * 365

        rec = db.execute(
            "SELECT * FROM receptura WHERE gospodarstwo_id=? ORDER BY aktywna DESC, nazwa", (g,)
        ).fetchall()

        html_rek = ""
        for r in rec:
            skladniki = db.execute(
                "SELECT rs.procent, sm.nazwa, sm.stan, sm.cena_aktualna, sm.jednostka "
                "FROM receptura_skladnik rs "
                "JOIN stan_magazynu sm ON rs.magazyn_id=sm.id "
                "WHERE rs.receptura_id=? ORDER BY rs.procent DESC", (r["id"],)
            ).fetchall()
            if not skladniki: continue

            wiersze = ""
            for s in skladniki:
                pct  = float(s["procent"] or 0)
                kg_r = round(kg_rok * pct, 1)
                kg_m = round(kg_r/12, 1)
                cena = float(s["cena_aktualna"] or 0)
                koszt_r = round(kg_r * cena, 0)
                stan = float(s["stan"] or 0)
                wystarczy = round(stan / (kg_rok * pct / 365), 0) if pct > 0 and stan > 0 else 0
                kol = "#A32D2D" if stan < kg_m else "#3B6D11"
                wiersze += (
                    '<tr>'
                    '<td style="font-weight:500">' + s["nazwa"] + '</td>'
                    '<td style="text-align:right">' + str(round(pct*100,1)) + '%</td>'
                    '<td style="text-align:right;font-weight:500">' + str(kg_r) + ' kg</td>'
                    '<td style="text-align:right">' + str(kg_m) + ' kg</td>'
                    '<td style="text-align:right;color:' + kol + '">' + str(round(stan,1)) + ' kg</td>'
                    '<td style="text-align:right">' + (str(int(wystarczy))+" dni" if wystarczy > 0 else "—") + '</td>'
                    '<td style="text-align:right;color:#5f5e5a">' + (str(int(koszt_r))+" zł" if koszt_r > 0 else "—") + '</td>'
                    '</tr>'
                )

            html_rek += (
                '<div class="card">'
                '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">'
                '<b>' + r["nazwa"] + '</b>'
                + ('<span class="badge b-green">Aktywna</span>' if r["aktywna"] else '')
                + (('<span class="badge b-blue">' + (r.get("sezon_stosowania") or r.get("sezon","")) + '</span>') if (r.get("sezon_stosowania") or r.get("sezon","caly_rok")) not in ("","caly_rok") else '')
                + '<a href="/pasza/receptura/' + str(r["id"]) + '/sezon-form" class="btn bo bsm" style="margin-left:auto">Ustaw sezon</a>'
                '</div>'
                '<p style="font-size:12px;color:#888;margin-bottom:8px">'
                'Przy zużyciu ' + str(pdz) + ' kg/dzień → <b>' + str(round(kg_rok,0)) + ' kg paszy rocznie</b></p>'
                '<div style="overflow-x:auto"><table style="font-size:13px">'
                '<thead><tr>'
                '<th>Składnik</th><th style="text-align:right">%</th>'
                '<th style="text-align:right">Rocznie</th><th style="text-align:right">Miesięcznie</th>'
                '<th style="text-align:right">W magazynie</th><th style="text-align:right">Wystarczy</th>'
                '<th style="text-align:right">Koszt/rok</th>'
                '</tr></thead>'
                '<tbody>' + wiersze + '</tbody>'
                '</table></div></div>'
            )

        db.close()

        html = (
            '<h1>Zapotrzebowanie na składniki — roczne</h1>'
            '<p style="font-size:13px;color:#5f5e5a;margin-bottom:12px">'
            'Obliczenia na podstawie aktywnych receptur i dziennego zużycia paszy. '
            'Ustaw dzienne zużycie w <a href="/ustawienia" style="color:#534AB7">Ustawieniach</a>.</p>'
            + (html_rek or '<div class="card"><p style="color:#888">Brak receptur z składnikami.</p></div>')
            + '<a href="/pasza/receptury" class="btn bo bsm" style="margin-top:8px">← Receptury</a>'
        )
        return R(html, "pasza")

    @app.route("/pasza/receptura/<int:rid>/sezon-form")
    @farm_required
    def pasza_receptura_sezon_form(rid):
        g = gid()
        db = get_db()
        r = db.execute("SELECT * FROM receptura WHERE id=? AND gospodarstwo_id=?", (rid,g)).fetchone()
        db.close()
        if not r: return redirect("/pasza/receptury")

        SEZONY = [
            ("caly_rok","Cały rok"),("wiosna","Wiosna (mar-maj)"),
            ("lato","Lato (cze-sie)"),("jesien","Jesień (wrz-lis)"),("zima","Zima (gru-lut)"),
            ("wiosna_lato","Wiosna + Lato"),("jesien_zima","Jesień + Zima"),
        ]
        MIESIACE = [(1,"Styczeń"),(2,"Luty"),(3,"Marzec"),(4,"Kwiecień"),(5,"Maj"),(6,"Czerwiec"),
                    (7,"Lipiec"),(8,"Sierpień"),(9,"Wrzesień"),(10,"Październik"),(11,"Listopad"),(12,"Grudzień")]

        s_opt = "".join(
            '<option value="' + v + '" ' + ('selected' if (r.get("sezon_stosowania") or r.get("sezon","caly_rok"))==v else '') + '>' + l + '</option>'
            for v,l in SEZONY
        )
        m_od_opt = "".join(
            '<option value="' + str(nr) + '" ' + ('selected' if str(r.get("miesiac_od",""))==str(nr) else '') + '>' + n + '</option>'
            for nr,n in MIESIACE
        )
        m_do_opt = "".join(
            '<option value="' + str(nr) + '" ' + ('selected' if str(r.get("miesiac_do",""))==str(nr) else '') + '>' + n + '</option>'
            for nr,n in MIESIACE
        )

        html = (
            '<h1>Sezon stosowania: ' + r["nazwa"] + '</h1>'
            '<div class="card"><form method="POST" action="/pasza/receptura/' + str(rid) + '/sezon">'
            '<label>Sezon stosowania</label>'
            '<select name="sezon_stosowania">' + s_opt + '</select>'
            '<div class="g2" style="margin-top:10px">'
            '<div><label>Stosuj od miesiąca</label><select name="miesiac_od"><option value="">—</option>' + m_od_opt + '</select></div>'
            '<div><label>Do miesiąca</label><select name="miesiac_do"><option value="">—</option>' + m_do_opt + '</select></div>'
            '</div>'
            '<p style="font-size:12px;color:#888;margin-top:8px">'
            'System podpowie aktywną recepturę na podstawie bieżącego miesiąca.</p>'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/pasza/receptury" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )
        return R(html, "pasza")

    # ══════════════════════════════════════════════════════════════════════
    # 5. IMPORT xlsx — naprawiony import sprzedaży
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/import/xlsx", methods=["GET","POST"])
    @farm_required
    def import_xlsx_v6():
        g = gid()
        msg_html = ""
        if request.method == "POST":
            if "plik" not in request.files:
                flash("Brak pliku.")
                return redirect("/import/xlsx")
            plik = request.files["plik"]
            if not plik.filename.endswith(".xlsx"):
                flash("Tylko pliki .xlsx")
                return redirect("/import/xlsx")
            tmp = "/tmp/ferma_imp_" + str(g) + ".xlsx"
            plik.save(tmp)
            typ = request.form.get("typ","produkcja")
            wyniki = _importuj(tmp, g, typ)
            if "error" in wyniki:
                flash("Błąd: " + wyniki["error"])
            else:
                czesci = []
                if wyniki.get("produkcja"): czesci.append(f"Produkcja: {wyniki['produkcja']} dni")
                if wyniki.get("sprzedaz"):  czesci.append(f"Sprzedaż: {wyniki['sprzedaz']} transakcji")
                if wyniki.get("koszty"):    czesci.append(f"Koszty: {wyniki['koszty']} wpisów")
                if wyniki.get("receptury"): czesci.append(f"Receptury: {wyniki['receptury']}")
                flash("Import OK — " + ", ".join(czesci))
                if wyniki.get("bledy"):
                    msg_html = '<div class="al alw" style="margin-top:8px"><b>Pominięte wiersze (' + str(len(wyniki["bledy"])) + '):</b><br>' + "<br>".join(wyniki["bledy"][:5]) + '</div>'

        html = (
            '<h1>Import danych z Excel</h1>'
            + msg_html
            + '<div class="card">'
            '<form method="POST" enctype="multipart/form-data">'
            '<label>Plik Excel (.xlsx)</label>'
            '<input type="file" name="plik" accept=".xlsx" required>'
            '<label>Co importować</label>'
            '<select name="typ">'
            '<option value="produkcja">Produkcja + sprzedaż + koszty (JAJKA, CHICKEN, Koszta)</option>'
            '<option value="receptury">Receptury paszowe (Paszav2, Paszav3, Pasza Zimowa)</option>'
            '</select>'
            '<br><button class="btn bp" style="margin-top:12px">Importuj</button>'
            '</form></div>'
            '<div class="card"><b>Obsługiwane arkusze z Chicken.xlsx</b>'
            '<ul style="font-size:13px;color:#5f5e5a;margin:8px 0;list-style:disc;margin-left:18px;line-height:2">'
            '<li><b>JAJKA</b> — data, jaja, sprzedaż po 1,2zł i 1,0zł, zarobek</li>'
            '<li><b>CHICKEN</b> — alternatywny format z tymi samymi danymi</li>'
            '<li><b>Koszta</b> — koszty miesięczne wg kategorii</li>'
            '<li><b>Paszav2 / Paszav3 / Pasza Zimowa</b> — receptury z proporcjami</li>'
            '</ul></div>'
        )
        return R(html, "ust")

    def _importuj(filepath, g, typ):
        try:
            import pandas as pd
        except ImportError:
            return {"error":"pip install pandas openpyxl"}
        import os
        if not os.path.exists(filepath):
            return {"error":"Plik nie istnieje"}

        xl = pd.read_excel(filepath, sheet_name=None)
        wyniki = {"produkcja":0,"sprzedaz":0,"koszty":0,"receptury":0,"bledy":[]}
        db = get_db()

        if typ == "produkcja":
            # ── JAJKA ────────────────────────────────────────────────────
            if "JAJKA" in xl:
                df = xl["JAJKA"].dropna(subset=["Data"])
                for _, row in df.iterrows():
                    try:
                        data  = pd.to_datetime(row["Data"]).strftime("%Y-%m-%d")
                        jaja  = int(float(row.get("Ilość Jajek") or 0))
                        # Sprzedaż — suma obu cen
                        s12   = float(row.get("Sprzedane Jajka po 1,2") or 0)
                        s10   = float(row.get("Sprzedane Jajka po 1,0") or 0)
                        sprzed= int(s12 + s10)
                        zarobek = float(row.get("Zarobek") or 0)
                        # Oblicz cenę ważoną
                        if sprzed > 0:
                            cena = round(zarobek / sprzed, 2)
                        else:
                            cena = 0

                        ex = db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,data)).fetchone()
                        if not ex:
                            db.execute("""INSERT INTO produkcja
                                (gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi)
                                VALUES(?,?,?,?,?,0,'import JAJKA')""",
                                (g,data,jaja,sprzed,cena))
                            wyniki["produkcja"] += 1
                            if sprzed > 0:
                                wyniki["sprzedaz"] += 1
                        else:
                            # Aktualizuj sprzedaż jeśli brakuje
                            cur = db.execute("SELECT jaja_sprzedane,cena_sprzedazy FROM produkcja WHERE id=?", (ex["id"],)).fetchone()
                            if cur["jaja_sprzedane"] == 0 and sprzed > 0:
                                db.execute("UPDATE produkcja SET jaja_sprzedane=?,cena_sprzedazy=? WHERE id=?",
                                           (sprzed,cena,ex["id"]))
                                wyniki["sprzedaz"] += 1
                    except Exception as e:
                        wyniki["bledy"].append(f"JAJKA: {str(e)[:60]}")

            # ── Koszta ───────────────────────────────────────────────────
            if "Koszta" in xl:
                df = xl["Koszta"]
                # Znajdź wiersz nagłówkowy
                header_row = None
                for i, row in df.iterrows():
                    vals = [str(v) for v in row if not __import__("pandas").isna(v)]
                    if any("zwierz" in v.lower() for v in vals):
                        header_row = i; break

                if header_row is not None:
                    import pandas as pd2
                    df2 = df.iloc[header_row:].copy()
                    df2.columns = [str(v) for v in df2.iloc[0]]
                    df2 = df2.iloc[1:].reset_index(drop=True)
                    mies_map = {"styczeń":1,"luty":2,"marzec":3,"kwiecień":4,"maj":5,"czerwiec":6,
                                "czewiec":6,"lipiec":7,"sierpień":8,"śierpień":8,
                                "wrzesień":9,"październik":10,"listopad":11,"grudzień":12}
                    rok_b = None
                    for _, row in df2.iterrows():
                        try:
                            import pandas as pd3
                            if not pd3.isna(row.iloc[1]) and str(row.iloc[1]).strip().isdigit():
                                rok_b = int(row.iloc[1])
                            mies_raw = str(row.iloc[2]).strip().lower() if not pd3.isna(row.iloc[2]) else ""
                            m_nr = mies_map.get(mies_raw)
                            if not m_nr or not rok_b: continue
                            data_w = f"{rok_b}-{m_nr:02d}-01"
                            kat_idx = {"Zwierzęta":("Weterynarz",3),"Witaminy":("Witaminy/suplementy",4),
                                       "Kreda Pastewna":("Zboże/pasza",5),"Kukurydza":("Zboże/pasza",6),
                                       "Pszenica":("Zboże/pasza",7),"Owies":("Zboże/pasza",8),
                                       "Jęczmień":("Zboże/pasza",9),"Sorgo":("Zboże/pasza",10)}
                            for nazwa,(kat,idx) in kat_idx.items():
                                if idx < len(row):
                                    v = row.iloc[idx]
                                    if not pd3.isna(v) and float(v or 0) > 0:
                                        db.execute("""INSERT INTO wydatki(gospodarstwo_id,data,kategoria,
                                            nazwa,ilosc,jednostka,cena_jednostkowa,wartosc_total,uwagi)
                                            VALUES(?,?,?,?,1,'import',?,?,'import Koszta')""",
                                            (g,data_w,kat,nazwa,float(v),float(v)))
                                        wyniki["koszty"] += 1
                        except Exception as e:
                            wyniki["bledy"].append(f"Koszta: {str(e)[:60]}")

        elif typ == "receptury":
            ARKUSZE = {"Paszav2":"Z Soją","Paszav3":"Z Soją v3","Pasza Zimowa":"Zimowa"}
            import pandas as pd
            for ark, domyslna in ARKUSZE.items():
                if ark not in xl: continue
                df = xl[ark]
                try:
                    sekcje = []
                    for i, row in df.iterrows():
                        c0 = str(row.iloc[0]).strip()
                        c2 = str(row.iloc[2]).strip() if len(row)>2 and not pd.isna(row.iloc[2]) else ""
                        if c2 in ["Z Soją","Bez Soji","Bez Soi","V1","Groch wysoko białkowy","Zimowa","Arkusz1"]:
                            sekcje.append((i, c2))
                        elif c0 == "Składnik" and not sekcje:
                            sekcje.append((i, domyslna))

                    if not sekcje:
                        sekcje = [(0, domyslna)]

                    for si, (start, sek_nazwa) in enumerate(sekcje):
                        end = sekcje[si+1][0] if si+1 < len(sekcje) else len(df)
                        sek_df = df.iloc[start+2:end]
                        rec_nazwa = sek_nazwa
                        ex = db.execute("SELECT id FROM receptura WHERE gospodarstwo_id=? AND nazwa=?", (g,rec_nazwa)).fetchone()
                        rid = ex["id"] if ex else db.execute(
                            "INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",
                            (g,rec_nazwa,"caly_rok")).lastrowid

                        for _, row in sek_df.iterrows():
                            try:
                                skl = str(row.iloc[0]).strip()
                                if not skl or skl in ["nan","NaN","Składnik","Liczba Kur","KG/KURA",""]: continue
                                if pd.isna(row.iloc[0]): continue
                                pct = float(row.iloc[3] or 0) if len(row)>3 and not pd.isna(row.iloc[3]) else 0
                                if pct <= 0: continue
                                mag = db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=?", (g,skl)).fetchone()
                                mid = mag["id"] if mag else db.execute(
                                    "INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan) VALUES(?,?,?,?,0)",
                                    (g,"Zboże/pasza",skl,"kg")).lastrowid
                                if not db.execute("SELECT id FROM receptura_skladnik WHERE receptura_id=? AND magazyn_id=?", (rid,mid)).fetchone():
                                    db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)", (rid,mid,pct))
                            except Exception as e:
                                wyniki["bledy"].append(f"{ark} {sek_nazwa}: {str(e)[:50]}")
                        wyniki["receptury"] += 1
                except Exception as e:
                    wyniki["bledy"].append(f"{ark}: {str(e)[:80]}")

        db.commit(); db.close()
        return wyniki

    return app
