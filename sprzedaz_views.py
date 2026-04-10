# -*- coding: utf-8 -*-
"""sprzedaz_views.py — /sprzedaz: formularz + magazyn + historia + klienci"""
from datetime import date, timedelta


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

            # Zapisz jako osobna transakcja (wiele per dzien)
            db.execute(
                "INSERT INTO sprzedaz_szczegol"
                "(gospodarstwo_id,data,klient_id,zamowienie_id,ilosc,cena_szt,wartosc,typ,uwagi)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (g, d, kid, zid, sprzed, cena, kwota, typ, uwagi))
            # Aktualizuj sumy w produkcja (magazyn jaj)
            ex = db.execute(
                "SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?",
                (g, d)).fetchone()
            if ex:
                db.execute(
                    "UPDATE produkcja SET"
                    " jaja_sprzedane=(SELECT COALESCE(SUM(ilosc),0) FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND data=?),"
                    " cena_sprzedazy=?,klient_id=?,typ_sprzedazy=? WHERE id=?",
                    (g, d, cena, kid, typ, ex["id"]))
            else:
                db.execute(
                    "INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,klient_id,typ_sprzedazy)"
                    " VALUES(?,?,0,?,?,0,?,?)",
                    (g, d, sprzed, cena, kid, typ))

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

            # Rabat — obniż wartość transakcji
            rabat = float(request.form.get("rabat", 0) or 0)
            if rabat > 0:
                kwota = max(0, round(kwota - rabat, 2))
                db.execute("UPDATE sprzedaz_szczegol SET wartosc=? WHERE id=(SELECT MAX(id) FROM sprzedaz_szczegol WHERE gospodarstwo_id=?)", (kwota, g))

            # Wpłata klienta — zaktualizuj saldo
            wplata = float(request.form.get("wplata_klienta", 0) or 0)
            rozlicz0 = request.form.get("rozlicz_do_zera") == "1"
            if kid and (wplata > 0 or rozlicz0):
                from datetime import datetime
                ks2 = db.execute("SELECT saldo_pln FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
                stare_sal = float(ks2["saldo_pln"] if ks2 else 0)
                do_zaplaty = round(stare_sal + kwota, 2)
                if rozlicz0:
                    # Zeruj saldo niezaleznie od reszty/nadplaty
                    nowe_sal = 0.0
                    if wplata <= 0: wplata = max(0, do_zaplaty)
                    reszta = round(wplata - do_zaplaty, 2)
                else:
                    nowe_sal = round(do_zaplaty - wplata, 2)
                    reszta = round(wplata - do_zaplaty, 2)
                if ks2:
                    db.execute("UPDATE konta_saldo SET saldo_pln=?,ostatnia_zmiana=datetime('now') WHERE klient_id=?", (nowe_sal, kid))
                else:
                    db.execute("INSERT INTO konta_saldo(klient_id,saldo_pln,ostatnia_zmiana) VALUES(?,?,datetime('now'))", (kid, nowe_sal))
                opis = ("Rozliczono do zera" if rozlicz0 else "Wplata") + " przy sprzedazy " + str(sprzed) + " szt."
                db.execute("INSERT INTO konta_transakcje(gospodarstwo_id,klient_id,data,typ,kwota,opis,saldo_po) VALUES(?,?,datetime('now'),?,?,?,?)"
                    , (g, kid, "wplata", -wplata, opis, nowe_sal))
                flash_msg = ("Zapisano: " + str(sprzed) + " szt. = " + str(kwota) + " zl"
                    + (", rabat: " + str(rabat) + " zl" if rabat > 0 else "")
                    + (", wplata: " + str(wplata) + " zl" if wplata > 0 else "")
                    + (" | Saldo wyzerowane ✓" if rozlicz0 else "")
                    + (" | Reszta: " + str(reszta) + " zl" if not rozlicz0 and reszta > 0.005 else "")
                    + (" | Brakuje: " + str(-reszta) + " zl" if not rozlicz0 and reszta < -0.005 else "")
                    + (" | Rozliczono ✓" if not rozlicz0 and abs(reszta) <= 0.005 else ""))
            else:
                flash_msg = "Zapisano: " + str(sprzed) + " szt. x " + str(cena) + " zl = " + str(kwota) + " zl"
                if rabat > 0: flash_msg += " (rabat: " + str(rabat) + " zl)"

            sid = db.execute("SELECT MAX(id) FROM sprzedaz_szczegol WHERE gospodarstwo_id=?", (g,)).fetchone()[0]
            db.commit(); db.close()
            # Jesli klient i typ "nastepnym_razem" lub ma saldo — pokaz rozliczenie
            if kid and typ in ("nastepnym_razem","gotowka","przelew"):
                flash(flash_msg)
                return redirect("/sprzedaz/rozlicz/" + str(sid))
            flash(flash_msg)
            return redirect(request.referrer or "/sprzedaz")

        # ── GET ───────────────────────────────────────────────────────────
        # Filtr dat - priorytet: query param > sesja > biezacy miesiac
        data_od = request.args.get("od", "")
        data_do = request.args.get("do", "")
        sesja_dat = session.get("zakres_dat", {})
        if not data_od:
            data_od = sesja_dat.get("od", date.today().replace(day=1).isoformat())
        if not data_do:
            data_do = sesja_dat.get("do", date.today().isoformat())

        db = get_db()

        # Stan magazynu
        from db import stan_magazynu as _sm
        stan = _sm(db, g)
        rez = db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as s FROM zamowienia"
            " WHERE gospodarstwo_id=? AND status IN ('nowe','potwierdzone')", (g,)).fetchone()["s"]
        dostepne = max(0, stan - int(rez))

        # Klienci i zamówienia (do formularza)
        klienci = db.execute(
            "SELECT id, nazwa, cena_indyw FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
        zamow_akt = db.execute(
            "SELECT z.id, z.data_dostawy, z.ilosc, k.nazwa as kn"
            " FROM zamowienia z LEFT JOIN klienci k ON z.klient_id=k.id"
            " WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')"
            " ORDER BY z.data_dostawy", (g,)).fetchall()
        cena_def = gs("cena_jajka", "1.20")

        historia = db.execute("""
            SELECT s.id, s.data, s.ilosc as jaja_sprzedane, s.cena_szt as cena_sprzedazy,
                   s.typ as typ_sprzedazy, s.uwagi, s.wartosc as kwota,
                   k.id as kid, k.nazwa as kn
            FROM sprzedaz_szczegol s
            LEFT JOIN klienci k ON s.klient_id = k.id
            WHERE s.gospodarstwo_id=? AND s.data >= ? AND s.data <= ?
            ORDER BY s.data DESC, s.id DESC""", (g, data_od, data_do)).fetchall()

        # Statystyki w zakresie - uwzgledniaj stare dane (produkcja) i nowe (sprzedaz_szczegol)
        # Dla dni bez sprzedaz_szczegol uzyj produkcja.jaja_sprzedane * cena_sprzedazy
        _sz = db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as szt, COALESCE(SUM(wartosc),0) as przychod"
            " FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND data>=? AND data<=?",
            (g, data_od, data_do)).fetchone()
        _sp = db.execute(
            "SELECT COALESCE(SUM(jaja_sprzedane),0) as szt,"
            " COALESCE(SUM(jaja_sprzedane*COALESCE(cena_sprzedazy,0)),0) as przychod"
            " FROM produkcja WHERE gospodarstwo_id=? AND data>=? AND data<=?"
            " AND NOT EXISTS (SELECT 1 FROM sprzedaz_szczegol ss"
            "   WHERE ss.gospodarstwo_id=produkcja.gospodarstwo_id AND ss.data=produkcja.data)",
            (g, data_od, data_do)).fetchone()
        stat_zakres = {
            "szt": int(_sz["szt"]) + int(_sp["szt"]),
            "przychod": float(_sz["przychod"]) + float(_sp["przychod"])
        }

        koszty_zakres = db.execute(
            "SELECT COALESCE(SUM(wartosc_total),0) as koszty"
            " FROM wydatki WHERE gospodarstwo_id=? AND data>=? AND data<=?",
            (g, data_od, data_do)).fetchone()

        # Statystyki bieżący miesiąc
        _sz2 = db.execute(
            "SELECT COALESCE(SUM(ilosc),0) as szt, COALESCE(SUM(wartosc),0) as kwota"
            " FROM sprzedaz_szczegol WHERE gospodarstwo_id=?"
            " AND strftime('%Y-%m',data)=strftime('%Y-%m','now')", (g,)).fetchone()
        _sp2 = db.execute(
            "SELECT COALESCE(SUM(jaja_sprzedane),0) as szt,"
            " COALESCE(SUM(jaja_sprzedane*COALESCE(cena_sprzedazy,0)),0) as kwota"
            " FROM produkcja WHERE gospodarstwo_id=?"
            " AND strftime('%Y-%m',data)=strftime('%Y-%m','now')"
            " AND NOT EXISTS (SELECT 1 FROM sprzedaz_szczegol ss"
            "   WHERE ss.gospodarstwo_id=produkcja.gospodarstwo_id AND ss.data=produkcja.data)",
            (g,)).fetchone()
        stat = {
            "szt": int(_sz2["szt"]) + int(_sp2["szt"]),
            "kwota": float(_sz2["kwota"]) + float(_sp2["kwota"])
        }

        # Klienci z saldami
        klienci_saldo = db.execute("""
            SELECT k.id, k.nazwa, k.telefon,
                   COALESCE(ks.saldo_pln, 0) as saldo,
                   COUNT(s.id) as transakcji,
                   COALESCE(SUM(s.wartosc), 0) as total,
                   MAX(s.data) as ostatnia
            FROM klienci k
            LEFT JOIN konta_saldo ks ON ks.klient_id=k.id
            LEFT JOIN sprzedaz_szczegol s ON s.klient_id=k.id AND s.gospodarstwo_id=?
            WHERE k.gospodarstwo_id=?
            GROUP BY k.id ORDER BY ABS(COALESCE(ks.saldo_pln,0)) DESC, k.nazwa""",
            (g, g)).fetchall()

        # Anonimowe sprzedaze (bez klienta)
        anon = db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(ilosc),0) as szt, COALESCE(SUM(wartosc),0) as total"
            " FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND klient_id IS NULL"
            " AND data>=? AND data<=?", (g, data_od, data_do)).fetchone()

        # Aktywne zamówienia do wyświetlenia
        zam_aktywne = db.execute(
            "SELECT z.*, k.nazwa as kn FROM zamowienia z"
            " LEFT JOIN klienci k ON z.klient_id=k.id"
            " WHERE z.gospodarstwo_id=? AND z.status IN ('nowe','potwierdzone')"
            " ORDER BY z.data_dostawy", (g,)).fetchall()

        db.close()

        TYP_ICO = {"gotowka": "💵", "przelew": "🏦", "z_salda": "📋", "nastepnym_razem": "⏳"}
        dzis = date.today().isoformat()
        suma_dlug = sum(max(0, float(k["saldo"] or 0)) for k in klienci_saldo)
        przychod  = round(float(stat_zakres["przychod"]), 2)
        koszty    = round(float(koszty_zakres["koszty"]), 2)
        zysk      = round(przychod - koszty, 2)

        # ─── 1. FORMULARZ SPRZEDAŻY ───────────────────────────────────────
        kl_opt = "<option value=''>— anonimowa —</option>" + "".join(
            "<option value='" + str(k["id"]) + "'>" + k["nazwa"] + "</option>"
            for k in klienci)
        zam_opt = "<option value=''>— bez zamówienia —</option>" + "".join(
            "<option value='" + str(z["id"]) + "'>"
            + z["data_dostawy"] + " · " + (z["kn"] or "?") + " · " + str(z["ilosc"]) + " szt."
            + "</option>"
            for z in zamow_akt)

        # Saldo klientow dla JS
        kl_saldo_map = {}
        for k in klienci_saldo:
            kl_saldo_map[str(k["id"])] = round(float(k["saldo"] or 0), 2)
        kl_ceny_map = {}
        for k in klienci:
            kl_ceny_map[str(k["id"])] = float(k["cena_indyw"] or 0)

        kl_opt = "<option value=''>— anonimowa —</option>"
        for k in klienci_saldo:
            sal = float(k["saldo"] or 0)
            sal_txt = ""
            if sal > 0.01: sal_txt = " [dług: " + str(round(sal,2)) + " zł]"
            elif sal < -0.01: sal_txt = " [nadpłata: " + str(round(-sal,2)) + " zł]"
            kl_opt += "<option value='" + str(k["id"]) + "' data-saldo='" + str(round(sal,2)) + "'>" + k["nazwa"] + sal_txt + "</option>"

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
            "<div><label>Klient</label><select name='klient_id' id='kl-sel'>" + kl_opt + "</select></div>"
            "<div><label>Typ płatności</label>"
            "<select name='typ_sprzedazy' id='typ-sel'>"
            "<option value='gotowka'>💵 Gotówka</option>"
            "<option value='przelew'>🏦 Przelew</option>"
            "<option value='nastepnym_razem'>⏳ Następnym razem (dług)</option>"
            "<option value='z_salda'>📋 Z salda</option>"
            "</select></div>"
            "</div>"
            "<div><label>Zamówienie</label>"
            "<select name='zamowienie_id'>" + zam_opt + "</select></div>"
            "<div><label>Uwagi</label>"
            "<input name='uwagi' placeholder='opcjonalnie'></div>"

            # Blok reszty/wplaty
            "<div id='blok-wplata' style='margin-top:10px;padding:12px;"
            "background:#f0f9f0;border-radius:10px;border:1px solid #c8e6c9;display:none'>"
            "<div style='display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end'>"
            "<div style='flex:1;min-width:100px'>"
            "<label style='font-size:12px;color:#888'>💵 Ile dał klient (zł)</label>"
            "<input id='wplata-inp' name='wplata_klienta' type='number' step='0.01'"
            " min='0' placeholder='0.00' oninput='obliczW()'"
            " style='font-size:20px;text-align:center'></div>"
            "<div style='flex:1;min-width:100px'>"
            "<label style='font-size:12px;color:#888'>🏷 Rabat (zł)</label>"
            "<input id='rabat-inp' name='rabat' type='number' step='0.01'"
            " min='0' value='0' oninput='oblicz()'"
            " style='font-size:16px;text-align:center'></div>"
            "</div>"
            "<div style='margin-top:8px'>"
            "<label style='display:flex;align-items:center;gap:8px;cursor:pointer;"
            "background:#e8f5e9;border-radius:8px;padding:6px 10px;font-size:13px'>"
            "<input type='checkbox' id='rozlicz0' name='rozlicz_do_zera' value='1'"
            " onchange='toggleRozlicz(this)' style='width:16px;height:16px'>"
            "<span><b>Rozlicz do zera</b> — wpisz dokładnie tyle ile potrzeba i wyzeruj saldo</span>"
            "</label>"
            "</div>"
            "<div id='wplata-info' style='font-size:14px;margin-top:8px;line-height:1.8'></div>"
            "</div>"

            "<button class='btn bg' style='width:100%;margin-top:12px;padding:12px;font-size:15px'>"
            "Zapisz sprzedaż</button>"
            "</form>"
            "<script>"
            "var _sal=" + str(kl_saldo_map).replace("'",'"') + ";"
            "var _ceny=" + str(kl_ceny_map).replace("'",'"') + ";"
            "function oblicz(){"
            "  var s=parseFloat(document.querySelector('[name=jaja_sprzedane]').value)||0;"
            "  var c=parseFloat(document.getElementById('cena').value)||0;"
            "  var r=parseFloat((document.getElementById('rabat-inp')||{value:'0'}).value)||0;"
            "  var w=Math.max(0,Math.round((s*c-r)*100)/100);"
            "  document.getElementById('wartosc').textContent=w.toFixed(2)+' zł';"
            "  obliczW();"
            "}"
            "function obliczW(){"
            "  var s=parseFloat(document.querySelector('[name=jaja_sprzedane]').value)||0;"
            "  var c=parseFloat(document.getElementById('cena').value)||0;"
            "  var r=parseFloat((document.getElementById('rabat-inp')||{value:'0'}).value)||0;"
            "  var wart=Math.max(0,Math.round((s*c-r)*100)/100);"
            "  var kid=(document.getElementById('kl-sel')||{value:''}).value;"
            "  var sal=kid?(_sal[kid]||0):0;"
            "  var dal=parseFloat((document.getElementById('wplata-inp')||{value:'0'}).value)||0;"
            "  var razem=Math.round((wart+sal)*100)/100;"
            "  var reszta=Math.round((dal-razem)*100)/100;"
            "  var info='Do zapłaty z tym razem: <b>'+razem.toFixed(2)+' zł</b>';"
            "  if(sal>0.01) info+=' <span style=\"color:#A32D2D\">(w tym dług: '+sal.toFixed(2)+' zł)</span>';"
            "  if(sal<-0.01) info+=' <span style=\"color:#3B6D11\">(nadpłata odliczona: '+(-sal).toFixed(2)+' zł)</span>';"
            "  if(dal>0.005){"
            "    if(reszta>0.005) info+='<br><b style=\"color:#3B6D11\">Reszta: '+reszta.toFixed(2)+' zł</b>';"
            "    else if(reszta<-0.005) info+='<br><b style=\"color:#A32D2D\">Brakuje: '+(-reszta).toFixed(2)+' zł</b>';"
            "    else info+='<br><b style=\"color:#3B6D11\">Kwota zgadza się ✓</b>';"
            "  }"
            "  document.getElementById('wplata-info').innerHTML=info;"
            "}"
            "document.querySelector('[name=jaja_sprzedane]').addEventListener('input',oblicz);"
            "document.getElementById('cena').addEventListener('input',oblicz);"
            "var ks=document.getElementById('kl-sel');"
            "if(ks){ks.addEventListener('change',function(){"
            "  var kid=this.value;"
            "  var bw=document.getElementById('blok-wplata');"
            "  bw.style.display=kid?'block':'none';"
            "  if(!kid){document.getElementById('wplata-info').innerHTML='';return;}"
            "  var ci=_ceny[kid]||0;"
            "  if(ci>0){document.getElementById('cena').value=ci.toFixed(2);}"
            "  else fetch('/api/klient-cena/'+kid).then(function(r){return r.json();})"
            "    .then(function(d){document.getElementById('cena').value=d.cena;oblicz();});"
            "  obliczW();"
            "});}"
