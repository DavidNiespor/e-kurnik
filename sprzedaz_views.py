# -*- coding: utf-8 -*-
"""sprzedaz_views.py — jedna strona /sprzedaz ze wszystkim"""
from datetime import date


def register_sprzedaz(app):
    from flask import request, redirect, flash, session
    from db import get_db, get_setting
    from auth import farm_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    @app.route("/sprzedaz")
    @farm_required
    def sprzedaz():
        g = gid()
        db = get_db()

        # ── Dane magazyn ──────────────────────────────────────────────────
        mag = db.execute(
            "SELECT COALESCE(SUM(jaja_zebrane),0) as p, COALESCE(SUM(jaja_sprzedane),0) as s "
            "FROM produkcja WHERE gospodarstwo_id=?", (g,)).fetchone()
        stan = max(0, int(mag["p"]) - int(mag["s"]))

        rez_rows = db.execute(
            "SELECT z.*, k.nazwa as kn FROM zamowienia z "
            "LEFT JOIN klienci k ON z.klient_id=k.id "
            "WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone') "
            "ORDER BY z.data_dostawy", (g,)).fetchall()
        zarezerwowane = sum(r["ilosc"] for r in rez_rows)
        dostepne = max(0, stan - zarezerwowane)

        # ── Dane sprzedaży ────────────────────────────────────────────────
        sprzedaz_rows = db.execute("""
            SELECT p.data, p.jaja_sprzedane, p.cena_sprzedazy, p.typ_sprzedazy, p.uwagi,
                   k.id as kid, k.nazwa as kn,
                   ROUND(p.jaja_sprzedane * COALESCE(p.cena_sprzedazy, 0), 2) as kwota
            FROM produkcja p
            LEFT JOIN klienci k ON p.klient_id = k.id
            WHERE p.gospodarstwo_id=? AND p.jaja_sprzedane > 0
            ORDER BY p.data DESC LIMIT 60""", (g,)).fetchall()

        stat_mies = db.execute(
            "SELECT COALESCE(SUM(jaja_sprzedane),0) as szt, "
            "COALESCE(SUM(jaja_sprzedane*COALESCE(cena_sprzedazy,0)),0) as kwota "
            "FROM produkcja WHERE gospodarstwo_id=? "
            "AND strftime('%Y-%m',data)=strftime('%Y-%m','now') "
            "AND jaja_sprzedane>0", (g,)).fetchone()

        # ── Dane klientów ─────────────────────────────────────────────────
        klienci_rows = db.execute("""
            SELECT k.*,
                   COALESCE(ks.saldo_pln, 0) as saldo,
                   COUNT(DISTINCT p.data) as transakcji,
                   COALESCE(SUM(CASE WHEN p.jaja_sprzedane>0
                       THEN p.jaja_sprzedane*COALESCE(p.cena_sprzedazy,0) ELSE 0 END), 0) as total,
                   MAX(p.data) as ostatnia
            FROM klienci k
            LEFT JOIN konta_saldo ks ON ks.klient_id = k.id
            LEFT JOIN produkcja p ON p.klient_id=k.id AND p.gospodarstwo_id=?
            WHERE k.gospodarstwo_id=?
            GROUP BY k.id ORDER BY ABS(COALESCE(ks.saldo_pln,0)) DESC, k.nazwa""", (g, g)).fetchall()

        suma_dlug = sum(max(0, float(k["saldo"] or 0)) for k in klienci_rows)

        db.close()

        dzis = date.today().isoformat()
        TYP = {"gotowka": "💵", "przelew": "🏦", "z_salda": "📋", "nastepnym_razem": "⏳"}

        # ═══════════════════════════════════════════════════════════════════
        # HTML — SEKCJA 1: Stan magazynu + liczniki
        # ═══════════════════════════════════════════════════════════════════
        c_stan = "#3B6D11" if stan > 0 else "#888"
        c_dost = "#3B6D11" if dostepne > 0 else "#A32D2D"
        c_dlug = "#A32D2D" if suma_dlug > 0.01 else "#888"

        s1 = (
            "<div class='g4' style='margin-bottom:4px'>"
            "<div class='card stat'>"
            "<div class='v' style='color:" + c_stan + "'>" + str(stan) + "</div>"
            "<div class='l'>W magazynie</div>"
            "<div class='s'>szt. jaj</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v' style='color:#BA7517'>" + str(zarezerwowane) + "</div>"
            "<div class='l'>Zarezerwowane</div>"
            "<div class='s'>w zamówieniach</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v' style='color:" + c_dost + "'>" + str(dostepne) + "</div>"
            "<div class='l'>Dostępne</div>"
            "<div class='s'>do sprzedaży</div>"
            "</div>"
            "<div class='card stat'>"
            "<div class='v' style='color:" + c_dlug + "'>" + str(round(suma_dlug, 2)) + " zł</div>"
            "<div class='l'>Do odebrania</div>"
            "<div class='s'>łączne długi</div>"
            "</div>"
            "</div>"
        )

        # ═══════════════════════════════════════════════════════════════════
        # SEKCJA 2: Aktywne zamówienia
        # ═══════════════════════════════════════════════════════════════════
        zam_rows_html = ""
        for r in rez_rows:
            alarm = " ⚠️" if r["data_dostawy"] == dzis else ""
            kwarta = round(r["ilosc"] * (r["cena_za_szt"] or 0), 2)
            zam_rows_html += (
                "<tr>"
                "<td style='white-space:nowrap;font-weight:500'>" + r["data_dostawy"] + alarm + "</td>"
                "<td style='font-weight:600'>" + str(r["ilosc"]) + " szt.</td>"
                "<td>" + (r["kn"] or "—") + "</td>"
                "<td style='color:#3B6D11'>" + str(kwarta) + " zł</td>"
                "<td class='nowrap'>"
                "<a href='/zamowienia/" + str(r["id"]) + "/status/dostarczone' class='btn bg bsm'>✓ Dostarcz</a> "
                "<a href='/zamowienia/" + str(r["id"]) + "/status/anulowane' class='btn br bsm' "
                "onclick=\"return confirm('Anulować?')\">✕</a>"
                "</td></tr>"
            )

        s2 = (
            "<div class='card'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px'>"
            "<b>🛒 Zamówienia do realizacji</b>"
            "<a href='/zamowienia/dodaj' class='btn bp bsm'>+ Nowe zamówienie</a>"
            "</div>"
            + (
                "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
                "<th>Dostawa</th><th>Ilość</th><th>Klient</th><th>Wartość</th><th>Akcja</th>"
                "</tr></thead><tbody>" + zam_rows_html + "</tbody></table></div>"
                if zam_rows_html else
                "<p style='color:#888;text-align:center;padding:12px'>Brak aktywnych zamówień</p>"
            )
            + "</div>"
        )

        # ═══════════════════════════════════════════════════════════════════
        # SEKCJA 3: Historia sprzedaży (ostatnie 60)
        # ═══════════════════════════════════════════════════════════════════
        sp_rows_html = ""
        for r in sprzedaz_rows:
            kid_link = ("<a href='#k-" + str(r["kid"]) + "' style='color:#534AB7'>" + r["kn"] + "</a>"
                        if r["kid"] else "—")
            sp_rows_html += (
                "<tr>"
                "<td style='font-size:13px;white-space:nowrap'>" + r["data"] + "</td>"
                "<td style='font-weight:700;text-align:center;font-size:15px'>" + str(r["jaja_sprzedane"]) + "</td>"
                "<td style='text-align:right;color:#888'>" + str(r["cena_sprzedazy"] or "—") + " zł</td>"
                "<td style='font-weight:600;color:#3B6D11;text-align:right'>" + str(r["kwota"]) + " zł</td>"
                "<td>" + kid_link + "</td>"
                "<td style='font-size:16px' title='" + (r["typ_sprzedazy"] or "") + "'>"
                + TYP.get(r["typ_sprzedazy"] or "", "?") + "</td>"
                "<td style='font-size:11px;color:#888'>" + (r["uwagi"] or "") + "</td>"
                "</tr>"
            )

        s3 = (
            "<div class='card'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px'>"
            "<b>📋 Historia sprzedaży</b>"
            "<div style='font-size:13px;color:#5f5e5a'>"
            "Ten miesiąc: <b style='color:#3B6D11'>" + str(int(stat_mies["szt"])) + " szt.</b>"
            " — <b>" + str(round(float(stat_mies["kwota"]), 2)) + " zł</b>"
            "&nbsp; 💵 gotówka &nbsp; 🏦 przelew &nbsp; 📋 z salda &nbsp; ⏳ następnym razem"
            "</div>"
            "</div>"
            "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
            "<th>Data</th><th style='text-align:center'>Szt</th>"
            "<th style='text-align:right'>Cena/szt</th><th style='text-align:right'>Kwota</th>"
            "<th>Klient</th><th>Płat.</th><th>Uwagi</th>"
            "</tr></thead>"
            "<tbody>" + (sp_rows_html or "<tr><td colspan=7 style='color:#888;text-align:center;padding:16px'>Brak sprzedaży</td></tr>") + "</tbody>"
            "</table></div></div>"
        )

        # ═══════════════════════════════════════════════════════════════════
        # SEKCJA 4: Klienci — karty z historią inline
        # ═══════════════════════════════════════════════════════════════════
        kl_cards = ""
        for k in klienci_rows:
            saldo = float(k["saldo"] or 0)
            kid = k["id"]

            if saldo > 0.01:
                s_kol = "#A32D2D"
                s_txt = "Dług: " + str(round(saldo, 2)) + " zł"
                s_badge = "b-red"
            elif saldo < -0.01:
                s_kol = "#3B6D11"
                s_txt = "Nadpłata: " + str(round(-saldo, 2)) + " zł"
                s_badge = "b-green"
            else:
                s_kol = "#888"
                s_txt = "Rozliczony"
                s_badge = "b-gray"

            # Ostatnie 5 transakcji tego klienta z row-cache
            ostatnie = [r for r in sprzedaz_rows if r["kid"] == kid][:5]
            last_html = ""
            for r in ostatnie:
                last_html += (
                    "<div style='display:flex;justify-content:space-between;padding:4px 0;"
                    "border-bottom:1px solid #f0ede4;font-size:12px'>"
                    "<span style='color:#888'>" + r["data"] + "</span>"
                    "<span>" + str(r["jaja_sprzedane"]) + " szt.</span>"
                    "<span style='font-weight:600;color:#3B6D11'>" + str(r["kwota"]) + " zł</span>"
                    "<span>" + TYP.get(r["typ_sprzedazy"] or "", "?") + "</span>"
                    "</div>"
                )

            kl_cards += (
                "<div class='card' id='k-" + str(kid) + "' style='border-left:4px solid " + s_kol + ";margin-bottom:10px'>"
                "<div style='display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:8px'>"
                # Lewa: info
                "<div>"
                "<div style='font-size:16px;font-weight:600'>" + k["nazwa"] + "</div>"
                + ("<div style='font-size:12px;color:#888;margin-top:2px'>" + k["telefon"] + "</div>" if k["telefon"] else "")
                + "<div style='margin-top:6px'>"
                "<span class='badge " + s_badge + "' style='font-size:13px;padding:4px 10px'>" + s_txt + "</span>"
                "</div>"
                "<div style='font-size:12px;color:#888;margin-top:4px'>"
                + str(k["transakcji"]) + " transakcji · " + str(round(float(k["total"]), 2)) + " zł łącznie"
                + ("  · ostatnia: " + k["ostatnia"] if k["ostatnia"] else "")
                + "</div>"
                "</div>"
                # Prawa: przyciski
                "<div style='display:flex;gap:6px;flex-wrap:wrap;align-items:flex-start'>"
                "<a href='/klienci/" + str(kid) + "/wplata' class='btn bg bsm'>+ Wpłata</a>"
                "<a href='/klienci/" + str(kid) + "/korekta-saldo' class='btn bo bsm'>Korekta salda</a>"
                "<a href='/klienci/" + str(kid) + "/edytuj' class='btn bo bsm'>Edytuj</a>"
                "</div>"
                "</div>"
                # Historia inline
                + (
                    "<div style='margin-top:10px;border-top:1px solid #f0ede4;padding-top:8px'>"
                    "<div style='font-size:11px;color:#aaa;margin-bottom:4px'>Ostatnie transakcje:</div>"
                    + last_html +
                    "</div>"
                    if last_html else
                    "<div style='margin-top:8px;font-size:12px;color:#aaa'>Brak transakcji sprzedaży</div>"
                )
                + "</div>"
            )

        s4 = (
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px'>"
            "<b style='font-size:16px'>👥 Klienci</b>"
            "<a href='/klienci/dodaj' class='btn bp bsm'>+ Nowy klient</a>"
            "</div>"
            + (kl_cards or "<div class='card'><p style='color:#888;text-align:center;padding:20px'>Brak klientów. <a href='/klienci/dodaj' style='color:#534AB7'>Dodaj pierwszego →</a></p></div>")
        )

        # ═══════════════════════════════════════════════════════════════════
        # Całość
        # ═══════════════════════════════════════════════════════════════════
        html = (
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px'>"
            "<h1 style='margin-bottom:0'>Sprzedaż</h1>"
            "<div style='display:flex;gap:6px;flex-wrap:wrap'>"
            "<a href='/zamowienia/dodaj' class='btn bp bsm'>+ Zamówienie</a>"
            "<a href='/klienci/dodaj' class='btn bo bsm'>+ Klient</a>"
            "</div>"
            "</div>"
            + s1 + s2 + s3 + s4
        )
        return R(html, "zam")

    return app
