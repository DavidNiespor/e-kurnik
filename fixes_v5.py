# -*- coding: utf-8 -*-
"""
fixes_v5.py — poprawki i nowe funkcje
Dodaj do app.py: from fixes_v5 import register_fixes; register_fixes(app)
"""
from flask import request, redirect, flash, session, jsonify
from markupsafe import Markup
from datetime import datetime, date, timedelta
import json

def register_fixes(app):
    from db import get_db, get_setting, save_setting
    from auth import (farm_required, login_required, superadmin_required,
                      current_user, current_farm, create_farm)

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    # ─── HELPER: wspólny R() działający bez templates.py ─────────────────────
    from flask import render_template_string
    try:
        from app import R
    except ImportError:
        from app import R

    # ════════════════════════════════════════════════════════════════════════
    # 1. WYPOSAŻENIE — zakładka której brakowało
    # ════════════════════════════════════════════════════════════════════════
    STANY_WYPOS = ["sprawne", "wymaga przeglądu", "uszkodzone", "wycofane"]
    KAT_WYPOS   = ["Karmidło", "Poideło", "Gniazdo", "Oświetlenie",
                   "Grzewcze", "Ogrodzenie", "Narzędzia", "Inne"]

    @app.route("/wyposazenie")
    @farm_required
    def wyposazenie():
        g = gid()
        db = get_db()
        rows = db.execute(
            "SELECT * FROM wyposazenie WHERE gospodarstwo_id=? ORDER BY stan, nazwa",
            (g,)
        ).fetchall()
        db.close()
        sbdg = {"sprawne":"b-green","wymaga przeglądu":"b-amber",
                "uszkodzone":"b-red","wycofane":"b-gray"}
        today = date.today().isoformat()
        w = "".join(
            '<tr>'
            '<td style="font-weight:500">' + r["nazwa"] + '</td>'
            '<td><span class="badge b-blue">' + (r["kategoria"] or "") + '</span></td>'
            '<td><span class="badge ' + sbdg.get(r["stan"],"b-gray") + '">' + (r["stan"] or "") + '</span></td>'
            '<td>' + (r["data_zakupu"] or "—") + '</td>'
            '<td>' + (str(round(r["cena"],2)) + " zł" if r["cena"] else "—") + '</td>'
            '<td style="color:' + ('#A32D2D' if r["nastepny_przeglad"] and r["nastepny_przeglad"] <= today else '#2c2c2a') + '">'
            + (r["nastepny_przeglad"] or "—") + '</td>'
            '<td class="nowrap">'
            '<a href="/wyposazenie/' + str(r["id"]) + '/edytuj" class="btn bo bsm">Edytuj</a> '
            '<a href="/wyposazenie/' + str(r["id"]) + '/usun" class="btn br bsm" onclick="return confirm(\'Usunąć?\')">✕</a>'
            '</td></tr>'
            for r in rows
        )
        html = (
            '<h1>Wyposażenie kurnika</h1>'
            '<a href="/wyposazenie/dodaj" class="btn bp bsm" style="margin-bottom:12px">+ Dodaj pozycję</a>'
            '<div class="card" style="overflow-x:auto"><table>'
            '<thead><tr><th>Nazwa</th><th>Kategoria</th><th>Stan</th>'
            '<th>Zakup</th><th>Cena</th><th>Następny przegląd</th><th></th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=7 style="color:#888;text-align:center;padding:20px">Brak wyposażenia</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "wyp")

    def _wypos_form(action, v=None):
        v = v or {}
        kat_opt = "".join('<option value="' + k + '" ' + ('selected' if v.get("kategoria")==k else '') + '>' + k + '</option>' for k in KAT_WYPOS)
        stan_opt= "".join('<option value="' + s + '" ' + ('selected' if v.get("stan")==s else '') + '>' + s + '</option>' for s in STANY_WYPOS)
        return (
            '<div class="card"><form method="POST" action="' + action + '">'
            '<label>Nazwa</label><input name="nazwa" required value="' + v.get("nazwa","") + '">'
            '<div class="g2">'
            '<div><label>Kategoria</label><select name="kategoria">' + kat_opt + '</select></div>'
            '<div><label>Stan</label><select name="stan">' + stan_opt + '</select></div>'
            '</div>'
            '<div class="g3">'
            '<div><label>Data zakupu</label><input name="data_zakupu" type="date" value="' + (v.get("data_zakupu") or "") + '"></div>'
            '<div><label>Cena (zł)</label><input name="cena" type="number" step="0.01" value="' + str(v.get("cena","")) + '"></div>'
            '<div><label>Następny przegląd</label><input name="nastepny_przeglad" type="date" value="' + (v.get("nastepny_przeglad") or "") + '"></div>'
            '</div>'
            '<label>Uwagi</label><textarea name="uwagi" rows="2">' + (v.get("uwagi","")) + '</textarea>'
            '<br><button class="btn bp">Zapisz</button>'
            '<a href="/wyposazenie" class="btn bo" style="margin-left:8px">Anuluj</a>'
            '</form></div>'
        )

    @app.route("/wyposazenie/dodaj", methods=["GET","POST"])
    @farm_required
    def wyposazenie_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            db.execute(
                "INSERT INTO wyposazenie(gospodarstwo_id,nazwa,kategoria,data_zakupu,cena,stan,nastepny_przeglad,uwagi) VALUES(?,?,?,?,?,?,?,?)",
                (g, request.form["nazwa"], request.form.get("kategoria","Inne"),
                 request.form.get("data_zakupu","") or None,
                 float(request.form.get("cena",0) or 0),
                 request.form.get("stan","sprawne"),
                 request.form.get("nastepny_przeglad","") or None,
                 request.form.get("uwagi",""))
            )
            db.commit(); db.close()
            flash("Dodano do wyposażenia.")
            return redirect("/wyposazenie")
        return R('<h1>Nowa pozycja wyposażenia</h1>' + _wypos_form("/wyposazenie/dodaj"), "wyp")

    @app.route("/wyposazenie/<int:wid>/edytuj", methods=["GET","POST"])
    @farm_required
    def wyposazenie_edytuj(wid):
        g = gid()
        db = get_db()
        if request.method == "POST":
            db.execute(
                "UPDATE wyposazenie SET nazwa=?,kategoria=?,data_zakupu=?,cena=?,stan=?,nastepny_przeglad=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                (request.form["nazwa"], request.form.get("kategoria","Inne"),
                 request.form.get("data_zakupu","") or None,
                 float(request.form.get("cena",0) or 0),
                 request.form.get("stan","sprawne"),
                 request.form.get("nastepny_przeglad","") or None,
                 request.form.get("uwagi",""), wid, g)
            )
            db.commit(); db.close()
            flash("Zaktualizowano.")
            return redirect("/wyposazenie")
        r = dict(db.execute("SELECT * FROM wyposazenie WHERE id=? AND gospodarstwo_id=?", (wid,g)).fetchone() or {})
        db.close()
        return R('<h1>Edytuj wyposażenie</h1>' + _wypos_form("/wyposazenie/"+str(wid)+"/edytuj", r), "wyp")

    @app.route("/wyposazenie/<int:wid>/usun")
    @farm_required
    def wyposazenie_usun(wid):
        g = gid()
        db = get_db()
        db.execute("DELETE FROM wyposazenie WHERE id=? AND gospodarstwo_id=?", (wid,g))
        db.commit(); db.close()
        flash("Usunięto.")
        return redirect("/wyposazenie")

    # ════════════════════════════════════════════════════════════════════════
    # 2. POIDŁA / KARMIDŁA — manualne uzupełnienie z zaznaczeniem
    # ════════════════════════════════════════════════════════════════════════
    @app.route("/dzienne-czynnosci", methods=["GET","POST"])
    @farm_required
    def dzienne_czynnosci():
        g = gid()
        db = get_db()
        if request.method == "POST":
            dzis = date.today().isoformat()
            czynnosci = request.form.getlist("czynnosc")
            notatka   = request.form.get("notatka","")
            istn = db.execute(
                "SELECT id FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",
                (g, dzis)
            ).fetchone()
            dane = json.dumps(czynnosci)
            if istn:
                db.execute(
                    "UPDATE dzienne_czynnosci SET czynnosci=?,notatka=? WHERE id=?",
                    (dane, notatka, istn["id"])
                )
            else:
                db.execute(
                    "INSERT INTO dzienne_czynnosci(gospodarstwo_id,data,czynnosci,notatka) VALUES(?,?,?,?)",
                    (g, dzis, dane, notatka)
                )
            db.commit(); db.close()
            flash("Czynności zapisane.")
            return redirect("/dzienne-czynnosci")

        dzis = date.today().isoformat()
        wpis_dzis = db.execute(
            "SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? AND data=?",
            (g, dzis)
        ).fetchone()
        historia = db.execute(
            "SELECT * FROM dzienne_czynnosci WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 7",
            (g,)
        ).fetchall()
        db.close()

        zaznaczone = json.loads(wpis_dzis["czynnosci"]) if wpis_dzis else []

        CZYNNOSCI = [
            ("poidla_uzupelnione",   "Poidła uzupełnione"),
            ("karmidla_uzupelnione", "Karmidła uzupełnione"),
            ("jaja_zebrane",         "Jaja zebrane"),
            ("sciola_sprawdzona",    "Ściółka sprawdzona"),
            ("kurnik_posprzatany",   "Kurnik posprzątany"),
            ("leki_podane",          "Leki / witaminy podane"),
            ("bramka_zamknieta",     "Bramka zamknięta na noc"),
            ("woda_sprawdzona",      "Woda sprawdzona"),
        ]

        checkboxy = "".join(
            '<label style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f0ede4;cursor:pointer;font-size:15px">'
            '<input type="checkbox" name="czynnosc" value="' + k + '" '
            + ('checked' if k in zaznaczone else '') +
            ' style="width:20px;height:20px;accent-color:#534AB7">'
            '<span style="' + ('text-decoration:line-through;color:#888' if k in zaznaczone else '') + '">'
            + l + '</span>'
            '</label>'
            for k, l in CZYNNOSCI
        )

        # Statystyki ostatnich 7 dni
        stats_html = ""
        for h in historia:
            cz = json.loads(h["czynnosci"] or "[]")
            pct = round(len(cz) / len(CZYNNOSCI) * 100)
            kolor = "#3B6D11" if pct >= 80 else "#BA7517" if pct >= 50 else "#A32D2D"
            stats_html += (
                '<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px">'
                '<span style="min-width:80px;color:#888">' + h["data"] + '</span>'
                '<div style="flex:1;background:#e0ddd4;border-radius:4px;height:8px">'
                '<div style="width:' + str(pct) + '%;background:' + kolor + ';height:100%;border-radius:4px"></div></div>'
                '<span style="min-width:30px;color:' + kolor + ';font-weight:500">' + str(pct) + '%</span>'
                '</div>'
            )

        html = (
            '<h1>Czynności dzienne</h1>'
            '<div class="g2">'
            '<div class="card">'
            '<b>Dziś — ' + dzis + '</b>'
            '<form method="POST" style="margin-top:12px">'
            + checkboxy
            + '<label style="margin-top:12px">Notatka</label>'
            '<textarea name="notatka" rows="2" placeholder="opcjonalnie">'
            + (wpis_dzis["notatka"] if wpis_dzis and wpis_dzis["notatka"] else "") +
            '</textarea>'
            '<br><button class="btn bp" style="margin-top:12px;width:100%">Zapisz</button>'
            '</form>'
            '</div>'
            '<div class="card"><b>Ostatnie 7 dni</b>'
            '<div style="margin-top:12px">' + (stats_html or '<p style="color:#888;font-size:13px">Brak historii</p>') + '</div>'
            '</div>'
            '</div>'
        )
        return R(html, "dash")

    # ════════════════════════════════════════════════════════════════════════
    # 3. LICZNIK ENERGII — wpis ręczny + predykcja
    # ════════════════════════════════════════════════════════════════════════
    @app.route("/energia", methods=["GET","POST"])
    @farm_required
    def energia():
        g = gid()
        db = get_db()
        if request.method == "POST":
            action = request.form.get("action","wpis")
            if action == "wpis":
                dzis = request.form.get("data", date.today().isoformat())
                kwh  = float(request.form.get("kwh",0) or 0)
                odczyt = float(request.form.get("odczyt_licznika",0) or 0)
                cena_kwh = float(request.form.get("cena_kwh",0) or 0) or float(gs("cena_kwh","0.80"))
                koszt = round(kwh * cena_kwh, 2)
                if db.execute("SELECT id FROM prad_odczyty WHERE gospodarstwo_id=? AND data=?", (g,dzis)).fetchone():
                    db.execute("UPDATE prad_odczyty SET kwh=?,odczyt_licznika=?,koszt=? WHERE gospodarstwo_id=? AND data=?",
                               (kwh, odczyt, koszt, g, dzis))
                else:
                    db.execute("INSERT INTO prad_odczyty(gospodarstwo_id,data,kwh,odczyt_licznika,koszt) VALUES(?,?,?,?,?)",
                               (g, dzis, kwh, odczyt, koszt))
                db.commit()
                flash("Odczyt zapisany.")
            db.close()
            return redirect("/energia")

        # Dane do wyświetlenia
        odczyty = db.execute(
            "SELECT * FROM prad_odczyty WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 60",
            (g,)
        ).fetchall()
        cena_kwh = float(gs("cena_kwh","0.80"))

        # Suma bieżący miesiąc
        miesiac = db.execute(
            "SELECT COALESCE(SUM(kwh),0) as kwh, COALESCE(SUM(koszt),0) as koszt "
            "FROM prad_odczyty WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",
            (g,)
        ).fetchone()

        # Predykcja do końca roku
        avg30 = db.execute(
            "SELECT AVG(kwh) as a FROM prad_odczyty WHERE gospodarstwo_id=? AND data>=date('now','-30 days')",
            (g,)
        ).fetchone()["a"] or 0

        today = date.today()
        koniec_roku = date(today.year, 12, 31)
        dni_do_konca = (koniec_roku - today).days
        pred_kwh  = round(avg30 * dni_do_konca, 1)
        pred_koszt= round(pred_kwh * cena_kwh, 2)

        # Sierpniowy alert (zamów/przygotuj)
        sierpien_alert = ""
        if today.month in (7, 8):
            sierpien_alert = (
                '<div class="al alw"><b>Sierpień — czas planować zimę!</b><br>'
                'Przewidywane zużycie do końca roku: <b>' + str(pred_kwh) + ' kWh</b> '
                '(' + str(pred_koszt) + ' zł). '
                'Sprawdź stan instalacji elektrycznej i oświetlenia przed sezonem jesiennym.</div>'
            )

        db.close()

        # Ostatni odczyt licznika
        ostatni = odczyty[0] if odczyty else None

        w = "".join(
            '<tr><td>' + r["data"] + '</td>'
            '<td style="font-weight:500">' + str(round(r["kwh"],3)) + ' kWh</td>'
            '<td style="color:#888">' + (str(round(r["odczyt_licznika"],1)) if r["odczyt_licznika"] else "—") + '</td>'
            '<td>' + str(round(r["koszt"],2)) + ' zł</td>'
            '</tr>'
            for r in odczyty
        )

        html = (
            sierpien_alert
            + '<h1>Licznik energii</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            '<div class="card stat"><div class="v">' + str(round(miesiac["kwh"],2)) + ' kWh</div><div class="l">Ten miesiąc</div></div>'
            '<div class="card stat"><div class="v" style="color:#A32D2D">' + str(round(miesiac["koszt"],2)) + ' zł</div><div class="l">Koszt miesiąc</div></div>'
            '<div class="card stat"><div class="v" style="color:#534AB7">' + str(pred_kwh) + ' kWh</div><div class="l">Predykcja do końca roku</div><div class="s">' + str(pred_koszt) + ' zł</div></div>'
            '</div>'
            '<div class="card"><b>Dodaj odczyt</b>'
            '<form method="POST" style="margin-top:10px">'
            '<input type="hidden" name="action" value="wpis">'
            '<div class="g3">'
            '<div><label>Data</label><input name="data" type="date" value="' + today.isoformat() + '"></div>'
            '<div><label>Zużycie (kWh)</label><input name="kwh" type="number" step="0.001" placeholder="np. 2.450"></div>'
            '<div><label>Stan licznika (kWh)</label><input name="odczyt_licznika" type="number" step="0.1" value="' + (str(ostatni["odczyt_licznika"]) if ostatni and ostatni["odczyt_licznika"] else "") + '"></div>'
            '</div>'
            '<div class="g2">'
            '<div><label>Cena kWh (zł) — zostaw puste = z ustawień (' + str(cena_kwh) + ' zł)</label>'
            '<input name="cena_kwh" type="number" step="0.01" placeholder="' + str(cena_kwh) + '"></div>'
            '</div>'
            '<br><button class="btn bp">Zapisz odczyt</button>'
            '</form></div>'
            '<div class="card" style="overflow-x:auto"><b>Historia</b>'
            '<table style="margin-top:8px"><thead><tr><th>Data</th><th>Zużycie</th><th>Stan licznika</th><th>Koszt</th></tr></thead>'
            '<tbody>' + (w or '<tr><td colspan=4 style="color:#888;text-align:center;padding:16px">Brak odczytów</td></tr>') + '</tbody></table></div>'
        )
        return R(html, "wyd")

    # ════════════════════════════════════════════════════════════════════════
    # 4. PREDYKCJA PASZY DO KOŃCA ROKU
    # ════════════════════════════════════════════════════════════════════════
    @app.route("/pasza/predykcja")
    @farm_required
    def pasza_predykcja():
        g = gid()
        db = get_db()
        pdz = float(gs("pasza_dzienna_kg","6"))
        today = date.today()

        # Faktyczne zużycie ostatnie 30 dni
        avg_zuzycie = db.execute(
            "SELECT AVG(pasza_wydana_kg) as a FROM produkcja "
            "WHERE gospodarstwo_id=? AND pasza_wydana_kg>0 AND data>=date('now','-30 days')",
            (g,)
        ).fetchone()["a"] or pdz

        # Stan paszy gotowej
        wyprod = db.execute("SELECT COALESCE(SUM(ilosc_kg),0) as s FROM mieszania WHERE gospodarstwo_id=?", (g,)).fetchone()["s"]
        wydana = db.execute("SELECT COALESCE(SUM(pasza_wydana_kg),0) as s FROM produkcja WHERE gospodarstwo_id=?", (g,)).fetchone()["s"]
        pasza_gotowa = max(0, wyprod - wydana)

        # Stan składników
        skladniki = db.execute(
            "SELECT nazwa, stan, min_zapas FROM stan_magazynu WHERE gospodarstwo_id=? AND stan>0",
            (g,)
        ).fetchall()

        # Oblicz ile paszy można zrobić z obecnych zapasów
        aktywna_rec = db.execute("SELECT id FROM receptura WHERE gospodarstwo_id=? AND aktywna=1", (g,)).fetchone()
        max_mozliwa = 0
        if aktywna_rec:
            skl_rec = db.execute("""
                SELECT rs.procent, sm.stan FROM receptura_skladnik rs
                JOIN stan_magazynu sm ON rs.magazyn_id=sm.id
                WHERE rs.receptura_id=?
            """, (aktywna_rec["id"],)).fetchall()
            if skl_rec:
                mx = min(
                    (s["stan"] / (s["procent"]/100) for s in skl_rec if s["procent"] > 0),
                    default=0
                )
                max_mozliwa = round(mx, 1)

        koniec_roku = date(today.year, 12, 31)
        koniec_sezonu_letniego = date(today.year, 8, 31)
        dni_do_konca_roku = (koniec_roku - today).days
        dni_do_konca_lata = max(0, (koniec_sezonu_letniego - today).days)

        zapas_total  = pasza_gotowa + max_mozliwa
        wystarczy_na = round(zapas_total / avg_zuzycie, 0) if avg_zuzycie > 0 else 0

        potrzeba_do_konca_roku   = round(avg_zuzycie * dni_do_konca_roku, 1)
        brakuje_do_konca_roku    = max(0, round(potrzeba_do_konca_roku - zapas_total, 1))
        potrzeba_do_konca_lata   = round(avg_zuzycie * dni_do_konca_lata, 1)

        # Alert sierpniowy
        sierpien_alert = ""
        if today.month in (7, 8) and brakuje_do_konca_roku > 0:
            sierpien_alert = (
                '<div class="al ald"><b>SIERPIEŃ — zamów składniki!</b><br>'
                'Brakuje <b>' + str(brakuje_do_konca_roku) + ' kg paszy</b> do końca roku.<br>'
                'Przy obecnym zużyciu ' + str(round(avg_zuzycie,1)) + ' kg/dzień zapasy wystarczą na '
                + str(int(wystarczy_na)) + ' dni.</div>'
            )
        elif today.month == 7:
            sierpien_alert = (
                '<div class="al alw">Lipiec — sprawdź zapasy przed zimą. '
                'Potrzeba do końca roku: <b>' + str(potrzeba_do_konca_roku) + ' kg</b></div>'
            )

        # Miesięczna tabela predykcji
        wiersze_pred = ""
        for i in range(1, 13):
            m = date(today.year, i, 1)
            if m.month < today.month:
                continue
            ostatni_dzien = (date(today.year, i % 12 + 1, 1) - timedelta(days=1)) if i < 12 else date(today.year, 12, 31)
            dni_w_mies = (ostatni_dzien - max(m, today)).days + 1
            potrzeba_m = round(avg_zuzycie * dni_w_mies, 1)
            wiersze_pred += (
                '<tr><td>' + m.strftime("%B %Y") + '</td>'
                '<td>' + str(dni_w_mies) + '</td>'
                '<td style="font-weight:500">' + str(potrzeba_m) + ' kg</td>'
                '</tr>'
            )

        db.close()

        html = (
            sierpien_alert
            + '<h1>Predykcja paszy — do końca roku</h1>'
            '<div class="g3" style="margin-bottom:12px">'
            '<div class="card stat"><div class="v">' + str(round(pasza_gotowa,1)) + ' kg</div><div class="l">Pasza gotowa</div></div>'
            '<div class="card stat"><div class="v" style="color:#534AB7">' + str(max_mozliwa) + ' kg</div><div class="l">Można wyprodukować</div><div class="s">ze składników w magazynie</div></div>'
            '<div class="card stat"><div class="v" style="color:' + ('#A32D2D' if brakuje_do_konca_roku > 0 else '#3B6D11') + '">'
            + (str(brakuje_do_konca_roku) + ' kg' if brakuje_do_konca_roku > 0 else 'Wystarczy') + '</div>'
            '<div class="l">' + ('Brakuje do końca roku' if brakuje_do_konca_roku > 0 else 'Zapas do końca roku') + '</div></div>'
            '</div>'
            '<div class="g2" style="margin-bottom:12px">'
            '<div class="card stat"><div class="v">' + str(int(wystarczy_na)) + ' dni</div><div class="l">Zapas wystarczy na</div><div class="s">pasza gotowa + z magazynu</div></div>'
            '<div class="card stat"><div class="v">' + str(potrzeba_do_konca_roku) + ' kg</div><div class="l">Potrzeba do 31.12</div><div class="s">zużycie ' + str(round(avg_zuzycie,1)) + ' kg/dzień</div></div>'
            '</div>'
            '<div class="card"><b>Harmonogram miesięczny</b>'
            '<div style="overflow-x:auto"><table style="margin-top:8px">'
            '<thead><tr><th>Miesiąc</th><th>Dni</th><th>Potrzeba</th></tr></thead>'
            '<tbody>' + wiersze_pred + '</tbody></table></div>'
            '<p style="font-size:12px;color:#888;margin-top:8px">'
            'Prognoza na podstawie średniego zużycia z ostatnich 30 dni.</p></div>'
        )
        return R(html, "pasza")

    # ════════════════════════════════════════════════════════════════════════
    # 5. ADMIN — przypisywanie farm do userów
    # ════════════════════════════════════════════════════════════════════════

    @app.route("/api/skladniki-autocomplete")
    @farm_required
    def skladniki_autocomplete():
        g = gid()
        q = request.args.get("q","").lower()
        db = get_db()
        rows = db.execute(
            "SELECT nazwa, kategoria, cena_aktualna FROM stan_magazynu "
            "WHERE gospodarstwo_id=? AND LOWER(nazwa) LIKE ? LIMIT 10",
            (g, "%" + q + "%")
        ).fetchall()
        # Dodaj też z bazy składników
        from_baza = db.execute(
            "SELECT nazwa, kategoria, cena_pln_t/1000.0 as cena_aktualna "
            "FROM skladniki_baza WHERE LOWER(nazwa) LIKE ? AND aktywny=1 LIMIT 10",
            ("%" + q + "%",)
        ).fetchall()
        db.close()
        wyniki = []
        nazwy  = set()
        for r in list(rows) + list(from_baza):
            if r["nazwa"] not in nazwy:
                nazwy.add(r["nazwa"])
                wyniki.append({
                    "nazwa":     r["nazwa"],
                    "kategoria": r["kategoria"],
                    "cena":      round(r["cena_aktualna"] or 0, 2)
                })
        return jsonify(wyniki[:10])

    # ════════════════════════════════════════════════════════════════════════
    # 7. INIT TABEL dla nowych funkcji
    # ════════════════════════════════════════════════════════════════════════
    def _init_new_tables():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS dzienne_czynnosci (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gospodarstwo_id INTEGER NOT NULL REFERENCES gospodarstwa(id) ON DELETE CASCADE,
            data DATE NOT NULL,
            czynnosci TEXT DEFAULT '[]',
            notatka TEXT,
            UNIQUE(gospodarstwo_id, data)
        );
        CREATE TABLE IF NOT EXISTS prad_odczyty_fix (
            id INTEGER PRIMARY KEY,
            odczyt_licznika REAL DEFAULT 0
        );
        """)
        # Dodaj kolumnę odczyt_licznika jeśli nie istnieje
        try:
            db.execute("ALTER TABLE prad_odczyty ADD COLUMN odczyt_licznika REAL DEFAULT 0")
            db.commit()
        except Exception:
            pass  # już istnieje
        db.commit(); db.close()

    _init_new_tables()

    return app
