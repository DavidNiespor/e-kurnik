# -*- coding: utf-8 -*-
"""produkcja_views.py — widoki produkcji jaj i sprzedaży"""
from datetime import date
import json


def register_produkcja(app):
    from flask import request, redirect, flash, session, jsonify
    from db import get_db, get_setting
    from auth import farm_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    # ─── PRODUKCJA — tylko zbiory jaj ─────────────────────────────────────

    @app.route("/magazyn-jaj", methods=["GET","POST"])
    @app.route("/produkcja", methods=["GET","POST"])
    @app.route("/produkcja/dodaj", methods=["POST"])
    @farm_required
    def produkcja():
        g = gid(); db = get_db()

        # ── POST ─────────────────────────────────────────────────────────
        if request.method == "POST":
            action = request.form.get("action", "")

            if action == "strata":
                ile   = int(request.form.get("strata_ile", 0) or 0)
                powod = request.form.get("strata_powod", "inne")
                uwagi = request.form.get("strata_uwagi", "")
                data_s = request.form.get("strata_data", date.today().isoformat())
                if ile > 0:
                    db.execute(
                        "INSERT INTO jaja_straty(gospodarstwo_id,data,ilosc,powod,uwagi) VALUES(?,?,?,?,?)",
                        (g, data_s, ile, powod, uwagi))
                    db.commit()
                    flash(str(ile) + " jaj — strata: " + powod)
                db.close(); return redirect("/magazyn-jaj")

            if action == "za0":
                ile   = int(request.form.get("za0_ile", 0) or 0)
                powod = request.form.get("za0_powod", "gratis")
                uwagi = request.form.get("za0_uwagi", "")
                data_z = request.form.get("za0_data", date.today().isoformat())
                if ile > 0:
                    db.execute(
                        "INSERT INTO sprzedaz_szczegol(gospodarstwo_id,data,ilosc,cena_szt,wartosc,typ,uwagi)"
                        " VALUES(?,?,?,0,0,?,?)",
                        (g, data_z, ile, "za0", (powod + " " + uwagi).strip()))
                    ex0 = db.execute("SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, data_z)).fetchone()
                    if ex0:
                        db.execute(
                            "UPDATE produkcja SET jaja_sprzedane=(SELECT COALESCE(SUM(ilosc),0) FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND data=?) WHERE id=?",
                            (g, data_z, ex0["id"]))
                    db.commit()
                    flash(str(ile) + " jaj za darmo: " + powod)
                db.close(); return redirect("/magazyn-jaj")

            # Domyślnie: zapis zebranych jaj
            d     = request.form.get("data", date.today().isoformat())
            jaja  = int(request.form.get("jaja_zebrane", 0) or 0)
            uwagi = request.form.get("uwagi", "")
            ex = db.execute(
                "SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, d)).fetchone()
            if ex:
                db.execute(
                    "UPDATE produkcja SET jaja_zebrane=?,uwagi=? WHERE id=?",
                    (jaja, uwagi, ex["id"]))
            else:
                db.execute(
                    "INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,pasza_wydana_kg,uwagi)"
                    " VALUES(?,?,?,0,0,?)",
                    (g, d, jaja, uwagi))
            db.commit(); db.close()
            flash("Zapisano: " + str(jaja) + " szt. — " + d)
            return redirect("/magazyn-jaj")

        # ── GET ────────────────────────────────────────────────────────────
        kur = int(db.execute(
            "SELECT COALESCE(SUM(liczba),0) as s FROM stado"
            " WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",
            (g,)).fetchone()["s"]) or 1

        # Statystyki
        stat = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as sum_zeb,"
            " COALESCE(AVG(jaja_zebrane),0) as avg_zeb"
            " FROM produkcja WHERE gospodarstwo_id=?"
            " AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()

        # Stan magazynu
        from db import stan_magazynu as _sm
        stan_mag = _sm(db, g)
        rez = int(db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as s FROM zamowienia"
            " WHERE gospodarstwo_id=? AND status IN ('nowe','potwierdzone')",
            (g,)).fetchone()["s"])
        dostepne = max(0, stan_mag - rez)

        # Straty miesiąc
        straty_mies = int(db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as s FROM jaja_straty"
            " WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",
            (g,)).fetchone()["s"])
        za0_mies = int(db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as s FROM sprzedaz_szczegol"
            " WHERE gospodarstwo_id=? AND cena_szt=0"
            " AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",
            (g,)).fetchone()["s"])
        cena_def = float(gs("cena_jajka", "1.20"))
        pot_strata = round((straty_mies + za0_mies) * cena_def, 2)

        # Historia 60 dni
        rows = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 60",
            (g,)).fetchall()

        # Ostatnie straty
        straty_hist = db.execute(
            "SELECT * FROM jaja_straty WHERE gospodarstwo_id=?"
            " ORDER BY data DESC, id DESC LIMIT 15", (g,)).fetchall()

        # Dzisiejszy wpis
        dzis_row = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=?",
            (g, date.today().isoformat())).fetchone()

        # Ostatnie 7 wpisów (mini historia)
        ostatnie = db.execute(
            "SELECT data, jaja_zebrane FROM produkcja WHERE gospodarstwo_id=?"
            " ORDER BY data DESC LIMIT 7", (g,)).fetchall()

        db.close()

        # ── HTML ───────────────────────────────────────────────────────────
        dzis = date.today().isoformat()

        # 4 kafelki główne
        s_stats = (
            "<div class='g4' style='margin-bottom:12px'>"
            "<div class='card stat'>"
            "<div class='v' style='color:#3B6D11'>" + str(stan_mag) + "</div>"
            "<div class='l'>W magazynie</div>"
            "<div class='s'>dostepne: " + str(dostepne) + " szt.</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v'>" + str(int(stat["sum_zeb"])) + "</div>"
            "<div class='l'>Zebrano w mies.</div>"
            "<div class='s'>sr. " + str(round(stat["avg_zeb"],1)) + " / dzien</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v' style='color:#A32D2D'>" + str(straty_mies) + "</div>"
            "<div class='l'>Straty mies.</div>"
            "<div class='s'>" + str(straty_mies + za0_mies) + " szt. razem z gratis</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v' style='color:#A32D2D'>" + str(pot_strata) + " zl</div>"
            "<div class='l'>Pot. strata mies.</div>"
            "<div class='s'>straty + gratis x cena</div>"
            "</div>"
            "</div>"
        )

        # Formularz wpisu dziennego
        mini_hist = "".join(
            "<div style='background:#f5f5f0;border-radius:6px;padding:3px 8px;"
            "font-size:11px;white-space:nowrap'>"
            "<span style='color:#888'>" + r["data"][5:] + "</span> "
            "<b>" + str(r["jaja_zebrane"]) + "</b></div>"
            for r in ostatnie)

        s_wpis = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
            "<b>Zebrane jaja</b>"
            + ("<span style='font-size:12px;color:#3B6D11;font-weight:600'>Dzis: "
               + str(dzis_row["jaja_zebrane"]) + " szt.</span>" if dzis_row else
               "<span style='font-size:12px;color:#aaa'>Brak wpisu na dzis</span>")
            + "</div>"
            "<div style='display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px'>"
            + mini_hist +
            "</div>"
            "<form method='POST'>"
            "<div style='display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap'>"
            "<div style='flex:1;min-width:80px'><label style='font-size:11px'>Szt. zebranych</label>"
            "<input name='jaja_zebrane' type='number' min='0'"
            " value='" + (str(dzis_row["jaja_zebrane"]) if dzis_row else "") + "'"
            " placeholder='0' style='font-size:20px;text-align:center' required></div>"
            "<div><label style='font-size:11px'>Data</label>"
            "<input name='data' type='date' value='" + dzis + "' style='font-size:13px'></div>"
            "<div style='flex:2;min-width:120px'><label style='font-size:11px'>Uwagi</label>"
            "<input name='uwagi' value='" + (dzis_row["uwagi"] or "" if dzis_row else "") + "'"
            " placeholder='opcjonalnie' style='font-size:13px'></div>"
            "<button class='btn bg bsm' style='padding:10px 16px'>Zapisz</button>"
            "</div>"
            "</form></div>"
        )

        # Formularz strat
        s_strata = (
            "<div class='card' style='margin-bottom:12px'>"
            "<b>Dodaj strate / za darmo</b>"
            "<div style='display:flex;gap:12px;margin-top:10px;flex-wrap:wrap'>"

            "<form method='POST' action='/produkcja'"
            " style='display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;flex:1'>"
            "<input type='hidden' name='action' value='strata'>"
            "<div><label style='font-size:11px'>Stluczki/zepsute (szt.)</label>"
            "<input name='strata_ile' type='number' min='1'"
            " style='width:80px;font-size:16px;text-align:center' placeholder='0'></div>"
            "<div><label style='font-size:11px'>Powod</label>"
            "<select name='strata_powod' style='font-size:13px'>"
            "<option value='stluczone'>Stluczki</option>"
            "<option value='zepsute'>Zepsute</option>"
            "<option value='zgubione'>Inne</option>"
            "</select></div>"
            "<input name='strata_data' type='date' value='" + dzis + "' style='font-size:13px'>"
            "<button class='btn br bsm'>Zapisz strate</button>"
            "</form>"

            "<form method='POST' action='/produkcja'"
            " style='display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end;flex:1'>"
            "<input type='hidden' name='action' value='za0'>"
            "<div><label style='font-size:11px'>Oddane za darmo (szt.)</label>"
            "<input name='za0_ile' type='number' min='1'"
            " style='width:80px;font-size:16px;text-align:center' placeholder='0'></div>"
            "<div><label style='font-size:11px'>Opis</label>"
            "<input name='za0_uwagi' placeholder='Sasiad, probka...' style='font-size:13px'></div>"
            "<input name='za0_data' type='date' value='" + dzis + "' style='font-size:13px'>"
            "<button class='btn bo bsm'>Za darmo</button>"
            "</form>"

            "</div></div>"
        )

        # Historia strat
        POWOD = {"stluczone": "Stluczki", "zepsute": "Zepsute", "zgubione": "Inne", "inne": "Inne"}
        sh_rows = ""
        for r in straty_hist:
            sh_rows += (
                "<tr>"
                "<td style='font-size:12px'>" + r["data"] + "</td>"
                "<td style='color:#A32D2D;font-weight:700;text-align:center'>-" + str(r["ilosc"]) + "</td>"
                "<td>" + POWOD.get(r["powod"], r["powod"]) + "</td>"
                "<td style='font-size:11px;color:#888'>" + (r["uwagi"] or "") + "</td>"
                "<td style='color:#A32D2D;font-size:12px'>" + str(round(r["ilosc"]*cena_def,2)) + " zl</td>"
                "<td><a href='/jaja_strata/" + str(r["id"]) + "/usun' class='btn br bsm'"
                " onclick='return confirm(\"Usunac?\")'>x</a></td>"
                "</tr>"
            )

        s_straty_hist = (
            "<div class='card' style='margin-bottom:12px'>"
            "<b>Historia strat</b>"
            "<div style='overflow-x:auto'>"
            "<table style='font-size:13px;margin-top:8px'><thead><tr>"
            "<th>Data</th><th>Szt.</th><th>Powod</th><th>Uwagi</th><th>Pot.strata</th><th></th>"
            "</tr></thead>"
            "<tbody>"
            + (sh_rows or "<tr><td colspan=6 style='color:#888;text-align:center;padding:12px'>Brak strat</td></tr>")
            + "</tbody></table></div></div>"
        ) if straty_hist else ""

        # Historia zebranych
        rows_html = ""
        for r in rows:
            niesn = round(r["jaja_zebrane"] / kur * 100, 1) if kur else 0
            kol = "#3B6D11" if niesn >= 80 else "#BA7517" if niesn >= 60 else "#A32D2D"
            _rid = "r" + r["data"].replace("-","")
            _uwagi_esc = (r["uwagi"] or "").replace("'","&#39;")
            rows_html += (
                "<tr>"
                "<td style='white-space:nowrap;font-size:13px'>" + r["data"] + "</td>"
                "<td style='font-weight:700;font-size:16px;text-align:center'>" + str(r["jaja_zebrane"]) + "</td>"
                "<td style='color:" + kol + ";font-weight:600;text-align:center'>" + str(niesn) + "%</td>"
                "<td style='color:#888;font-size:12px'>" + (r["uwagi"] or "") + "</td>"
                "<td><button class='btn bo bsm' style='font-size:11px'"
                " onclick='var e=document.getElementById(\"" + _rid + "\");"
                "e.style.display=e.style.display===\"none\"?\"table-row\":\"none\"'>Edytuj</button></td>"
                "</tr>"
                "<tr id='" + _rid + "' style='display:none;background:#f8f8f4'>"
                "<td colspan=5 style='padding:8px 12px'>"
                "<form method='POST'"
                " style='display:flex;gap:8px;align-items:flex-end;flex-wrap:wrap'>"
                "<input type='hidden' name='data' value='" + r["data"] + "'>"
                "<div><label style='font-size:11px'>Zebrane (szt.)</label>"
                "<input name='jaja_zebrane' type='number' min='0'"
                " value='" + str(r["jaja_zebrane"]) + "'"
                " style='width:90px;font-size:16px;text-align:center'></div>"
                "<div style='flex:2;min-width:120px'><label style='font-size:11px'>Uwagi</label>"
                "<input name='uwagi' value='" + _uwagi_esc + "' style='font-size:13px'></div>"
                "<button class='btn bp bsm'>Zapisz</button>"
                "<button type='button' class='btn bo bsm'"
                " onclick='document.getElementById(\"" + _rid + "\").style.display=\"none\"'>Anuluj</button>"
                "</form></td></tr>"
            )

        s_historia = (
            "<div class='card'><b>Historia zebran — 60 dni</b>"
            "<div style='overflow-x:auto'>"
            "<table style='font-size:13px;margin-top:8px'><thead><tr>"
            "<th>Data</th><th style='text-align:center'>Zebrane</th>"
            "<th style='text-align:center'>Niesnosc</th><th>Uwagi</th><th></th>"
            "</tr></thead>"
            "<tbody>"
            + (rows_html or "<tr><td colspan=5 style='color:#888;text-align:center;padding:20px'>Brak wpisow</td></tr>")
            + "</tbody></table></div></div>"
        )

        html = (
            "<h1>Magazyn jaj</h1>"
            + s_stats
            + s_wpis
            + s_strata
            + s_straty_hist
            + s_historia
        )
        return R(html, "prod")


    @app.route("/produkcja/edytuj/<data>", methods=["GET", "POST"])
    @farm_required
    def produkcja_edytuj(data):
        """Edycja / korekta zbioru — tylko ile zebrano, uwagi."""
        g = gid(); db = get_db()
        r = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, data)).fetchone()
        if not r:
            db.close(); flash("Nie znaleziono wpisu."); return redirect("/magazyn-jaj")

        if request.method == "POST":
            jaja  = int(request.form.get("jaja_zebrane", 0) or 0)
            uwagi = request.form.get("uwagi", "")
            pasza = float(request.form.get("pasza_wydana_kg", r["pasza_wydana_kg"] or 0) or 0)
            db.execute(
                "UPDATE produkcja SET jaja_zebrane=?,uwagi=?,pasza_wydana_kg=? "
                "WHERE gospodarstwo_id=? AND data=?", (jaja, uwagi, pasza, g, data))
            db.commit(); db.close()
            flash(f"Wpis {data} zaktualizowany.")
            return redirect("/magazyn-jaj")
        db.close()

        html = (
            f"<h1>Korekta zbioru — {data}</h1>"
            "<div class='card'><form method='POST'>"
            "<div class='al alw'>Edytujesz <b>tylko zbiór</b> z tego dnia. "
            "Sprzedaż edytuj w <a href='/sprzedaz'>Historii sprzedaży</a>.</div>"
            "<label style='margin-top:12px'>Zebrane jaja (szt)</label>"
            f"<input name='jaja_zebrane' type='number' min='0' value='{r['jaja_zebrane']}' "
            "style='font-size:28px;text-align:center'>"
            # Pasza jako hidden - zachowaj bez zmian przy edycji zbioru
            f"<input type='hidden' name='pasza_wydana_kg' value='{r['pasza_wydana_kg'] or 0}'>"
            "<label>Uwagi (np. stłukło się X jaj, choroba)</label>"
            f"<input name='uwagi' value='{r['uwagi'] or ''}' placeholder='opcjonalnie'>"
            "<br><button class='btn bp' style='margin-top:12px;width:100%;padding:12px'>Zapisz korektę</button>"
            "<a href='/produkcja' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "prod")

    # ─── SPRZEDAŻ — historia transakcji ────────────────────────────────────

    # sprzedaz przeniesiona do sprzedaz_views.py

    @app.route("/klienci")
    @farm_required
    def klienci():
        g = gid(); db = get_db()
        rows = db.execute("""
            SELECT k.*,
                   COALESCE(ks.saldo_pln, 0) as saldo,
                   COUNT(DISTINCT p.data) as transakcji,
                   COALESCE((SELECT SUM(wartosc) FROM sprzedaz_szczegol ss WHERE ss.klient_id=k.id AND ss.gospodarstwo_id=?),0) as total_kwota,
                   MAX(p.data) as ostatnia_transakcja
            FROM klienci k
            LEFT JOIN konta_saldo ks ON ks.klient_id=k.id
            LEFT JOIN produkcja p ON p.klient_id=k.id AND p.gospodarstwo_id=?
            WHERE k.gospodarstwo_id=?
            GROUP BY k.id ORDER BY k.nazwa""", (g, g, g)).fetchall()
        db.close()

        rows_html = ""
        for r in rows:
            saldo = float(r["saldo"] or 0)
            if saldo > 0.01:
                saldo_html = f"<span class='badge b-red'>Dług: {round(saldo,2)} zł</span>"
            elif saldo < -0.01:
                saldo_html = f"<span class='badge b-green'>Nadpłata: {round(-saldo,2)} zł</span>"
            else:
                saldo_html = "<span class='badge b-gray'>Rozliczony</span>"

            rows_html += (
                f"<tr>"
                f"<td><a href='/klienci/{r['id']}' style='color:#534AB7;font-weight:500'>{r['nazwa']}</a></td>"
                f"<td style='font-size:12px;color:#888'>{r['telefon'] or '—'}</td>"
                f"<td>{saldo_html}</td>"
                f"<td style='text-align:right;font-size:13px'>{r['transakcji']} transakcji</td>"
                f"<td style='text-align:right;font-size:13px'>{round(r['total_kwota'],2)} zł łącznie</td>"
                f"<td style='font-size:12px;color:#888'>{r['ostatnia_transakcja'] or '—'}</td>"
                f"<td class='nowrap'>"
                f"<a href='/klienci/{r['id']}' class='btn bo bsm'>Podgląd</a> "
                f"<a href='/klienci/{r['id']}/edytuj' class='btn bo bsm'>Edytuj</a>"
                f"</td></tr>"
            )

        # Suma długów i nadpłat
        db2 = get_db()
        salda = db2.execute("""
            SELECT COALESCE(SUM(CASE WHEN ks.saldo_pln>0 THEN ks.saldo_pln ELSE 0 END),0) as dlug,
                   COALESCE(SUM(CASE WHEN ks.saldo_pln<0 THEN -ks.saldo_pln ELSE 0 END),0) as nadplata
            FROM konta_saldo ks JOIN klienci k ON ks.klient_id=k.id
            WHERE k.gospodarstwo_id=?""", (g,)).fetchone()
        db2.close()

        html = (
            "<h1>Klienci</h1>"
            "<div style='display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap'>"
            "<a href='/klienci/dodaj' class='btn bp bsm'>+ Dodaj klienta</a>"
            "<a href='/sprzedaz' class='btn bo bsm'>Historia sprzedaży</a>"
            "</div>"
            + (f"<div class='g2' style='margin-bottom:12px'>"
               f"<div class='card' style='border-left:4px solid #A32D2D'>"
               f"<div style='font-size:22px;font-weight:700;color:#A32D2D'>{round(salda['dlug'],2)} zł</div>"
               f"<div style='font-size:12px;color:#888;margin-top:4px'>Do odebrania od klientów (długi)</div></div>"
               f"<div class='card' style='border-left:4px solid #3B6D11'>"
               f"<div style='font-size:22px;font-weight:700;color:#3B6D11'>{round(salda['nadplata'],2)} zł</div>"
               f"<div style='font-size:12px;color:#888;margin-top:4px'>Nadpłaty do zwrotu / zaliczki</div></div>"
               f"</div>")
            + "<div class='card' style='overflow-x:auto'>"
            "<table><thead><tr>"
            "<th>Klient</th><th>Telefon</th><th>Saldo</th>"
            "<th style='text-align:right'>Transakcje</th><th style='text-align:right'>Łącznie</th>"
            "<th>Ostatnia transakcja</th><th></th>"
            "</tr></thead>"
            f"<tbody>{rows_html or '<tr><td colspan=7 style=\"color:#888;text-align:center;padding:20px\">Brak klientów</td></tr>'}</tbody>"
            "</table></div>"
        )
        return R(html, "zam")

    @app.route("/klienci/<int:kid>")
    @farm_required
    def klient_podglad(kid):
        g = gid(); db = get_db()
        k = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid, g)).fetchone()
        if not k: db.close(); return redirect("/klienci")

        # Saldo
        ks = db.execute("SELECT * FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
        saldo = float(ks["saldo_pln"] if ks else 0)

        # Historia sprzedaży temu klientowi
        sprzedaz = db.execute("""
            SELECT p.data, p.jaja_sprzedane, p.cena_sprzedazy, p.typ_sprzedazy, p.uwagi,
                   ROUND(p.jaja_sprzedane * COALESCE(p.cena_sprzedazy,0),2) as kwota
            FROM produkcja p
            WHERE p.klient_id=? AND p.gospodarstwo_id=? AND p.jaja_sprzedane>0
            ORDER BY p.data DESC LIMIT 60""", (kid, g)).fetchall()

        # Transakcje saldo (wpłaty, korekty)
        transakcje = db.execute("""
            SELECT * FROM konta_transakcje
            WHERE klient_id=? AND gospodarstwo_id=?
            ORDER BY data DESC LIMIT 30""", (kid, g)).fetchall()

        # Aktywne zamówienia
        zamow = db.execute("""
            SELECT * FROM zamowienia WHERE klient_id=? AND gospodarstwo_id=?
            AND status NOT IN ('dostarczone','anulowane')
            ORDER BY data_dostawy""", (kid, g)).fetchall()

        db.close()

        # Statystyki
        total_sprzedane = sum(r["jaja_sprzedane"] or 0 for r in sprzedaz)
        total_kwota = sum(r["kwota"] or 0 for r in sprzedaz)

        # Saldo karta
        # Ile ma zapłacić przy następnej dostawie
        cena_kl = float(k["cena_indyw"] if "cena_indyw" in k.keys() and k["cena_indyw"] else 0)
        cena_def_k = float(gs("cena_jajka","1.20"))
        cena_akt = cena_kl if cena_kl > 0 else cena_def_k
        zam_sum = sum(float(z["ilosc"]) * cena_akt for z in zamow)
        do_zaplaty = round(saldo + zam_sum, 2)  # dług + aktywne zamówienia

        if saldo > 0.01:
            saldo_kol = "#A32D2D"
            saldo_txt = "Do zapłaty: " + str(round(saldo,2)) + " zł"
            saldo_sub = "Klient ma dług — oczekuje na płatność"
        elif saldo < -0.01:
            saldo_kol = "#3B6D11"
            saldo_txt = "Nadpłata: " + str(round(-saldo,2)) + " zł"
            saldo_sub = "Klient nadpłacił — do zwrotu lub zaliczka"
        else:
            saldo_kol = "#534AB7"
            saldo_txt = "Rozliczony"
            saldo_sub = "Brak zadłużenia"

        TYP = {"gotowka": "💵 Gotówka", "przelew": "🏦 Przelew",
               "z_salda": "📋 Z salda", "nastepnym_razem": "⏳ Następnym razem"}

        sp_rows = "".join(
            f"<tr>"
            f"<td style='font-size:13px'>{r['data']}</td>"
            f"<td style='font-weight:600;text-align:center'>{r['jaja_sprzedane']}</td>"
            f"<td style='text-align:right'>{r['cena_sprzedazy'] or '—'} zł</td>"
            f"<td style='font-weight:600;color:#3B6D11;text-align:right'>{r['kwota']} zł</td>"
            f"<td style='font-size:12px;color:#888'>{TYP.get(r['typ_sprzedazy'] or '','—')}</td>"
            f"<td style='font-size:11px;color:#888'>{r['uwagi'] or ''}</td>"
            f"</tr>"
            for r in sprzedaz
        )

        def _tr_row(t):
            kol = "#3B6D11" if t["kwota"] >= 0 else "#A32D2D"
            sign = "+" if t["kwota"] >= 0 else ""
            return (
                "<tr>"
                "<td style='font-size:12px;color:#888'>" + t["data"][:16] + "</td>"
                "<td>" + (t["typ"] or "") + "</td>"
                "<td style='font-weight:600;color:" + kol + "'>" + sign + str(round(t["kwota"],2)) + " zl</td>"
                "<td style='font-size:12px;color:#888'>" + (t["opis"] or "") + "</td>"
                "<td style='font-size:11px;color:#aaa'>saldo: " + str(round(t["saldo_po"],2)) + " zl</td>"
                "</tr>"
            )
        tr_rows = "".join(_tr_row(t) for t in transakcje) if transakcje else "<tr><td colspan=5 style='color:#aaa;text-align:center;padding:10px'>Brak transakcji saldo</td></tr>"

        zam_rows = "".join(
            f"<tr>"
            f"<td style='font-size:13px'>{z['data_dostawy']}</td>"
            f"<td style='font-weight:600'>{z['ilosc']} szt</td>"
            f"<td>{z['cena_za_szt'] or '—'} zł/szt</td>"
            f"<td><span class='badge b-amber'>{z['status']}</span></td>"
            f"</tr>"
            for z in zamow
        ) if zamow else "<tr><td colspan=4 style='color:#aaa;text-align:center;padding:10px'>Brak aktywnych zamówień</td></tr>"

        html = (
            f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap'>"
            f"<h1 style='margin-bottom:0'>{k['nazwa']}</h1>"
            f"<div style='margin-left:auto;display:flex;gap:6px'>"
            f"<a href='/klienci/{kid}/edytuj' class='btn bo bsm'>Edytuj</a>"
            f"<a href='/klienci' class='btn bo bsm'>← Lista</a>"
            f"</div></div>"

            # Info + saldo
            f"<div class='g2'>"
            f"<div class='card'>"
            f"<div style='font-size:13px'>"
            + (f"<div style='padding:3px 0'><span style='color:#888'>Telefon:</span> <b>{k['telefon']}</b></div>" if k["telefon"] else "")
            + (f"<div style='padding:3px 0'><span style='color:#888'>Email:</span> <b>{k['email']}</b></div>" if k["email"] else "")
            + (f"<div style='padding:3px 0'><span style='color:#888'>Adres:</span> {k['adres']}</div>" if k["adres"] else "")
            + f"<div style='margin-top:10px;padding-top:10px;border-top:1px solid #f0ede4'>"
            f"<div style='font-size:12px;color:#888'>Łącznie sprzedano:</div>"
            f"<div style='font-size:18px;font-weight:600'>{total_sprzedane} szt = {round(total_kwota,2)} zł</div>"
            f"</div></div></div>"

            f"<div class='card' style='border-left:4px solid {saldo_kol}'>"
            f"<div style='font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.5px'>Saldo konta</div>"
            f"<div style='font-size:28px;font-weight:700;color:{saldo_kol};margin-top:4px'>{saldo_txt}</div>"
            f"<div style='font-size:12px;color:#888;margin-top:4px'>{saldo_sub}</div>"
            + (f"<div style='margin-top:8px;font-size:12px;background:#f5f5f0;border-radius:6px;padding:6px 10px'>"
               f"💰 Cena indyw.: <b>{cena_akt} zł/szt</b>"
               + (' <span style="color:#888">(domyślna)</span>' if cena_kl == 0 else ' <span style="color:#534AB7">(indyw.)</span>')
               + f"</div>")
            + (f"<div style='margin-top:8px;background:#fff3cd;border-radius:6px;padding:8px 12px;font-size:13px'>"
               f"🧾 Przy następnej wizycie do zapłaty: <b style='font-size:16px'>{do_zaplaty} zł</b>"
               f"<div style='font-size:11px;color:#888;margin-top:2px'>dług {round(saldo,2)} zł + zamówienia {round(zam_sum,2)} zł</div>"
               f"</div>" if do_zaplaty > 0.01 else "")
            + f"<div style='margin-top:12px;display:flex;gap:8px;flex-wrap:wrap'>"
            f"<a href='/klienci/{kid}/wplata' class='btn bg bsm'>+ Wpłata</a>"
            f"<a href='/klienci/{kid}/korekta-saldo' class='btn bo bsm'>Korekta salda</a>"
            f"</div></div>"
            f"</div>"  # end g2

            # Historia sprzedaży
            f"<div class='card'><b>Historia sprzedaży</b>"
            "<div style='overflow-x:auto'><table style='margin-top:8px;font-size:13px'><thead><tr>"
            "<th>Data</th><th style='text-align:center'>Szt</th><th style='text-align:right'>Cena</th>"
            "<th style='text-align:right'>Kwota</th><th>Płatność</th><th>Uwagi</th>"
            "</tr></thead>"
            f"<tbody>{sp_rows or '<tr><td colspan=6 style=\"color:#888;text-align:center;padding:16px\">Brak transakcji</td></tr>'}</tbody>"
            "</table></div></div>"

            # Transakcje saldo
            f"<div class='card'><b>Transakcje saldo (wpłaty, korekty)</b>"
            "<div style='overflow-x:auto'><table style='margin-top:8px;font-size:13px'><thead><tr>"
            "<th>Data</th><th>Typ</th><th>Kwota</th><th>Opis</th><th>Saldo po</th>"
            "</tr></thead>"
            f"<tbody>{tr_rows}</tbody>"
            "</table></div></div>"

            # Zamówienia
            f"<div class='card'><b>Aktywne zamówienia</b>"
            "<div style='overflow-x:auto'><table style='margin-top:8px;font-size:13px'><thead><tr>"
            "<th>Dostawa</th><th>Ilość</th><th>Cena</th><th>Status</th>"
            "</tr></thead>"
            f"<tbody>{zam_rows}</tbody>"
            "</table></div></div>"
        )
        return R(html, "zam")

    @app.route("/klienci/<int:kid>/wplata", methods=["GET", "POST"])
    @farm_required
    def klient_wplata(kid):
        g = gid(); db = get_db()
        k = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid, g)).fetchone()
        if not k: db.close(); return redirect("/klienci")
        ks = db.execute("SELECT saldo_pln FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
        saldo = float(ks["saldo_pln"] if ks else 0)

        if request.method == "POST":
            kwota = float(request.form.get("kwota", 0) or 0)
            opis  = request.form.get("opis", "Wpłata").strip() or "Wpłata"
            rozlicz0 = request.form.get("rozlicz_do_zera") == "1"
            if kwota <= 0 and not rozlicz0:
                flash("Kwota musi być > 0"); db.close(); return redirect(f"/klienci/{kid}/wplata")
            from datetime import datetime
            if rozlicz0:
                # Zeruj saldo - wplata = aktualne saldo
                if kwota <= 0: kwota = max(0, saldo)
                nowe_saldo = 0.0
                opis = opis + " (rozliczono do zera)"
            else:
                nowe_saldo = round(saldo - kwota, 2)
            if ks:
                db.execute("UPDATE konta_saldo SET saldo_pln=?,ostatnia_zmiana=? WHERE klient_id=?",
                           (nowe_saldo, datetime.now().isoformat(), kid))
            else:
                db.execute("INSERT INTO konta_saldo(klient_id,saldo_pln,ostatnia_zmiana) VALUES(?,?,?)",
                           (kid, nowe_saldo, datetime.now().isoformat()))
            db.execute(
                "INSERT INTO konta_transakcje(gospodarstwo_id,klient_id,data,typ,kwota,opis,saldo_po) "
                "VALUES(?,?,?,?,?,?,?)",
                (g, kid, datetime.now().isoformat(), "wplata", -kwota, opis, nowe_saldo))
            db.commit(); db.close()
            flash_msg = f"Wpłata {kwota} zł. Nowe saldo: {nowe_saldo} zł"
            if rozlicz0: flash_msg = f"Rozliczono do zera. Saldo: 0.00 zł ✓"
            flash(flash_msg)
            # Wróć na sprzedaz jeśli przyszło stamtąd
            ref = request.referrer or ""
            return redirect("/sprzedaz" if "/sprzedaz" in ref else f"/klienci/{kid}")

        # Ostatnie transakcje klienta
        ostatnie = db.execute(
            "SELECT * FROM konta_transakcje WHERE klient_id=? ORDER BY data DESC LIMIT 5", (kid,)).fetchall()
        db.close()
        saldo_kol = "#A32D2D" if saldo > 0.01 else "#3B6D11" if saldo < -0.01 else "#888"
        saldo_txt = ("Dług: " + str(round(saldo,2)) + " zł — klient powinien zapłacić" if saldo > 0.01
                     else "Nadpłata: " + str(round(-saldo,2)) + " zł — masz mu oddać" if saldo < -0.01
                     else "Rozliczony")
        # Sugestia kwoty = aktualny dług
        sug = str(round(saldo, 2)) if saldo > 0 else ""
        trans_html = "".join(
            "<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px;"
            "border-bottom:1px solid #f0ede4'>"
            "<span style='color:#888'>" + t["data"][:16] + "</span>"
            "<span>" + (t["opis"] or t["typ"]) + "</span>"
            "<span style='font-weight:600;color:" + ("#3B6D11" if float(t["kwota"] or 0) < 0 else "#A32D2D") + "'>"
            + ("+" if float(t["kwota"] or 0) < 0 else "") + str(round(float(t["kwota"] or 0),2)) + " zł</span>"
            "<span style='color:#888'> → " + str(round(float(t["saldo_po"] or 0),2)) + " zł</span>"
            "</div>" for t in ostatnie)
        html = (
            "<h1>Wpłata od: " + k["nazwa"] + "</h1>"
            "<div class='card' style='margin-bottom:12px'><form method='POST'>"
            "<div class='al " + ("ald" if saldo > 0.01 else "alok") + "' style='font-size:15px'>"
            "<b>" + saldo_txt + "</b></div>"
            "<label style='margin-top:14px'>Kwota wpłaty (zł)</label>"
            "<input name='kwota' type='number' step='0.01' min='0.01' required"
            " style='font-size:28px;text-align:center' value='" + sug + "' placeholder='0.00'>"
            "<div id='podsum' style='background:#f5f5f0;border-radius:8px;padding:8px 12px;"
            "font-size:13px;margin:8px 0'>"
            "Po wpłacie: <b id='nowe-saldo'>oblicz...</b></div>"
            "<label>Opis</label>"
            "<input name='opis' value='Wpłata gotówkowa' placeholder='np. Gotówka, Przelew BLIK'>"
            "<button class='btn bg' style='margin-top:12px;width:100%;padding:14px;font-size:16px'>"
            "Zarejestruj wpłatę</button>"
            "<a href='/klienci/" + str(kid) + "' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
            "</form>"
            "<script>"
            "var sal=" + str(saldo) + ";"
            "var inp=document.querySelector('[name=kwota]');"
            "function upd(){"
            "  var k=parseFloat(inp.value)||0;"
            "  var ns=Math.round((sal-k)*100)/100;"
            "  var txt=ns>0.01?'Dług: '+ns+' zł':ns<-0.01?'Nadpłata: '+(-ns)+' zł':'Rozliczony ✓';"
            "  document.getElementById('nowe-saldo').textContent=txt;"
            "  document.getElementById('nowe-saldo').style.color=ns>0.01?'#A32D2D':'#3B6D11';"
            "}"
            "inp.addEventListener('input',upd);upd();"
            "</script></div>"
            + ("<div class='card'><b>Ostatnie transakcje</b><div style='margin-top:8px'>"
               + trans_html + "</div></div>" if ostatnie else "")
        )
        return R(html, "zam")

    @app.route("/klienci/<int:kid>/korekta-saldo", methods=["GET", "POST"])
    @farm_required
    def klient_korekta_saldo(kid):
        g = gid(); db = get_db()
        k = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid, g)).fetchone()
        if not k: db.close(); return redirect("/klienci")
        ks = db.execute("SELECT saldo_pln FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
        saldo = float(ks["saldo_pln"] if ks else 0)

        if request.method == "POST":
            nowe = float(request.form.get("nowe_saldo", 0) or 0)
            opis = request.form.get("opis", "Korekta ręczna").strip()
            from datetime import datetime
            if ks:
                db.execute("UPDATE konta_saldo SET saldo_pln=?,ostatnia_zmiana=? WHERE klient_id=?",
                           (nowe, datetime.now().isoformat(), kid))
            else:
                db.execute("INSERT INTO konta_saldo(klient_id,saldo_pln,ostatnia_zmiana) VALUES(?,?,?)",
                           (kid, nowe, datetime.now().isoformat()))
            db.execute(
                "INSERT INTO konta_transakcje(gospodarstwo_id,klient_id,data,typ,kwota,opis,saldo_po) "
                "VALUES(?,?,?,?,?,?,?)",
                (g, kid, datetime.now().isoformat(), "korekta", nowe - saldo, opis, nowe))
            db.commit(); db.close()
            flash(f"Saldo skorygowane: {round(saldo,2)} → {nowe} zł")
            return redirect(f"/klienci/{kid}")

        db.close()
        html = (
            f"<h1>Korekta salda: {k['nazwa']}</h1>"
            "<div class='card'><form method='POST'>"
            "<div class='al alw'>Korekta ręczna — używaj tylko do poprawienia błędów. "
            "Do rejestracji wpłat użyj przycisku <b>+ Wpłata</b>.</div>"
            f"<label style='margin-top:12px'>Aktualne saldo w systemie</label>"
            f"<div style='font-size:20px;font-weight:600;padding:8px;background:#f5f5f0;border-radius:8px'>{round(saldo,2)} zł</div>"
            "<label style='margin-top:10px'>Nowe saldo (zł) — wpisz 0 jeśli rozliczony</label>"
            f"<input name='nowe_saldo' type='number' step='0.01' value='{round(saldo,2)}' style='font-size:20px;text-align:center'>"
            "<label>Powód korekty</label>"
            "<input name='opis' value='Korekta ręczna' placeholder='opisz powód'>"
            "<br><button class='btn bp' style='margin-top:12px;width:100%;padding:12px'>Zapisz korektę</button>"
            f"<a href='/klienci/{kid}' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "zam")

    @app.route("/klienci/dodaj", methods=["GET", "POST"])
    @farm_required
    def klienci_dodaj():
        g = gid()
        if request.method == "POST":
            db = get_db()
            kid = db.execute(
                "INSERT INTO klienci(gospodarstwo_id,nazwa,telefon,email,adres,uwagi) VALUES(?,?,?,?,?,?)",
                (g, request.form["nazwa"], request.form.get("telefon", ""),
                 request.form.get("email", ""), request.form.get("adres", ""),
                 request.form.get("uwagi", ""))).lastrowid
            db.commit(); db.close()
            flash("Klient dodany.")
            return redirect(f"/klienci/{kid}")
        html = (
            "<h1>Nowy klient</h1><div class='card'><form method='POST'>"
            "<label>Nazwa</label><input name='nazwa' required placeholder='Imię i nazwisko lub firma'>"
            "<div class='g2'>"
            "<div><label>Telefon</label><input name='telefon' type='tel'></div>"
            "<div><label>Email</label><input name='email' type='email'></div>"
            "</div>"
            "<label>Adres</label><textarea name='adres' rows='2'></textarea>"
            "<label>Uwagi</label><input name='uwagi' placeholder='np. odbiór w piątek'>"
            "<br><button class='btn bp' style='margin-top:12px'>Zapisz</button>"
            "<a href='/klienci' class='btn bo' style='margin-left:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "zam")

    @app.route("/klienci/<int:kid>/edytuj", methods=["GET", "POST"])
    @farm_required
    def klienci_edytuj(kid):
        g = gid(); db = get_db()
        if request.method == "POST":
            cena_i = float(request.form.get("cena_indyw", 0) or 0)
            stal_z = 1 if request.form.get("stale_zamowienie") else 0
            try:
                db.execute(
                    "UPDATE klienci SET nazwa=?,telefon=?,email=?,adres=?,uwagi=?,cena_indyw=?,stale_zamowienie=? WHERE id=? AND gospodarstwo_id=?",
                    (request.form["nazwa"], request.form.get("telefon",""), request.form.get("email",""),
                     request.form.get("adres",""), request.form.get("uwagi",""), cena_i, stal_z, kid, g))
            except Exception:
                db.execute(
                    "UPDATE klienci SET nazwa=?,telefon=?,email=?,adres=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                    (request.form["nazwa"], request.form.get("telefon",""), request.form.get("email",""),
                     request.form.get("adres",""), request.form.get("uwagi",""), kid, g))
            db.commit(); db.close()
            flash("Klient zaktualizowany.")
            return redirect(f"/klienci/{kid}")
        r = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid, g)).fetchone()
        cena_def = gs("cena_jajka","1.20")
        db.close()
        if not r: return redirect("/klienci")
        cena_i = float(r["cena_indyw"] if "cena_indyw" in r.keys() else 0) or 0
        stal_z = int(r["stale_zamowienie"] if "stale_zamowienie" in r.keys() else 0) or 0
        html = (
            "<h1>Edytuj: " + r["nazwa"] + "</h1>"
            "<div class='card'><form method='POST'>"
            "<label>Nazwa</label>"
            "<input name='nazwa' required value='" + r["nazwa"] + "'>"
            "<div class='g2'>"
            "<div><label>Telefon</label><input name='telefon' value='" + (r["telefon"] or "") + "'></div>"
            "<div><label>Email</label><input name='email' value='" + (r["email"] or "") + "'></div>"
            "</div>"
            "<label>Adres</label><textarea name='adres' rows='2'>" + (r["adres"] or "") + "</textarea>"
            "<div class='g2' style='margin-top:8px'>"
            "<div>"
            "<label>💰 Indywidualna cena jajka (zł/szt.)</label>"
            "<input name='cena_indyw' type='number' step='0.01' min='0' value='" + str(cena_i or "") + "' placeholder='domyslna: " + str(cena_def) + " zl'>"
            "<p style='font-size:11px;color:#888;margin-top:3px'>0 = używa ceny domyślnej z ustawień</p>"
            "</div>"
            "<div>"
            "<label>Stałe zamówienie (tygodniowe)</label>"
            "<label style='display:flex;align-items:center;gap:8px;margin-top:10px;cursor:pointer'>"
            "<input type='checkbox' name='stale_zamowienie'" + (" checked" if stal_z else "") + "> Klient ma stałe zamówienie"
            "</label>"
            "<p style='font-size:11px;color:#888;margin-top:3px'>Wyswietla sie przy sprzedazy</p>"
            "</div>"
            "</div>"
            "<label>Uwagi</label><input name='uwagi' value='" + (r["uwagi"] or "") + "'>"
            "<br><button class='btn bp' style='margin-top:12px'>Zapisz</button>"
            "<a href='/klienci/" + str(kid) + "' class='btn bo' style='margin-left:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "zam")

    @app.route("/jaja_strata/<int:sid>/usun")
    @farm_required
    def jaja_strata_usun(sid):
        g = gid(); db = get_db()
        db.execute("DELETE FROM jaja_straty WHERE id=? AND gospodarstwo_id=?", (sid, g))
        db.commit(); db.close()
        flash("Strata usunieta.")
        return redirect("/magazyn-jaj")

    return app
