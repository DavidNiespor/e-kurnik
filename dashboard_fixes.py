# -*- coding: utf-8 -*-
"""
dashboard_fixes.py — poprawki dashboardu i nowe funkcje:
1. Dashboard: sprzedaż z przypisaniem do klienta/zamówienia
2. Czynności dzienne: poidła, karmidła z UI kafelkowym
3. Woda ręczna z cenami mediów
4. Koszty: wybór zboż z bazy
5. Import xlsx — naprawiony
Dodaj do app.py: from dashboard_fixes import register_dashboard_fixes; register_dashboard_fixes(app)
"""
from flask import request, redirect, flash, session, jsonify
from markupsafe import Markup
from flask import render_template_string
from datetime import datetime, date, timedelta
import json

def register_dashboard_fixes(app):
    from db import get_db, get_setting, save_setting
    from auth import farm_required, login_required, current_user

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    try:
        from app import R
    except ImportError:
        from app import R

    # ── init tabel ────────────────────────────────────────────────────────
    def _init():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sprzedaz_szczegol (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
            data DATE NOT NULL,
            klient_id INTEGER REFERENCES klienci(id),
            zamowienie_id INTEGER REFERENCES zamowienia(id),
            ilosc INTEGER NOT NULL,
            cena_szt REAL DEFAULT 0,
            wartosc REAL DEFAULT 0,
            typ TEXT DEFAULT 'gotowka',
            uwagi TEXT
        );
        CREATE TABLE IF NOT EXISTS media_ceny (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
            nazwa TEXT NOT NULL,
            jednostka TEXT DEFAULT 'kWh',
            cena_jedn REAL DEFAULT 0,
            od_daty DATE
        );
        CREATE TABLE IF NOT EXISTS woda_reczna (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id),
            data DATE NOT NULL,
            litry REAL DEFAULT 0,
            cena_litra REAL DEFAULT 0,
            koszt REAL DEFAULT 0,
            uwagi TEXT,
            UNIQUE(gospodarstwo_id, data)
        );
        """)
        # Dodaj kolumny jeśli brak
        for col, tbl, defval in [
            ("klient_id","produkcja","NULL"),
            ("zamowienie_id","produkcja","NULL"),
            ("typ_sprzedazy","produkcja","'gotowka'"),
        ]:
            try:
                db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} " +
                           ("INTEGER" if "id" in col else "TEXT") +
                           f" DEFAULT {defval}")
                db.commit()
            except Exception:
                pass
        db.commit(); db.close()

    _init()

    # ══════════════════════════════════════════════════════════════════════
    # 1. DASHBOARD — szybki wpis z opcją sprzedaży do klienta/zamówienia
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/produkcja/dodaj-pelny", methods=["GET","POST"])
    @farm_required
    def produkcja_dodaj_pelny():
        g = gid()
        if request.method == "POST":
            db = get_db()
            d       = request.form.get("data", date.today().isoformat())
            jaja    = int(request.form.get("jaja_zebrane",0) or 0)
            sprzed  = int(request.form.get("jaja_sprzedane",0) or 0)
            cena    = float(request.form.get("cena_sprzedazy",0) or 0)
            pasza   = float(request.form.get("pasza_wydana_kg",0) or 0)
            uwagi   = request.form.get("uwagi","")
            klient_id    = request.form.get("klient_id") or None
            zamow_id     = request.form.get("zamowienie_id") or None
            typ_sprzedazy= request.form.get("typ_sprzedazy","gotowka")

            # Upsert produkcja
            ex = db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,d)).fetchone()
            if ex:
                db.execute("""UPDATE produkcja SET jaja_zebrane=?,jaja_sprzedane=?,
                    cena_sprzedazy=?,pasza_wydana_kg=?,uwagi=?,
                    klient_id=?,zamowienie_id=?,typ_sprzedazy=? WHERE id=?""",
                    (jaja,sprzed,cena,pasza,uwagi,klient_id,zamow_id,typ_sprzedazy,ex["id"]))
            else:
                db.execute("""INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,
                    jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi,
                    klient_id,zamowienie_id,typ_sprzedazy)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (g,d,jaja,sprzed,cena,pasza,uwagi,klient_id,zamow_id,typ_sprzedazy))

            # Jeśli sprzedaż do zamówienia → oznacz jako dostarczone
            if zamow_id and sprzed > 0:
                db.execute("UPDATE zamowienia SET status='dostarczone' WHERE id=? AND gospodarstwo_id=?",
                           (zamow_id, g))

            # Zapis szczegółu sprzedaży
            if sprzed > 0:
                db.execute("""INSERT INTO sprzedaz_szczegol
                    (gospodarstwo_id,data,klient_id,zamowienie_id,ilosc,cena_szt,wartosc,typ,uwagi)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (g,d,klient_id,zamow_id,sprzed,cena,round(sprzed*cena,2),typ_sprzedazy,uwagi))

            db.commit(); db.close()
            flash("Wpis zapisany.")
            return redirect("/")

        db = get_db()
        d_param = request.args.get("data", date.today().isoformat())
        dzis = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, d_param)
        ).fetchone()
        klienci = db.execute(
            "SELECT id,nazwa FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)
        ).fetchall()
        zamowienia = db.execute(
            """SELECT z.id,z.data_dostawy,z.ilosc,k.nazwa as kn
               FROM zamowienia z LEFT JOIN klienci k ON z.klient_id=k.id
               WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')
               ORDER BY z.data_dostawy""", (g,)
        ).fetchall()
        pdz = float(gs("pasza_dzienna_kg","6"))
        db.close()

        kl_opt = '<option value="">— brak / anonimowa —</option>' + "".join(
            '<option value="' + str(k["id"]) + '" ' +
            ('selected' if dzis and dzis["klient_id"]==k["id"] else "") +
            '>' + k["nazwa"] + '</option>'
            for k in klienci
        )
        zam_opt = '<option value="">— bez zamówienia —</option>' + "".join(
            '<option value="' + str(z["id"]) + '" ' +
            ('selected' if dzis and dzis["zamowienie_id"]==z["id"] else "") +
            '>' + z["data_dostawy"] + ' · ' + (z["kn"] or "?") + ' · ' + str(z["ilosc"]) + ' szt.</option>'
            for z in zamowienia
        )

        html = (
            '<h1>Wpis produkcji i sprzedaży</h1>'
            '<div class="card"><form method="POST" id="pf">'
            '<label>Data</label><input name="data" type="date" value="' + d_param + '">'
            '<div class="g3">'
            '<div><label>Zebrane jaja</label><input name="jaja_zebrane" type="number" min="0" '
            'value="' + (str(dzis["jaja_zebrane"]) if dzis else "") + '" placeholder="0"></div>'
            '<div><label>Sprzedane (szt)</label><input name="jaja_sprzedane" type="number" min="0" '
            'value="' + (str(dzis["jaja_sprzedane"]) if dzis else "0") + '" id="sprzed" oninput="calcW()"></div>'
            '<div><label>Cena/szt (zł)</label><input name="cena_sprzedazy" type="number" step="0.01" '
            'value="' + (str(dzis["cena_sprzedazy"]) if dzis else "") + '" id="cena" oninput="calcW()"></div>'
            '</div>'
            '<div style="background:#f5f5f0;border-radius:8px;padding:10px;font-size:14px;margin-top:4px">'
            'Wartość sprzedaży: <b id="wart">0.00 zł</b></div>'
            '<h2>Sprzedaż — szczegóły</h2>'
            '<div class="g2">'
            '<div><label>Klient</label><select name="klient_id" id="kl-sel" onchange="fillZam(this.value)">' + kl_opt + '</select>'
            '<a href="/klienci/dodaj" style="font-size:12px;color:#534AB7;display:block;margin-top:4px">+ nowy klient</a></div>'
            '<div><label>Typ płatności</label><select name="typ_sprzedazy">'
            + "".join('<option value="' + v + '" ' + ('selected' if dzis and dzis.get("typ_sprzedazy")==v else "") + '>' + l + '</option>'
                      for v,l in [("gotowka","Gotówka"),("przelew","Przelew"),("z_salda","Z salda"),("nastepnym_razem","Następnym razem"),("wymiana","Wymiana / barter")])
            + '</select></div>'
            '</div>'
            '<label>Powiąż z zamówieniem</label><select name="zamowienie_id">' + zam_opt + '</select>'
            '<div class="g2">'
            '<div><label>Pasza wydana (kg)</label><input name="pasza_wydana_kg" type="number" step="0.1" '
            'value="' + (str(dzis["pasza_wydana_kg"]) if dzis else str(pdz)) + '"></div>'
            '<div><label>Uwagi</label><input name="uwagi" value="' + (dzis["uwagi"] if dzis and dzis["uwagi"] else "") + '"></div>'
            '</div>'
            '<br><button class="btn bg" style="width:100%;padding:14px;font-size:16px">Zapisz</button>'
            '</form></div>'
            '<script>'
            'function calcW(){'
            'var s=parseFloat(document.getElementById("sprzed").value)||0;'
            'var c=parseFloat(document.getElementById("cena").value)||0;'
            'document.getElementById("wart").textContent=(s*c).toFixed(2)+" zł";}'
            'calcW();'
            '</script>'
        )
        return R(html, "prod")

    # ══════════════════════════════════════════════════════════════════════
    # 2. CZYNNOŚCI DZIENNE — kafelki z poidłami i karmidłami
    # ══════════════════════════════════════════════════════════════════════
    CZYNNOSCI_DEF = [
        ("poidla",    "Poidła uzupełnione",   "💧"),
        ("karmidla",  "Karmidła uzupełnione",  "🌾"),
        ("jaja",      "Jaja zebrane",           "🥚"),
        ("sciołka",   "Ściółka sprawdzona",     "🏚"),
        ("leki",      "Witaminy / leki",        "💊"),
        ("bramka",    "Bramka zamknięta",       "🚪"),
        ("posprzatan","Kurnik posprzątany",     "🧹"),
        ("woda",      "Woda sprawdzona",        "🚰"),
    ]

    @app.route("/dzienne", methods=["GET","POST"])
    @farm_required
    def dzienne():
        g = gid()
        db = get_db()
        if request.method == "POST":
            d = date.today().isoformat()
            cz = request.form.getlist("cz")
            nota = request.form.get("nota","")
            ex = db.execute(
                "SELECT id FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?", (g,d)
            ).fetchone()
            dane = json.dumps(cz)
            if ex:
                db.execute("UPDATE dzienne_czynnosci SET czynnosci=?,notatka=? WHERE id=?",
                           (dane, nota, ex["id"]))
            else:
                db.execute("INSERT INTO dzienne_czynnosci(gospodarstwo_id,data,czynnosci,notatka) VALUES(?,?,?,?)",
                           (g, d, dane, nota))
            db.commit(); db.close()
            flash("Zapisano.")
            return redirect("/dzienne")

        d = date.today().isoformat()
        wpis = db.execute(
            "SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?", (g,d)
        ).fetchone()
        hist7 = db.execute(
            "SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 8",
            (g,)
        ).fetchall()
        db.close()

        zaznaczone = json.loads(wpis["czynnosci"]) if wpis else []
        n = len(CZYNNOSCI_DEF)

        tiles = ""
        for k, l, ico in CZYNNOSCI_DEF:
            on = k in zaznaczone
            tiles += (
                '<label style="cursor:pointer">'
                '<input type="checkbox" name="cz" value="' + k + '" ' + ('checked' if on else '') +
                ' style="display:none" onchange="this.closest(\'label\').classList.toggle(\'tile-on\',this.checked)">'
                '<div class="tile ' + ('tile-on' if on else '') + '">'
                '<div style="font-size:28px">' + ico + '</div>'
                '<div style="font-size:13px;font-weight:500;margin-top:6px">' + l + '</div>'
                '<div style="font-size:11px;margin-top:2px;color:' + ('#3B6D11' if on else '#aaa') + '">' + ('✓ Zrobione' if on else 'Kliknij') + '</div>'
                '</div></label>'
            )

        hist_html = ""
        for h in hist7:
            cz = json.loads(h["czynnosci"] or "[]")
            pct = round(len(cz)/n*100)
            kolor = "#3B6D11" if pct>=80 else "#BA7517" if pct>=50 else "#A32D2D"
            hist_html += (
                '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:13px;border-bottom:1px solid #f0ede4">'
                '<span style="min-width:80px;color:#888">' + h["data"] + '</span>'
                '<div style="flex:1;background:#e0ddd4;border-radius:4px;height:8px">'
                '<div style="width:' + str(pct) + '%;background:' + kolor + ';height:100%;border-radius:4px"></div></div>'
                '<span style="min-width:32px;text-align:right;color:' + kolor + ';font-weight:500">' + str(pct) + '%</span>'
                '</div>'
            )

        html = (
            '<style>'
            '.tile{border:2px solid #e0ddd4;border-radius:14px;padding:14px 10px;text-align:center;'
            'background:#fff;transition:all .15s;min-height:90px;display:flex;flex-direction:column;align-items:center;justify-content:center}'
            '.tile-on{border-color:#3B6D11;background:#EAF3DE}'
            '.tiles-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}'
            '@media(max-width:500px){.tiles-grid{grid-template-columns:repeat(2,1fr)}}'
            '</style>'
            '<h1>Czynności — dziś ' + d + '</h1>'
            '<div class="card"><form method="POST">'
            '<div class="tiles-grid">' + tiles + '</div>'
            '<label style="margin-top:14px">Notatka</label>'
            '<input name="nota" placeholder="opcjonalnie" value="' + (wpis["notatka"] if wpis and wpis["notatka"] else "") + '">'
            '<br><button class="btn bp" style="width:100%;margin-top:12px;padding:12px;font-size:15px">Zapisz</button>'
            '</form></div>'
            '<div class="card"><b>Ostatnie dni</b><div style="margin-top:8px">'
            + (hist_html or '<p style="color:#888;font-size:13px">Brak historii</p>')
            + '</div></div>'
            '<div style="text-align:center;margin-top:12px">'
            '<a href="/" class="btn bo bsm">← Wróć do dashboardu</a></div>'
        )
        return R(html, "dash")

    # ══════════════════════════════════════════════════════════════════════
    # 3. WODA RĘCZNA z cenami mediów
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/woda", methods=["GET","POST"])
    @farm_required
    def woda():
        g = gid()
        db = get_db()
        if request.method == "POST":
            d       = request.form.get("data", date.today().isoformat())
            litry   = float(request.form.get("litry",0) or 0)
            cena_l  = float(request.form.get("cena_litra",0) or 0)
            if cena_l == 0:
                cena_l = float(gs("cena_wody_litra","0.005"))
            koszt   = round(litry * cena_l, 2)
            uwagi   = request.form.get("uwagi","")
            ex = db.execute(
                "SELECT id FROM woda_reczna WHERE gospodarstwo_id=? AND data=?", (g,d)
            ).fetchone()
            if ex:
                db.execute("UPDATE woda_reczna SET litry=?,cena_litra=?,koszt=?,uwagi=? WHERE id=?",
                           (litry, cena_l, koszt, uwagi, ex["id"]))
            else:
                db.execute("INSERT INTO woda_reczna(gospodarstwo_id,data,litry,cena_litra,koszt,uwagi) VALUES(?,?,?,?,?,?)",
                           (g,d,litry,cena_l,koszt,uwagi))
            db.commit(); db.close()
            flash("Odczyt wody zapisany.")
            return redirect("/woda")

        historia = db.execute(
            "SELECT * FROM woda_reczna WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 30", (g,)
        ).fetchall()
        # sumy miesięczne
        mies = db.execute(
            "SELECT strftime('%Y-%m',data) as m, SUM(litry) as l, SUM(koszt) as k "
            "FROM woda_reczna WHERE gospodarstwo_id=? GROUP BY m ORDER BY m DESC LIMIT 6",
            (g,)
        ).fetchall()
        cena_wody = gs("cena_wody_litra","0.005")
        db.close()

        w = "".join(
            '<tr><td>' + r["data"] + '</td>'
            '<td style="font-weight:500">' + str(round(r["litry"],1)) + ' L</td>'
            '<td>' + str(round(r["cena_litra"],4)) + ' zł/L</td>'
            '<td>' + str(round(r["koszt"],2)) + ' zł</td>'
            '<td style="color:#888;font-size:11px">' + (r["uwagi"] or "") + '</td>'
            '</tr>'
            for r in historia
        )
        m_html = "".join(
            '<div style="display:flex;justify-content:space-between;padding:4px 0;font-size:13px;border-bottom:1px solid #f0ede4">'
            '<span style="color:#888">' + r["m"] + '</span>'
            '<span>' + str(round(r["l"],0)) + ' L</span>'
            '<span style="font-weight:500;color:#A32D2D">' + str(round(r["k"],2)) + ' zł</span>'
            '</div>'
            for r in mies
        )

        dzis_wpis = historia[0] if historia and historia[0]["data"] == date.today().isoformat() else None

        html = (
            '<h1>Woda — odczyty ręczne</h1>'
            '<div class="card"><b>Dodaj odczyt</b>'
            '<form method="POST" style="margin-top:10px">'
            '<div class="g3">'
            '<div><label>Data</label><input name="data" type="date" value="' + date.today().isoformat() + '"></div>'
            '<div><label>Zużycie (litry)</label><input name="litry" type="number" step="0.1" '
            'value="' + (str(dzis_wpis["litry"]) if dzis_wpis else "") + '" placeholder="np. 15.5"></div>'
            '<div><label>Cena za litr (zł) — puste = ' + cena_wody + ' zł</label>'
            '<input name="cena_litra" type="number" step="0.0001" placeholder="' + cena_wody + '"></div>'
            '</div>'
            '<label>Uwagi</label><input name="uwagi" placeholder="np. uzupełniono zbiornik">'
            '<br><button class="btn bp">Zapisz</button>'
            '</form></div>'
            '<div class="g2">'
            '<div class="card"><b>Sumy miesięczne</b><div style="margin-top:8px">' + (m_html or '<p style="color:#888;font-size:13px">Brak</p>') + '</div></div>'
            '<div class="card"><b>Cena wody</b>'
            '<form method="POST" action="/ustawienia/media" style="margin-top:10px">'
            '<label>Cena wody (zł/litr)</label><input name="cena_wody_litra" type="number" step="0.0001" value="' + cena_wody + '">'
            '<br><button class="btn bo bsm" style="margin-top:8px">Zapisz cenę</button>'
            '</form></div>'
            '</div>'
            '<div class="card" style="overflow-x:auto"><b>Historia 30 dni</b>'
            '<table style="margin-top:8px"><thead><tr><th>Data</th><th>Litry</th><th>Cena/L</th><th>Koszt</th><th>Uwagi</th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=5 style="color:#888;text-align:center;padding:16px">Brak wpisów</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "woda")

    @app.route("/ustawienia/media", methods=["POST"])
    @farm_required
    def ustawienia_media():
        g = gid()
        for k in ["cena_wody_litra","cena_kwh","cena_gazu_m3"]:
            v = request.form.get(k)
            if v:
                save_setting(k, v, g)
        flash("Ceny mediów zapisane.")
        return redirect(request.referrer or "/")

    # ══════════════════════════════════════════════════════════════════════
    # 4. KOSZTY — wybór zbóż z bazy składników
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/api/zboze-lista")
    @farm_required
    def api_zboze_lista():
        """Zwraca listę zbóż z bazy składników + magazynu dla dropdownu."""
        g = gid()
        db = get_db()
        # Z magazynu (już używane)
        z_mag = db.execute(
            "SELECT nazwa, kategoria, cena_aktualna as cena FROM stan_magazynu "
            "WHERE gospodarstwo_id=? AND kategoria IN ('Zboże/pasza','Witaminy/suplementy') ORDER BY nazwa",
            (g,)
        ).fetchall()
        # Z globalnej bazy składników
        try:
            z_baza = db.execute(
                "SELECT nazwa, kategoria, cena_pln_t/1000.0 as cena FROM skladniki_baza "
                "WHERE aktywny=1 ORDER BY kategoria, nazwa"
            ).fetchall()
        except Exception:
            z_baza = []
        db.close()

        wyniki = {}
        for r in list(z_mag) + list(z_baza):
            if r["nazwa"] not in wyniki:
                wyniki[r["nazwa"]] = {
                    "nazwa": r["nazwa"],
                    "kategoria": r["kategoria"],
                    "cena": round(float(r["cena"] or 0), 3)
                }
        return jsonify(sorted(wyniki.values(), key=lambda x: x["nazwa"]))

    # ══════════════════════════════════════════════════════════════════════
    # 5. IMPORT XLSX — naprawiony
    # ══════════════════════════════════════════════════════════════════════
    @app.route("/import/xlsx", methods=["GET","POST"])
    @farm_required
    def import_xlsx_page():
        g = gid()
        wyniki = None
        if request.method == "POST":
            if "plik" not in request.files:
                flash("Brak pliku.")
                return redirect("/import/xlsx")
            plik = request.files["plik"]
            if not plik.filename.endswith(".xlsx"):
                flash("Tylko pliki .xlsx")
                return redirect("/import/xlsx")
            tmp = "/tmp/ferma_import_" + str(g) + ".xlsx"
            plik.save(tmp)
            typ = request.form.get("typ","produkcja")
            wyniki = _do_import(tmp, g, typ)
            if "error" in wyniki:
                flash("Błąd: " + wyniki["error"])
            else:
                czesci = []
                if wyniki.get("produkcja"): czesci.append(f"Produkcja: {wyniki['produkcja']} wpisów")
                if wyniki.get("koszty"):    czesci.append(f"Koszty: {wyniki['koszty']} wpisów")
                if wyniki.get("receptury"): czesci.append(f"Receptury: {wyniki['receptury']}")
                flash("Import OK — " + ", ".join(czesci) + (f" | Pominięto: {len(wyniki.get('bledy',[]))}" if wyniki.get("bledy") else ""))

        html = (
            '<h1>Import danych z Excel</h1>'
            '<div class="card">'
            '<form method="POST" enctype="multipart/form-data">'
            '<label>Plik Excel (.xlsx)</label>'
            '<input type="file" name="plik" accept=".xlsx" required>'
            '<label>Co importować</label>'
            '<select name="typ">'
            '<option value="produkcja">Produkcja + koszty (arkusze JAJKA, Koszta, CHICKEN)</option>'
            '<option value="receptury">Receptury paszowe (Paszav2, Paszav3, Pasza Zimowa)</option>'
            '</select>'
            '<br><button class="btn bp" style="margin-top:12px">Importuj</button>'
            '</form></div>'
            '<div class="card"><b>Obsługiwane arkusze z Chicken.xlsx</b>'
            '<ul style="font-size:13px;color:#5f5e5a;margin-top:8px;list-style:disc;margin-left:18px;line-height:2">'
            '<li><b>JAJKA</b> — historia dzienna: zebrane jaja, sprzedane, zarobek</li>'
            '<li><b>CHICKEN</b> — alternatywny format z tym samym danymi</li>'
            '<li><b>Koszta</b> — koszty miesięczne według kategorii</li>'
            '<li><b>Paszav2 / Paszav3 / Pasza Zimowa</b> — receptury z proporcjami</li>'
            '</ul></div>'
        )
        return R(html, "ust")

    def _do_import(filepath, g, typ):
        try:
            import pandas as pd
        except ImportError:
            return {"error": "pip install pandas openpyxl --break-system-packages"}

        import os
        if not os.path.exists(filepath):
            return {"error": "Plik nie istnieje"}

        xl = pd.read_excel(filepath, sheet_name=None)
        wyniki = {"produkcja":0, "koszty":0, "receptury":0, "bledy":[]}
        db = get_db()

        if typ == "produkcja":
            # ── Arkusz JAJKA ──────────────────────────────────────────────
            for ark in ["JAJKA","CHICKEN"]:
                if ark not in xl:
                    continue
                df = xl[ark]

                # JAJKA ma czyste nagłówki
                if ark == "JAJKA":
                    df = df.dropna(subset=["Data"])
                    for _, row in df.iterrows():
                        try:
                            data = pd.to_datetime(row["Data"]).strftime("%Y-%m-%d")
                            jaja = int(float(row.get("Ilość Jajek") or 0))
                            s12  = float(row.get("Sprzedane Jajka po 1,2") or 0)
                            s10  = float(row.get("Sprzedane Jajka po 1,0") or 0)
                            sprzed = int(s12 + s10)
                            zarobek= float(row.get("Zarobek") or 0)
                            cena = round(zarobek/sprzed,2) if sprzed > 0 else 0
                            if not db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,data)).fetchone():
                                db.execute("""INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi)
                                    VALUES(?,?,?,?,?,0,'import JAJKA')""",
                                    (g,data,jaja,sprzed,cena))
                                wyniki["produkcja"] += 1
                        except Exception as e:
                            wyniki["bledy"].append(f"JAJKA {str(e)[:60]}")

                elif ark == "CHICKEN":
                    # CHICKEN: wiersz 0 = nagłówki, od wiersza 1 dane
                    try:
                        df2 = df.copy()
                        # Ustaw nagłówki z wiersza 0
                        df2.columns = df2.iloc[0].tolist()
                        df2 = df2.iloc[1:].reset_index(drop=True)
                        col_data   = df2.columns[0]   # data
                        col_kury   = df2.columns[1]   # ilość kur
                        col_jaja   = df2.columns[3]   # ilość jajek
                        col_suma   = df2.columns[12]  # suma sprzedaży

                        for _, row in df2.iterrows():
                            try:
                                raw = row[col_data]
                                if pd.isna(raw): continue
                                data = pd.to_datetime(raw).strftime("%Y-%m-%d")
                                jaja = int(float(row[col_jaja] or 0))
                                suma = float(row[col_suma] or 0)
                                if not db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g,data)).fetchone():
                                    db.execute("""INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,pasza_wydana_kg,uwagi)
                                        VALUES(?,?,?,0,'import CHICKEN')""", (g,data,jaja))
                                    wyniki["produkcja"] += 1
                            except Exception as e:
                                wyniki["bledy"].append(f"CHICKEN row: {str(e)[:60]}")
                    except Exception as e:
                        wyniki["bledy"].append(f"CHICKEN parse: {str(e)[:80]}")

            # ── Arkusz Koszta ─────────────────────────────────────────────
            if "Koszta" in xl:
                df = xl["Koszta"]
                try:
                    # Znajdź wiersz z nagłówkami (zawiera "Zwierzęta")
                    header_row = None
                    for i, row in df.iterrows():
                        vals = [str(v).lower() for v in row if not pd.isna(v)]
                        if any("zwierzęta" in v or "zwierzeta" in v for v in vals):
                            header_row = i
                            break

                    if header_row is not None:
                        df2 = df.iloc[header_row:].copy()
                        df2.columns = df2.iloc[0].tolist()
                        df2 = df2.iloc[1:].reset_index(drop=True)

                        rok_biezacy = None
                        mies_map = {
                            "styczeń":1,"luty":2,"marzec":3,"kwiecień":4,
                            "maj":5,"czerwiec":6,"czewiec":6,
                            "lipiec":7,"sierpień":8,"śierpień":8,
                            "wrzesień":9,"październik":10,"listopad":11,"grudzień":12
                        }

                        for _, row in df2.iterrows():
                            try:
                                rok_col = row.iloc[1] if len(row) > 1 else None
                                if not pd.isna(rok_col) and str(rok_col).isdigit():
                                    rok_biezacy = int(rok_col)

                                mies_raw = str(row.iloc[2]).strip().lower() if not pd.isna(row.iloc[2]) else ""
                                miesiac_nr = mies_map.get(mies_raw)
                                if not miesiac_nr or not rok_biezacy:
                                    continue

                                data_wyd = f"{rok_biezacy}-{miesiac_nr:02d}-01"
                                kat_cols = {
                                    "Zwierzęta":     ("Weterynarz", 3),
                                    "Witaminy":      ("Witaminy/suplementy", 4),
                                    "Kreda Pastewna":("Zboże/pasza", 5),
                                    "Kukurydza":     ("Zboże/pasza", 6),
                                    "Pszenica":      ("Zboże/pasza", 7),
                                    "Owies":         ("Zboże/pasza", 8),
                                    "Jęczmień":      ("Zboże/pasza", 9),
                                    "Sorgo":         ("Zboże/pasza", 10),
                                }
                                for nazwa, (kat, idx) in kat_cols.items():
                                    if idx < len(row):
                                        v = row.iloc[idx]
                                        if not pd.isna(v) and float(v or 0) > 0:
                                            db.execute("""INSERT INTO wydatki(gospodarstwo_id,data,kategoria,nazwa,
                                                ilosc,jednostka,cena_jednostkowa,wartosc_total,uwagi)
                                                VALUES(?,?,?,?,1,'import',?,?,'import Koszta')""",
                                                (g,data_wyd,kat,nazwa,float(v),float(v)))
                                            wyniki["koszty"] += 1
                            except Exception as e:
                                wyniki["bledy"].append(f"Koszta row: {str(e)[:60]}")
                except Exception as e:
                    wyniki["bledy"].append(f"Koszta: {str(e)[:80]}")

        elif typ == "receptury":
            arkusze = {
                "Paszav2":      "Z Soją (30 kur)",
                "Paszav3":      "Bez Soi (50 kur)",
                "Pasza Zimowa": "Zimowa",
            }
            for ark, nazwa_rec in arkusze.items():
                if ark not in xl:
                    continue
                try:
                    df = xl[ark]
                    # Znajdź sekcje receptur (każda zaczyna się od "Składnik" w col[0])
                    sekcje = []
                    for i, row in df.iterrows():
                        if str(row.iloc[0]).strip() == "Składnik" or str(row.iloc[0]).strip() in ["Z Soją","Bez Soji","Bez Soi","V1","Groch wysoko białkowy"]:
                            nazwa_sek = str(row.iloc[2]).strip() if len(row) > 2 and not pd.isna(row.iloc[2]) else nazwa_rec
                            sekcje.append((i, nazwa_sek))

                    for sek_idx, (start_row, sek_nazwa) in enumerate(sekcje):
                        end_row = sekcje[sek_idx+1][0] if sek_idx+1 < len(sekcje) else len(df)
                        sek_df = df.iloc[start_row+2:end_row].copy()

                        rec_nazwa = f"{ark} — {sek_nazwa}"
                        ex = db.execute("SELECT id FROM receptura WHERE gospodarstwo_id=? AND nazwa=?", (g,rec_nazwa)).fetchone()
                        if ex:
                            rid = ex["id"]
                        else:
                            rid = db.execute("INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",
                                             (g, rec_nazwa, "caly_rok")).lastrowid

                        for _, row in sek_df.iterrows():
                            try:
                                skl_nazwa = str(row.iloc[0]).strip()
                                if not skl_nazwa or skl_nazwa in ["NaN","nan","","-"] or pd.isna(row.iloc[0]):
                                    continue
                                pct = float(row.iloc[3] or 0) if len(row) > 3 and not pd.isna(row.iloc[3]) else 0
                                if pct <= 0: continue

                                mag = db.execute("SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=?",
                                                 (g, skl_nazwa)).fetchone()
                                if not mag:
                                    mid = db.execute("INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan) VALUES(?,?,?,?,0)",
                                                     (g,"Zboże/pasza",skl_nazwa,"kg")).lastrowid
                                else:
                                    mid = mag["id"]

                                if not db.execute("SELECT id FROM receptura_skladnik WHERE receptura_id=? AND magazyn_id=?", (rid,mid)).fetchone():
                                    db.execute("INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)",
                                               (rid,mid,pct))
                            except Exception as e:
                                wyniki["bledy"].append(f"{ark} skł: {str(e)[:50]}")
                        wyniki["receptury"] += 1
                except Exception as e:
                    wyniki["bledy"].append(f"{ark}: {str(e)[:80]}")

        db.commit(); db.close()
        return wyniki

    return app