"function toggleRozlicz(cb){"
"  var kid=(document.getElementById('kl-sel')||{value:''}).value;"
"  var sal=kid?(_sal[kid]||0):0;"
"  var r=parseFloat((document.getElementById('rabat-inp')||{value:'0'}).value)||0;"
"  var s=parseFloat(document.querySelector('[name=jaja_sprzedane]').value)||0;"
"  var c=parseFloat(document.getElementById('cena').value)||0;"
"  var wart=Math.max(0,Math.round((s*c-r)*100)/100);"
"  var razem=Math.round((wart+sal)*100)/100;"
"  var wi=document.getElementById('wplata-inp');"
"  if(cb.checked&&razem>0.005){wi.value=razem.toFixed(2);obliczW();}"
"  else if(cb.checked&&razem<=0.005){wi.value='0';obliczW();}"
"}"
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
            alarm = " ⚠️" if z["data_dostawy"] <= dzis else ""
            kwota_z = round(z["ilosc"] * (z["cena_za_szt"] or 0), 2)
            dni_do = (date.fromisoformat(z["data_dostawy"]) - date.today()).days
            dni_txt = ("dziś" if dni_do == 0 else
                       "jutro" if dni_do == 1 else
                       "za " + str(dni_do) + " dni" if dni_do > 0 else
                       str(-dni_do) + " dni temu")
            zam_html += (
                "<tr>"
                "<td style='white-space:nowrap'>" + z["data_dostawy"] + alarm + "</td>"
                "<td style='font-size:12px;color:#888'>" + dni_txt + "</td>"
                "<td style='font-weight:600'>" + str(z["ilosc"]) + " szt.</td>"
                "<td>" + (z["kn"] or "—") + "</td>"
                "<td>" + str(kwota_z) + " zł</td>"
                "<td class='nowrap'>"
                "<a href='/zamowienia/" + str(z["id"]) + "/status/dostarczone' class='btn bg bsm'>✓ Dostarcz</a> "
                "<a href='/zamowienia/" + str(z["id"]) + "/status/anulowane' class='btn br bsm'"
                " onclick=\"return confirm('Anulować?')\">✕</a>"
                "</td></tr>"
            )

        s_zamowienia = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
            "<b>🛒 Zamówienia</b>"
            "<a href='/zamowienia/dodaj' class='btn bp bsm'>+ Nowe</a>"
            "</div>"
            + (
                "<div style='overflow-x:auto'><table style='font-size:13px'><thead><tr>"
                "<th>Dostawa</th><th></th><th>Ilość</th><th>Klient</th><th>Wartość</th><th></th>"
                "</tr></thead><tbody>" + zam_html + "</tbody></table></div>"
                if zam_html else
                "<p style='color:#888;font-size:13px;text-align:center;padding:8px'>Brak aktywnych zamówień</p>"
            )
            + "</div>"
        )

        # ─── 4. FILTR + ZYSK/STRATA ───────────────────────────────────────
        zysk_kol = "#3B6D11" if zysk >= 0 else "#A32D2D"
        zysk_txt = ("+" if zysk >= 0 else "") + str(zysk) + " zł"

        s_filtr = (
            "<div class='card' style='margin-bottom:8px'>"
            "<form method='GET' action='/sprzedaz' style='display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end'>"
            "<div><label style='font-size:12px'>Od</label>"
            "<input name='od' type='date' value='" + data_od + "' style='font-size:13px'></div>"
            "<div><label style='font-size:12px'>Do</label>"
            "<input name='do' type='date' value='" + data_do + "' style='font-size:13px'></div>"
            "<button class='btn bo bsm'>Filtruj</button>"
            "<a href='/sprzedaz' class='btn bo bsm'>Reset</a>"
            "</form>"
            "<div style='display:flex;gap:16px;margin-top:10px;flex-wrap:wrap'>"
            "<div style='font-size:13px'>Sprzedano: <b style='color:#3B6D11'>" + str(int(stat_zakres["szt"])) + " szt.</b></div>"
            "<div style='font-size:13px'>Przychód: <b style='color:#3B6D11'>" + str(przychod) + " zł</b></div>"
            "<div style='font-size:13px'>Koszty: <b style='color:#A32D2D'>" + str(koszty) + " zł</b></div>"
            "<div style='font-size:13px;font-weight:600'>Zysk/strata: <b style='color:" + zysk_kol + "'>" + zysk_txt + "</b></div>"
            "</div>"
            "</div>"
        )

        # ─── 5. HISTORIA SPRZEDAŻY ────────────────────────────────────────
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
                "<td class='nowrap'>"
                "<a href='/sprzedaz/edytuj/" + str(r['id']) + "' class='btn bo bsm' style='font-size:11px'>Edytuj</a> "
                "<a href='/sprzedaz/usun/" + str(r['id']) + "' class='btn br bsm' style='font-size:11px' "
                "onclick='return confirm(\"Usunac?\")'>-</a>"
                "</td>"
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
            "<th>Klient</th><th>Płat.</th><th>Uwagi</th><th></th>"
            "</tr></thead><tbody>"
            + (hist_html or "<tr><td colspan=8 style='color:#888;text-align:center;padding:16px'>Brak sprzedaży w tym zakresie</td></tr>")
            + "</tbody></table></div></div>"
        )

        # ─── 6. KLIENCI ───────────────────────────────────────────────────
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
                "<button class='btn bg bsm' onclick='toggleWpl(" + str(kid_id) + ")'>+ Wpłata</button>"
                "<a href='/klienci/" + str(kid_id) + "/edytuj' class='btn bo bsm'>Edytuj</a>"
                "<a href='/klienci/" + str(kid_id) + "' class='btn bo bsm'>Szczegóły</a>"
                "</div></div>"
                + (
                    "<div style='margin-top:8px;padding-top:8px;border-top:1px solid #f0ede4'>"
                    + ost_html + "</div>"
                    if ost_html else
                    "<div style='font-size:11px;color:#ccc;margin-top:6px'>Brak transakcji w tym zakresie</div>"
                )
                + "<div id='wpl-" + str(kid_id) + "' style='display:none;margin-top:10px;"
                "padding:10px;background:#f0f9f0;border-radius:8px;border:1px solid #c8e6c9'>"
                "<form method='POST' action='/klienci/" + str(kid_id) + "/wplata'"
                " style='display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end'>"
                "<div><label style='font-size:11px'>Kwota wpłaty (zł)</label>"
                "<input name='kwota' type='number' step='0.01' min='0.01' required"
                " value='" + (str(round(saldo,2)) if saldo > 0.01 else "") + "'"
                " style='font-size:18px;text-align:center;width:120px'></div>"
                "<div style='flex:2;min-width:120px'><label style='font-size:11px'>Opis</label>"
                "<input name='opis' value='Wplata gotowkowa' style='font-size:13px'></div>"
                "<input type='hidden' name='rozlicz_do_zera' id='rz0-" + str(kid_id) + "' value=''>"
                "<div style='display:flex;flex-direction:column;gap:4px'>"
                "<button class='btn bg bsm'>Zapisz wpłatę</button>"
                "<button type='button' class='btn bo bsm' style='font-size:11px'"
                " onclick='document.getElementById(\"rz0-" + str(kid_id) + "\").value=\"1\";"
                "this.closest(\"form\").submit()'>Rozlicz do 0</button>"
                "</div></form>"
                "<button class='btn bo bsm' style='font-size:11px;margin-top:4px'"
                " onclick='document.getElementById(\"wpl-" + str(kid_id) + "\").style.display=\"none\"'>✕ Anuluj</button>"
                "</div>"
                + "</div>"
            )

        # Kafelek anonimowych
        anon_html = ""
        if anon and anon["cnt"] > 0:
            anon_html = (
                "<div class='card' style='border-left:4px solid #888;margin-bottom:8px'>"
                "<div style='font-weight:600;font-size:15px;color:#888'>— Anonimowa sprzedaż</div>"
                "<div style='font-size:13px;color:#888;margin-top:4px'>"
                + str(anon["cnt"]) + " transakcji · " + str(int(anon["szt"])) + " szt. · "
                + str(round(float(anon["total"]),2)) + " zł w wybranym zakresie"
                + "</div>"
                "<div style='font-size:12px;color:#aaa;margin-top:3px'>Brak przypisanego klienta</div>"
                "</div>"
            )

        _kl_count = len(klienci_saldo)
        _dlug_count = sum(1 for k in klienci_saldo if float(k["saldo"] or 0) > 0.01)
        _dlug_sum = round(sum(max(0, float(k["saldo"] or 0)) for k in klienci_saldo), 2)
        s_klienci = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center'>"
            "<div style='cursor:pointer' onclick='toggleKl()'>"
            "<b style='font-size:15px'>👥 Klienci (" + str(_kl_count) + ")</b>"
            + (" <span style='font-size:12px;color:#A32D2D;font-weight:600'>" + str(_dlug_count) + " z długiem · " + str(_dlug_sum) + " zł</span>" if _dlug_count > 0 else "")
            + " <span style='font-size:12px;color:#888' id='kl-arr'>▼</span>"
            "</div>"
            "<a href='/klienci/dodaj' class='btn bp bsm'>+ Nowy</a>"
            "</div>"
            "<div id='kl-body' style='display:none;margin-top:10px'>"
            + anon_html
            + (kl_html or
               "<p style='color:#888;text-align:center;padding:8px'>"
               "Brak klientów. <a href='/klienci/dodaj' style='color:#534AB7'>Dodaj →</a></p>")
            + "</div>"
            + "<script>"
            "function toggleKl(){"
            "  var b=document.getElementById('kl-body');"
            "  var a=document.getElementById('kl-arr');"
            "  var open=b.style.display==='none';"
            "  b.style.display=open?'block':'none';"
            "  a.textContent=open?'▲':'▼';"
            "}"
            "function toggleWpl(id){"
            "  var e=document.getElementById('wpl-'+id);"
            "  e.style.display=e.style.display==='none'?'block':'none';"
            "}"
            "</script>"
            "</div>"
        )

        straty_mies = 0; za0_mies = 0; pot_strata = 0.0; straty_hist = []
        try:
            straty_mies = int(db.execute(
                "SELECT COALESCE(SUM(ilosc),0) as s FROM jaja_straty WHERE gospodarstwo_id=? AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",
                (g,)).fetchone()["s"])
            za0_mies = int(db.execute(
                "SELECT COALESCE(SUM(ilosc),0) as s FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND cena_szt=0 AND strftime('%Y-%m',data)=strftime('%Y-%m','now')",
                (g,)).fetchone()["s"])
            cena_def_f = float(gs("cena_jajka","1.20"))
            pot_strata = round((straty_mies + za0_mies) * cena_def_f, 2)
            straty_hist = db.execute(
                "SELECT * FROM jaja_straty WHERE gospodarstwo_id=? ORDER BY data DESC, id DESC LIMIT 10",
                (g,)).fetchall()
        except Exception:
            pass
        sh_rows2 = ""
        for _r in straty_hist:
            sh_rows2 += (
                "<tr><td style='font-size:12px'>" + _r["data"] + "</td>"
                "<td style='color:#A32D2D;font-weight:700;text-align:center'>-" + str(_r["ilosc"]) + "</td>"
                "<td>" + {"stluczone":"Stluczki","zepsute":"Zepsute"}.get(_r["powod"],"Inne") + "</td>"
                "<td style='font-size:11px;color:#888'>" + (_r["uwagi"] or "") + "</td>"
                "<td style='color:#A32D2D'>" + str(round(_r["ilosc"]*cena_def_f,2)) + " zl</td>"
                "</tr>"
            )
        _dzis2 = date.today().isoformat()
        s_straty = (
            "<div class='card' style='margin-bottom:12px'>"
            "<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>"
            "<b>Straty i gratis</b>"
            "<a href='/magazyn-jaj' class='btn bo bsm' style='font-size:11px'>Pelny magazyn</a>"
            "</div>"
            "<div style='display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px'>"
            "<span style='font-size:13px'>Straty mies.: <b style='color:#A32D2D'>" + str(straty_mies) + " szt.</b></span>"
            "<span style='font-size:13px'>Za darmo: <b style='color:#888'>" + str(za0_mies) + " szt.</b></span>"
            "<span style='font-size:13px'>Pot. strata: <b style='color:#A32D2D'>" + str(pot_strata) + " zl</b></span>"
            "</div>"
            "<form method='POST' action='/produkcja' style='display:flex;gap:8px;flex-wrap:wrap;align-items:flex-end'>"
            "<input type='hidden' name='action' value='strata'>"
            "<div><label style='font-size:11px'>Ilosc strat (szt.)</label>"
            "<input name='strata_ile' type='number' min='1' placeholder='np. 3' style='width:80px;font-size:14px;text-align:center'></div>"
            "<div><label style='font-size:11px'>Powod</label>"
            "<select name='strata_powod' style='font-size:13px'>"
            "<option value='stluczone'>Stluczki</option>"
            "<option value='zepsute'>Zepsute</option>"
            "<option value='zgubione'>Inne</option>"
            "</select></div>"
            "<input name='strata_data' type='date' value='" + _dzis2 + "' style='font-size:13px'>"
            "<button class='btn br bsm'>Zapisz strate</button>"
            "</form>"
            + ("<div style='overflow-x:auto;margin-top:8px'>"
               "<table style='font-size:12px'><thead><tr>"
               "<th>Data</th><th>Szt.</th><th>Powod</th><th>Uwagi</th><th>Pot.strata</th></tr></thead>"
               "<tbody>" + sh_rows2 + "</tbody></table></div>" if straty_hist else "")
            + "</div>"
        )
        html = "<h1>Sprzedaz</h1>"

        # ── KAFELKI STATYSTYK ─────────────────────────────────────────
        html += (
            "<style>.sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-bottom:12px}"
            "@media(max-width:480px){.sg{grid-template-columns:repeat(2,1fr)}}</style>"
            "<div class='sg'>"
            "<div class='card stat'><div class='v' style='color:#3B6D11'>" + str(int(stat_zakres["szt"])) + "</div><div class='l'>Sprzedano</div><div class='s'>szt. w zakresie</div></div>"
            "<div class='card stat'><div class='v' style='color:#3B6D11'>" + str(round(przychod,2)) + " zl</div><div class='l'>Przychod</div><div class='s'>w zakresie</div></div>"
            "<div class='card stat'><div class='v' style='color:" + zysk_kol + "'>" + zysk_txt + "</div><div class='l'>Zysk/strata</div><div class='s'>przychod-koszty</div></div>"
            "<div class='card stat'><div class='v' style='color:" + c_stan + "'>" + str(stan) + "</div><div class='l'>W magazynie</div><div class='s'>dostepne: " + str(dostepne) + "</div></div>"
            + ("<div class='card stat'><div class='v' style='color:#A32D2D'>" + str(round(suma_dlug,2)) + " zl</div><div class='l'>Lacznie dlugow</div><div class='s'>klientow</div></div>" if suma_dlug > 0.01 else "")
            + "</div>"
        )

        # ── GŁÓWNY LAYOUT: formularz + magazyn ───────────────────────
        html += s_formularz
        html += s_magazyn

        # ── ZAMÓWIENIA ────────────────────────────────────────────────
        html += s_zamowienia

        # ── STRATY ────────────────────────────────────────────────────
        html += s_straty

        # ── FILTR + HISTORIA ──────────────────────────────────────────
        html += s_filtr
        html += s_historia

        # ── KLIENCI (zwijane, na dole) ────────────────────────────────
        html += s_klienci

        return R(html, "zam")

    # ── Edycja transakcji sprzedaży (po id) ─────────────────────────────
    @app.route("/sprzedaz/rozlicz/<int:sid>", methods=["GET","POST"])
    @farm_required
    def sprzedaz_rozlicz(sid):
        """Ekran rozliczenia długu po sprzedaży."""
        g = gid(); db = get_db()
        sp = db.execute(
            "SELECT ss.*, k.nazwa as kn, k.cena_indyw FROM sprzedaz_szczegol ss"
            " LEFT JOIN klienci k ON k.id=ss.klient_id"
            " WHERE ss.id=? AND ss.gospodarstwo_id=?", (sid, g)).fetchone()
        if not sp or not sp["klient_id"]:
            db.close(); return redirect("/sprzedaz")

        kid = sp["klient_id"]
        ks = db.execute("SELECT saldo_pln FROM konta_saldo WHERE klient_id=?", (kid,)).fetchone()
        saldo = float(ks["saldo_pln"] if ks else 0)
        kwota_sp = float(sp["wartosc"] or 0)

        if request.method == "POST":
            action = request.form.get("action","")
            wplata = float(request.form.get("kwota", 0) or 0)
            rozlicz0 = request.form.get("rozlicz0") == "1"
            if action in ("wplata","rozlicz0"):
                from datetime import datetime
                if rozlicz0: wplata = max(0, saldo); nowe_sal = 0.0
                else: nowe_sal = round(saldo - wplata, 2)
                if ks:
                    db.execute("UPDATE konta_saldo SET saldo_pln=?,ostatnia_zmiana=datetime('now') WHERE klient_id=?", (nowe_sal, kid))
                else:
                    db.execute("INSERT INTO konta_saldo(klient_id,saldo_pln,ostatnia_zmiana) VALUES(?,?,datetime('now'))", (kid, nowe_sal))
                db.execute(
                    "INSERT INTO konta_transakcje(gospodarstwo_id,klient_id,data,typ,kwota,opis,saldo_po) VALUES(?,?,datetime('now'),?,?,?,?)",
                    (g, kid, "wplata", -wplata, "Wpłata przy sprzedaży #"+str(sid), nowe_sal))
                db.commit(); db.close()
                flash("Wpłata " + str(round(wplata,2)) + " zł. Nowe saldo: " + str(nowe_sal) + " zł")
            else:
                db.close()
            return redirect(request.referrer.replace("/rozlicz/"+str(sid),"") if request.referrer else "/sprzedaz")

        db.close()
        # Kolor salda
        s_kol = "#A32D2D" if saldo > 0.01 else "#3B6D11" if saldo < -0.01 else "#888"
        s_txt = ("Dług: " + str(round(saldo,2)) + " zł") if saldo > 0.01 else ("Nadpłata: " + str(round(-saldo,2)) + " zł") if saldo < -0.01 else "Rozliczony"
        html = (
            "<h1>Rozliczenie — " + (sp["kn"] or "klient") + "</h1>"
            "<div class='card' style='max-width:480px;margin:0 auto'>"
            "<div style='display:flex;justify-content:space-between;margin-bottom:12px'>"
            "<div><div style='font-size:13px;color:#888'>Sprzedaż #" + str(sid) + "</div>"
            "<div style='font-size:18px;font-weight:700'>" + str(sp["ilosc"]) + " szt. × " + str(sp["cena_szt"]) + " zł</div>"
            "<div style='font-size:15px;color:#3B6D11;font-weight:600'>= " + str(round(kwota_sp,2)) + " zł</div></div>"
            "<div style='text-align:right'>"
            "<div style='font-size:12px;color:#888'>Saldo klienta</div>"
            "<div style='font-size:22px;font-weight:700;color:" + s_kol + "'>" + s_txt + "</div>"
            "</div></div>"
            "<hr style='border:none;border-top:1px solid #f0ede4;margin:10px 0'>"
            "<form method='POST'>"
            "<label style='font-size:12px;color:#888'>Kwota wpłaty (zł)</label>"
            "<input name='kwota' type='number' step='0.01' min='0' value='" + (str(round(saldo,2)) if saldo > 0.01 else "") + "'"
            " style='font-size:22px;text-align:center;font-weight:700;margin-bottom:8px'>"
            "<div style='display:flex;gap:8px;flex-direction:column'>"
            "<button name='action' value='wplata' class='btn bg' style='padding:12px;font-size:15px'>✓ Zapisz wpłatę</button>"
            + ("<button name='action' value='rozlicz0' class='btn bp' style='padding:10px' formnovalidate>"
               "<input type='hidden' name='rozlicz0' value='1'>Rozlicz do zera (" + str(round(saldo,2)) + " zł)</button>" if saldo > 0.01 else "")
            + "<a href='/sprzedaz' class='btn bo' style='padding:10px;text-align:center'>Pomiń → wróć do sprzedaży</a>"
            "</div></form></div>"
        )
        return R(html, "zam")


    @app.route("/sprzedaz/edytuj/<int:sid>", methods=["GET", "POST"])
    @farm_required
    def sprzedaz_edytuj(sid):
        g = gid(); db = get_db()
        r = db.execute(
            "SELECT s.*, k.nazwa as kn FROM sprzedaz_szczegol s"
            " LEFT JOIN klienci k ON s.klient_id=k.id"
            " WHERE s.id=? AND s.gospodarstwo_id=?", (sid, g)).fetchone()
        if not r: db.close(); flash("Nie znaleziono."); return redirect("/sprzedaz")

        klienci = db.execute(
            "SELECT id, nazwa, cena_indyw FROM klienci WHERE gospodarstwo_id=? ORDER BY nazwa", (g,)).fetchall()
        zamow = db.execute(
            "SELECT z.id, z.data_dostawy, z.ilosc, k.nazwa as kn FROM zamowienia z"
            " LEFT JOIN klienci k ON z.klient_id=k.id"
            " WHERE z.gospodarstwo_id=? AND (z.status IN ('nowe','potwierdzone') OR z.id=?)"
            " ORDER BY z.data_dostawy", (g, r["zamowienie_id"] or 0)).fetchall()

        if request.method == "POST":
            sprzed = int(request.form.get("jaja_sprzedane", 0) or 0)
            cena   = float(request.form.get("cena_sprzedazy", 0) or 0)
            kid    = request.form.get("klient_id") or None
            zid    = request.form.get("zamowienie_id") or None
            typ    = request.form.get("typ_sprzedazy", "gotowka")
            uwagi  = request.form.get("uwagi", "")
            kwota  = round(sprzed * cena, 2)
            db.execute(
                "UPDATE sprzedaz_szczegol SET ilosc=?,cena_szt=?,wartosc=?,"
                "klient_id=?,zamowienie_id=?,typ=?,uwagi=? WHERE id=? AND gospodarstwo_id=?",
                (sprzed, cena, kwota, kid, zid, typ, uwagi, sid, g))
            # Aktualizuj sumy w produkcja
            d = r["data"]
            db.execute(
                "UPDATE produkcja SET"
                " jaja_sprzedane=(SELECT COALESCE(SUM(ilosc),0) FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND data=?)"
                " WHERE gospodarstwo_id=? AND data=?", (g, d, g, d))
            db.commit(); db.close()
            flash("Zaktualizowano sprzedaz.")
            return redirect("/sprzedaz")

        db.close()
        kl_opt = "<option value=''>— anonimowa —</option>" + "".join(
            "<option value='" + str(k["id"]) + "'"
            + (" selected" if r["klient_id"] == k["id"] else "") + ">"
            + k["nazwa"] + "</option>" for k in klienci)
        zam_opt = "<option value=''>— bez zamowienia —</option>" + "".join(
            "<option value='" + str(z["id"]) + "'"
            + (" selected" if r["zamowienie_id"] == z["id"] else "") + ">"
            + z["data_dostawy"] + " - " + (z["kn"] or "?") + " - " + str(z["ilosc"]) + " szt."
            + "</option>" for z in zamow)
        TYP = [("gotowka","Gotowka"),("przelew","Przelew"),
               ("nastepnym_razem","Nastepnym razem"),("z_salda","Z salda")]
        typ_opt = "".join(
            "<option value='" + v + "'" + (" selected" if r["typ"]==v else "") + ">" + l + "</option>"
            for v,l in TYP)

        html = (
            "<h1>Edycja sprzedazy — " + r["data"] + "</h1>"
            "<div class='card'><form method='POST'>"
            "<div class='g3'>"
            "<div><label>Sprzedane (szt)</label>"
            "<input name='jaja_sprzedane' type='number' min='0' required"
            " value='" + str(r["ilosc"]) + "'"
            " style='font-size:20px;text-align:center'></div>"
            "<div><label>Cena/szt (zl)</label>"
            "<input name='cena_sprzedazy' type='number' step='0.01' min='0'"
            " value='" + str(r["cena_szt"] or "") + "'"
            " style='font-size:20px;text-align:center'></div>"
            "<div><label>Data</label>"
            "<input type='text' value='" + r["data"] + "' disabled style='background:#f5f5f0'></div>"
            "</div>"
            "<div class='g2'>"
            "<div><label>Klient</label><select name='klient_id'>" + kl_opt + "</select></div>"
            "<div><label>Typ platnosci</label><select name='typ_sprzedazy'>" + typ_opt + "</select></div>"
            "</div>"
            "<div><label>Zamowienie</label><select name='zamowienie_id'>" + zam_opt + "</select></div>"
            "<div><label>Uwagi</label><input name='uwagi' value='" + (r["uwagi"] or "") + "'></div>"
            "<br><button class='btn bp' style='margin-top:12px'>Zapisz</button>"
            "<a href='/sprzedaz' class='btn bo' style='margin-left:8px'>Anuluj</a>"
            "</form></div>"
        )
        return R(html, "zam")

    @app.route("/sprzedaz/usun/<int:sid>")
    @farm_required
    def sprzedaz_usun(sid):
        g = gid(); db = get_db()
        row = db.execute("SELECT data FROM sprzedaz_szczegol WHERE id=? AND gospodarstwo_id=?", (sid,g)).fetchone()
        if row:
            db.execute("DELETE FROM sprzedaz_szczegol WHERE id=? AND gospodarstwo_id=?", (sid, g))
            d = row["data"]
            # Aktualizuj sumy
            db.execute(
                "UPDATE produkcja SET"
                " jaja_sprzedane=(SELECT COALESCE(SUM(ilosc),0) FROM sprzedaz_szczegol WHERE gospodarstwo_id=? AND data=?)"
                " WHERE gospodarstwo_id=? AND data=?", (g, d, g, d))
            db.commit()
        db.close()
        flash("Transakcja usunieta.")
        return redirect("/sprzedaz")

    @app.route("/api/klient-cena/<int:kid>")
    @farm_required
    def api_klient_cena(kid):
        from flask import jsonify
        g = gid(); db = get_db()
        k = db.execute("SELECT cena_indyw FROM klienci WHERE id=? AND gospodarstwo_id=?", (kid,g)).fetchone()
        db.close()
        cena_i = float((k["cena_indyw"] or 0) if k else 0)
        cena_def = float(gs("cena_jajka","1.20"))
        return jsonify({"cena": cena_i if cena_i > 0 else cena_def, "indyw": cena_i > 0})

    return app
