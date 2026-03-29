# -*- coding: utf-8 -*-
"""sprzedaz_views.py — /sprzedaz: formularz + magazyn + historia + klienci"""
from datetime import date


def register_sprzedaz(app):
    from flask import request, redirect, flash, session
    from db import get_db, get_setting
    from auth import farm_required
    from app import R
    from datetime import datetime

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    # ── POST: zapisz sprzedaż ─────────────────────────────────────────────
    @app.route("/sprzedaz", methods=["GET", "POST"])
    @farm_required
    def sprzedaz():
        g = gid()

        if request.method == "POST":
            db = get_db()
            d      = request.form.get("data", date.today().isoformat())
            sprzed = int(request.form.get("jaja_sprzedane", 0) or 0)
            cena   = float(request.form.get("cena_sprzedazy", 0) or 0)
            kid    = request.form.get("klient_id") or None
            zid    = request.form.get("zamowienie_id") or None
            typ    = request.form.get("typ_sprzedazy", "gotowka")
            uwagi  = request.form.get("uwagi", "")
            kwota  = round(sprzed * cena, 2)

            ex = db.execute(
                "SELECT id, jaja_zebrane FROM produkcja WHERE gospodarstwo_id=? AND data=?",
                (g, d)).fetchone()
            if ex:
                db.execute(
                    "UPDATE produkcja SET jaja_sprzedane=?,cena_sprzedazy=?,"
                    "klient_id=?,zamowienie_id=?,typ_sprzedazy=?,uwagi=? WHERE id=?",
                    (sprzed, cena, kid, zid, typ, uwagi, ex["id"]))
            else:
                db.execute(
                    "INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,"
                    "jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,klient_id,zamowienie_id,typ_sprzedazy,uwagi)"
                    " VALUES(?,?,0,?,?,0,?,?,?,?)",
                    (g, d, sprzed, cena, kid, zid, typ, uwagi))

            if zid:
                db.execute(
                    "UPDATE zamowienia SET status='dostarczone' WHERE id=? AND gospodarstwo_id=?",
                    (zid, g))

            if kid and sprzed > 0 and typ == "nastepnym_razem":
                ks = db.execute("SELECT saldo_pln FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
                stare = float(ks["saldo_pln"] if ks else 0)
                nowe = round(stare + kwota, 2)
                if ks:
                    db.execute("UPDATE konta_saldo SET saldo_pln=?,ostatnia_zmiana=datetime('now') WHERE klient_id=?",
                               (nowe, kid))
                else:
                    db.execute("INSERT INTO konta_saldo(klient_id,saldo_pln,ostatnia_zmiana) VALUES(?,?,datetime('now'))",
                               (kid, nowe))
                db.execute(
                    "INSERT INTO konta_transakcje(gospodarstwo_id,klient_id,data,typ,kwota,opis,saldo_po)"
                    " VALUES(?,?,datetime('now'),?,?,?,?)",
                    (g, kid, "sprzedaz", kwota,
                     str(sprzed) + " szt. x " + str(cena) + " zl", nowe))

            db.commit(); db.close()
            flash("Sprzedaz zapisana: " + str(sprzed) + " szt. x " + str(cena) + " zl = " + str(kwota) + " zl")
            return redirect("/sprzedaz")

        # ── GET ───────────────────────────────────────────────────────────
        db = get_db()

        # Stan magazynu
        mag = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s"
            " FROM produkcja WHERE gospodarstwo_id=?", (g,)).fetchone()
        stan = max(0, int(mag["p"]) - int(mag["s"]))
        rez = db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as s FROM zamowienia"
            " WHERE gospodarstwo_id=? AND status IN ('nowe','potwierdzone')", (g,)).fetchone()["s"]
        dostepne = max(0, stan - int(rez))

        # Klienci i zamówienia (do formularza)
        klienci = db.execute(
            "SELECT id, nazwa FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
        zamow_akt = db.execute(
            "SELECT z.id, z.data_dostawy, z.ilosc, k.nazwa as kn"
            " FROM zamowienia z LEFT JOIN klienci k ON z.klient_id=k.id"
            " WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')"
            " ORDER BY z.data_dostawy", (g,)).fetchall()
        cena_def = gs("cena_jajka", "1.20")

        # Historia sprzedaży
        historia = db.execute("""
            SELECT p.data, p.jaja_sprzedane, p.cena_sprzedazy, p.typ_sprzedazy, p.uwagi,
                   k.id as kid, k.nazwa as kn,
                   ROUND(p.jaja_sprzedane * COALESCE(p.cena_sprzedazy,0), 2) as kwota
            FROM produkcja p
            LEFT JOIN klienci k ON p.klient_id = k.id
            WHERE p.gospodarstwo_id=? AND p.jaja_sprzedane > 0
            ORDER BY p.data DESC LIMIT 60""", (g,)).fetchall()

        stat = db.execute(
            "SELECT COALESCE(SUM(jaja_sprzedane),0) as szt,"
            " COALESCE(SUM(jaja_sprzedane*COALESCE(cena_sprzedazy,0)),0) as kwota"
            " FROM produkcja WHERE gospodarstwo_id=?"
            " AND strftime('%Y-%m',data)=strftime('%Y-%m','now')"
            " AND jaja_sprzedane>0", (g,)).fetchone()

        # Klienci z saldami
        klienci_saldo = db.execute("""
            SELECT k.id, k.nazwa, k.telefon,
                   COALESCE(ks.saldo_pln, 0) as saldo,
                   COUNT(DISTINCT p.data) as transakcji,
                   COALESCE(SUM(CASE WHEN p.jaja_sprzedane>0
                       THEN p.jaja_sprzedane*COALESCE(p.cena_sprzedazy,0) ELSE 0 END), 0) as total,
                   MAX(p.data) as ostatnia
            FROM klienci k
            LEFT JOIN konta_saldo ks ON ks.klient_id=k.id
            LEFT JOIN produkcja p ON p.klient_id=k.id AND p.gospodarstwo_id=?
            WHERE k.gospodarstwo_id=?
            GROUP BY k.id ORDER BY ABS(COALESCE(ks.saldo_pln,0)) DESC, k.nazwa""",
            (g, g)).fetchall()

        # Aktywne zamówienia
        zam_aktywne = db.execute(
            "SELECT z.*, k.nazwa as kn FROM zamowienia z"
            " LEFT JOIN klienci k ON z.klient_id=k.id"
            " WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')"
            " ORDER BY z.data_dostawy", (g,)).fetchall()

        db.close()

        TYP_ICO = {"gotowka": "💵", "przelew": "🏦", "z_salda": "📋", "nastepnym_razem": "⏳"}
        dzis = date.today().isoformat()
        suma_dlug = sum(max(0, float(k["saldo"] or 0)) for k in klienci_saldo)

        # ─── 1. FORMULARZ SPRZEDAŻY ───────────────────────────────────────
        kl_opt = "<option value=''>— anonimowa —</option>" + "".join(
            "<option value='" + str(k["id"]) + "'>" + k["nazwa"] + "</option>"
            for k in klienci)
        zam_opt = "<option value=''>— bez zamówienia —</option>" + "".join(
            "<option value='" + str(z["id"]) + "'>"
            + z["data_dostawy"] + " · " + (z["kn"] or "?") + " · " + str(z["ilosc"]) + " szt."
            + "</option>"
            for z in zamow_akt)

        s_formularz = (
            "<div class='card' style='margin-bottom:12px'>"
            "<b style='font-size:15px'>Sprzedaj jaja</b>"
            "<form method='POST' action='/sprzedaz' style='margin-top:12px'>"

            "<div class='g3'>"
            "<div><label>Sprzedane (szt)</label>"
            "<input name='jaja_sprzedane' type='number' min='0' required"
            " style='font-size:20px;text-align:center' placeholder='0'></div>"
            "<div><label>Cena/szt (zł)</label>"
            "<input name='cena_sprzedazy' type='number' step='0.01' min='0'"
            " id='cena' oninput='oblicz()' value='" + str(cena_def) + "'"
            " style='font-size:20px;text-align:center'></div>"
            "<div><label>Data</label>"
            "<input name='data' type='date' value='" + dzis + "'></div>"
            "</div>"

            "<div style='background:#f5f5f0;border-radius:8px;padding:8px 12px;"
            "font-size:14px;margin:8px 0'>Wartość: <b id='wartosc'>— zł</b></div>"

            "<div class='g2'>"
            "<div><label>Klient</label><select name='klient_id'>" + kl_opt + "</select></div>"
            "<div><label>Typ płatności</label>"
            "<select name='typ_sprzedazy'>"
            "<option value='gotowka'>💵 Gotówka</option>"
            "<option value='przelew'>🏦 Przelew</option>"
            "<option value='nastepnym_razem'>⏳ Następnym razem (dług)</option>"
            "<option value='z_salda'>📋 Z salda</option>"
            "</select></div>"
            "</div>"

            + ("<div><label>Zamówienie</label>"
               "<select name='zamowienie_id'>" + zam_opt + "</select></div>"
               if zamow_akt else "<input type='hidden' name='zamowienie_id' value=''>")

            + "<div><label>Uwagi</label>"
            "<input name='uwagi' placeholder='opcjonalnie'></div>"

            "<button class='btn bg' style='width:100%;margin-top:12px;padding:12px;font-size:15px'>"
            "Zapisz sprzedaż</button>"
            "</form>"
            "<script>function oblicz(){"
            "var s=parseFloat(document.querySelector('[name=jaja_sprzedane]').value)||0,"
            "c=parseFloat(document.getElementById('cena').value)||0;"
            "document.getElementById('wartosc').textContent=(s*c).toFixed(2)+' zl';}"
            "document.querySelector('[name=jaja_sprzedane]').addEventListener('input',oblicz);"
            "</script>"
            "</div>"
        )

        # ─── 2. LICZNIKI MAGAZYNU ─────────────────────────────────────────
        c_stan = "#3B6D11" if stan > 0 else "#888"
        c_dost = "#3B6D11" if dostepne > 0 else "#A32D2D"
        c_dlug = "#A32D2D" if suma_dlug > 0.01 else "#888"

        s_magazyn = (
            "<div class='g4' style='margin-bottom:12px'>"
            "<div class='card stat'><div class='v' style='color:" + c_stan + "'>" + str(stan) + "</div>"
            "<div class='l'>W magazynie</div><div class='s'>szt. jaj</div></div>"
            "<div class='card stat'><div class='v' style='color:#BA7517'>" + str(int(rez)) + "</div>"
            "<div class='l'>Zarezerwowane</div><div class='s'>w zamówieniach</div></div>"
            "<div class='card stat'><div class='v' style='color:" + c_dost + "'>" + str(dostepne) + "</div>"
            "<div class='l'>Dostępne</div><div class='s'>do sprzedaży</div></div>"
            "<div class='card stat'><div class='v' style='color:" + c_dlug + "'>"
            + str(round(suma_dlug, 2)) + " zł</div>"
            "<div class='l'>Do odebrania</div><div class='s'>łączne długi</div></div>"
            "</div>"
        )

        # ─── 3. ZAMÓWIENIA DO REALIZACJI ──────────────────────────────────
        zam_html = ""
        for z in zam_aktywne:
            alarm = " ⚠️" if z["data_dostawy"] == dzis else ""
            kwota_z = round(z["ilosc"] * (z["cena_za_szt"] or 0), 2)
            zam_html += (
                "<tr>"
                "<td style='white-space:nowrap'>" + z["data_dostawy"] + alarm + "</td>"
                "<td style='font-weight:600'>" + str(z["ilosc"]) + " szt.</td>"
                "<td>" + (z["kn"] or "—") + "</td>"
                "<td>" + str(kwota_z) + " zł</td>"
                "<td class='nowrap'>"
                "<a href='/zamowienia/" + str(z["id"]) + "/status/dostarczone' class='btn bg bsm'>✓ Dostarcz</a> "
                "<a href='/zamowienia/" + str(z["id"]) + "/status/anulowane' class='btn br bsm'"
                " onclick=\"return confirm('Anuloac?')\">✕</a>"
                "</td></tr>"
            )

        s_zamowienia = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
            "<b>🛒 Zamówienia do realizacji</b>"
            "<a href='/zamowienia/dodaj' class='btn bp bsm'>+ Nowe</a>"
            "</div>"
            + (
                "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
                "<th>Dostawa</th><th>Ilość</th><th>Klient</th><th>Wartość</th><th></th>"
                "</tr></thead><tbody>" + zam_html + "</tbody></table></div>"
                if zam_html else
                "<p style='color:#888;font-size:13px;text-align:center;padding:8px'>Brak aktywnych zamówień</p>"
            )
            + "</div>"
        )

        # ─── 4. HISTORIA SPRZEDAŻY ────────────────────────────────────────
        hist_html = ""
        for r in historia:
            klink = ("<a href='#k-" + str(r["kid"]) + "' style='color:#534AB7'>" + r["kn"] + "</a>"
                     if r["kid"] else "—")
            hist_html += (
                "<tr>"
                "<td style='white-space:nowrap;font-size:13px'>" + r["data"] + "</td>"
                "<td style='font-weight:700;text-align:center'>" + str(r["jaja_sprzedane"]) + "</td>"
                "<td style='text-align:right;color:#888'>" + str(r["cena_sprzedazy"] or "—") + " zł</td>"
                "<td style='font-weight:600;color:#3B6D11;text-align:right'>" + str(r["kwota"]) + " zł</td>"
                "<td>" + klink + "</td>"
                "<td style='font-size:15px'>" + TYP_ICO.get(r["typ_sprzedazy"] or "", "?") + "</td>"
                "<td style='font-size:11px;color:#888'>" + (r["uwagi"] or "") + "</td>"
                "</tr>"
            )

        s_historia = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;"
            "margin-bottom:8px;flex-wrap:wrap;gap:6px'>"
            "<b>📋 Historia sprzedaży</b>"
            "<span style='font-size:12px;color:#5f5e5a'>"
            "Miesiąc: <b style='color:#3B6D11'>" + str(int(stat["szt"])) + " szt.</b>"
            " · <b>" + str(round(float(stat["kwota"]), 2)) + " zł</b>"
            " &nbsp;💵🏦📋⏳"
            "</span>"
            "</div>"
            "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
            "<th>Data</th><th style='text-align:center'>Szt</th>"
            "<th style='text-align:right'>Cena</th><th style='text-align:right'>Kwota</th>"
            "<th>Klient</th><th>Płat.</th><th>Uwagi</th>"
            "</tr></thead><tbody>"
            + (hist_html or "<tr><td colspan=7 style='color:#888;text-align:center;padding:16px'>Brak sprzedaży</td></tr>")
            + "</tbody></table></div></div>"
        )

        # ─── 5. KLIENCI ───────────────────────────────────────────────────
        kl_html = ""
        for k in klienci_saldo:
            saldo = float(k["saldo"] or 0)
            kid_id = k["id"]
            if saldo > 0.01:
                s_kol, s_txt, s_b = "#A32D2D", "Dług: " + str(round(saldo, 2)) + " zł", "b-red"
            elif saldo < -0.01:
                s_kol, s_txt, s_b = "#3B6D11", "Nadpłata: " + str(round(-saldo, 2)) + " zł", "b-green"
            else:
                s_kol, s_txt, s_b = "#888", "Rozliczony", "b-gray"

            ostatnie_k = [r for r in historia if r["kid"] == kid_id][:5]
            ost_html = ""
            for r in ostatnie_k:
                ost_html += (
                    "<div style='display:flex;gap:10px;padding:3px 0;font-size:12px;"
                    "border-bottom:1px solid #f0ede4'>"
                    "<span style='color:#888;white-space:nowrap'>" + r["data"] + "</span>"
                    "<span>" + str(r["jaja_sprzedane"]) + " szt.</span>"
                    "<span style='color:#3B6D11;font-weight:600'>" + str(r["kwota"]) + " zł</span>"
                    "<span>" + TYP_ICO.get(r["typ_sprzedazy"] or "", "") + "</span>"
                    "</div>"
                )

            kl_html += (
                "<div class='card' id='k-" + str(kid_id) + "'"
                " style='border-left:4px solid " + s_kol + ";margin-bottom:8px'>"
                "<div style='display:flex;justify-content:space-between;align-items:flex-start;"
                "flex-wrap:wrap;gap:8px'>"
                "<div>"
                "<div style='font-weight:600;font-size:15px'>" + k["nazwa"] + "</div>"
                + ("<div style='font-size:12px;color:#888'>" + k["telefon"] + "</div>" if k["telefon"] else "")
                + "<div style='margin-top:4px'><span class='badge " + s_b + "'>" + s_txt + "</span></div>"
                "<div style='font-size:11px;color:#aaa;margin-top:3px'>"
                + str(k["transakcji"]) + " transakcji · " + str(round(float(k["total"]), 2)) + " zł łącznie"
                + ("  · ostatnia: " + k["ostatnia"] if k["ostatnia"] else "")
                + "</div></div>"
                "<div style='display:flex;gap:6px;flex-wrap:wrap'>"
                "<a href='/klienci/" + str(kid_id) + "/wplata' class='btn bg bsm'>+ Wpłata</a>"
                "<a href='/klienci/" + str(kid_id) + "/korekta-saldo' class='btn bo bsm'>Korekta</a>"
                "<a href='/klienci/" + str(kid_id) + "/edytuj' class='btn bo bsm'>Edytuj</a>"
                "</div></div>"
                + (
                    "<div style='margin-top:8px;padding-top:8px;border-top:1px solid #f0ede4'>"
                    + ost_html + "</div>"
                    if ost_html else
                    "<div style='font-size:11px;color:#ccc;margin-top:6px'>Brak transakcji sprzedaży</div>"
                )
                + "</div>"
            )

        s_klienci = (
            "<div style='display:flex;justify-content:space-between;align-items:center;"
            "margin-bottom:8px;flex-wrap:wrap;gap:8px'>"
            "<b style='font-size:15px'>👥 Klienci</b>"
            "<a href='/klienci/dodaj' class='btn bp bsm'>+ Nowy klient</a>"
            "</div>"
            + (kl_html or
               "<div class='card'><p style='color:#888;text-align:center;padding:20px'>"
               "Brak klientów. <a href='/klienci/dodaj' style='color:#534AB7'>Dodaj →</a></p></div>")
        )

        html = (
            "<h1>Sprzedaż</h1>"
            + s_formularz
            + s_magazyn
            + s_zamowienia
            + s_historia
            + s_klienci
        )
        return R(html, "zam")

    return app
