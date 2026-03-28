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

    @app.route("/produkcja")
    @farm_required
    def produkcja():
        g = gid(); db = get_db()
        rows = db.execute(
            "SELECT * FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 90", (g,)).fetchall()
        kur = db.execute(
            "SELECT COALESCE(SUM(liczba),0) as s FROM stado "
            "WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'", (g,)).fetchone()["s"] or 1
        # Statystyki miesiąc
        stat = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as sum_zeb, "
            "COALESCE(AVG(jaja_zebrane),0) as avg_zeb, COUNT(*) as dni "
            "FROM produkcja WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()
        db.close()

        rows_html = ""
        for r in rows:
            niesn = round(r["jaja_zebrane"] / kur * 100, 1) if kur else 0
            kol = "#3B6D11" if niesn >= 80 else "#BA7517" if niesn >= 60 else "#A32D2D"
            rows_html += (
                f"<tr>"
                f"<td style='white-space:nowrap;font-size:13px'>{r['data']}</td>"
                f"<td style='font-weight:700;font-size:18px;text-align:center'>{r['jaja_zebrane']}</td>"
                f"<td style='color:{kol};font-weight:600;text-align:center'>{niesn}%</td>"
                f"<td style='color:#888;font-size:12px'>{r['uwagi'] or ''}</td>"
                f"<td><a href='/produkcja/edytuj/{r['data']}' class='btn bo bsm'>Edytuj</a></td>"
                f"</tr>"
            )

        html = (
            "<h1>Produkcja jaj</h1>"
            "<div style='display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap'>"
            "<a href='/sprzedaz' class='btn bo bsm'>→ Historia sprzedaży</a>"
            "</div>"
            + (f"<div class='g3' style='margin-bottom:12px'>"
               f"<div class='card stat'><div class='v'>{int(stat['sum_zeb'])}</div><div class='l'>Zebrano w miesiącu</div></div>"
               f"<div class='card stat'><div class='v'>{round(stat['avg_zeb'],1)}</div><div class='l'>Średnio / dzień</div></div>"
               f"<div class='card stat'><div class='v'>{stat['dni']}</div><div class='l'>Dni z wpisem</div></div>"
               f"</div>")
            + "<div class='card' style='overflow-x:auto'>"
            "<table><thead><tr>"
            "<th>Data</th><th style='text-align:center'>Zebrane</th>"
            "<th style='text-align:center'>Nieśność</th><th>Uwagi</th><th></th>"
            "</tr></thead>"
            f"<tbody>{rows_html or '<tr><td colspan=5 style=\"color:#888;text-align:center;padding:20px\">Brak wpisów</td></tr>'}</tbody>"
            "</table></div>"
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
            db.close(); flash("Nie znaleziono wpisu."); return redirect("/produkcja")

        if request.method == "POST":
            jaja  = int(request.form.get("jaja_zebrane", 0) or 0)
            uwagi = request.form.get("uwagi", "")
            pasza = float(request.form.get("pasza_wydana_kg", r["pasza_wydana_kg"] or 0) or 0)
            db.execute(
                "UPDATE produkcja SET jaja_zebrane=?,uwagi=?,pasza_wydana_kg=? "
                "WHERE gospodarstwo_id=? AND data=?", (jaja, uwagi, pasza, g, data))
            db.commit(); db.close()
            flash(f"Wpis {data} zaktualizowany.")
            return redirect("/produkcja")
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
                   COALESCE(SUM(CASE WHEN p.jaja_sprzedane>0
                       THEN p.jaja_sprzedane*COALESCE(p.cena_sprzedazy,0) ELSE 0 END),0) as total_kwota,
                   MAX(p.data) as ostatnia_transakcja
            FROM klienci k
            LEFT JOIN konta_saldo ks ON ks.klient_id=k.id
            LEFT JOIN produkcja p ON p.klient_id=k.id AND p.gospodarstwo_id=?
            WHERE k.gospodarstwo_id=?
            GROUP BY k.id ORDER BY k.nazwa""", (g, g)).fetchall()
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
        if saldo > 0.01:
            saldo_kol = "#A32D2D"
            saldo_txt = f"Do zapłaty: {round(saldo,2)} zł"
            saldo_sub = "Klient ma dług — oczekuje na płatność"
        elif saldo < -0.01:
            saldo_kol = "#3B6D11"
            saldo_txt = f"Nadpłata: {round(-saldo,2)} zł"
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
            f"<div style='margin-top:12px;display:flex;gap:8px;flex-wrap:wrap'>"
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
            if kwota <= 0:
                flash("Kwota musi być > 0"); db.close(); return redirect(f"/klienci/{kid}/wplata")
            from datetime import datetime
            nowe_saldo = round(saldo - kwota, 2)  # wpłata zmniejsza dług
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
            flash(f"Wpłata {kwota} zł zarejestrowana. Nowe saldo: {nowe_saldo} zł")
            return redirect(f"/klienci/{kid}")

        db.close()
        html = (
            f"<h1>Wpłata od: {k['nazwa']}</h1>"
            f"<div class='card'><form method='POST'>"
            f"<div class='al {'ald' if saldo > 0 else 'alok'}'>"
            f"Aktualne saldo: <b>{'Dług: ' + str(round(saldo,2)) + ' zł' if saldo > 0 else 'Nadpłata: ' + str(round(-saldo,2)) + ' zł' if saldo < 0 else 'Rozliczony'}</b></div>"
            "<label style='margin-top:12px'>Kwota wpłaty (zł)</label>"
            "<input name='kwota' type='number' step='0.01' min='0.01' required style='font-size:24px;text-align:center' placeholder='0.00'>"
            "<label>Opis</label>"
            "<input name='opis' value='Wpłata gotówkowa' placeholder='np. Wpłata za jaja, Przelew'>"
            "<br><button class='btn bg' style='margin-top:12px;width:100%;padding:12px'>Zarejestruj wpłatę</button>"
            f"<a href='/klienci/{kid}' class='btn bo' style='display:block;text-align:center;margin-top:8px'>Anuluj</a>"
            "</form></div>"
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
            db.execute(
                "UPDATE klienci SET nazwa=?,telefon=?,email=?,adres=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                (request.form["nazwa"], request.form.get("telefon", ""), request.form.get("email", ""),
                 request.form.get("adres", ""), request.form.get("uwagi", ""), kid, g))
            db.commit(); db.close()
            flash("Klient zaktualizowany.")
            return redirect(f"/klienci/{kid}")
        r = db.execute("SELECT * FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid, g)).fetchone()
        db.close()
        if not r: return redirect("/klienci")
        html = (
            f"<h1>Edytuj: {r['nazwa']}</h1><div class='card'><form method='POST'>"
            f"<label>Nazwa</label><input name='nazwa' required value='{r['nazwa']}'>"
            "<div class='g2'>"
            f"<div><label>Telefon</label><input name='telefon' value='{r['telefon'] or ''}'></div>"
            f"<div><label>Email</label><input name='email' value='{r['email'] or ''}'></div>"
            "</div>"
            f"<label>Adres</label><textarea name='adres' rows='2'>{r['adres'] or ''}</textarea>"
            f"<label>Uwagi</label><input name='uwagi' value='{r['uwagi'] or ''}'>"
            "<br><button class='btn bp' style='margin-top:12px'>Zapisz</button>"
            f"<a href='/klienci/{kid}' class='btn bo' style='margin-left:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "zam")

    return app
