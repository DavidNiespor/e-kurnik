# -*- coding: utf-8 -*-
"""backup_views.py — backup Google Drive + edycja paszy"""
import os
import json
import shutil
import tempfile
from datetime import datetime


def register_backup(app):
    from flask import request, redirect, flash, session
    from db import get_db, get_setting, save_setting
    from auth import farm_required
    from app import R

    def gid(): return session.get("farm_id")
    def gs(k, d=""): return get_setting(k, d, gid())

    @app.route("/pasza/zuzycie", methods=["GET", "POST"])
    @farm_required
    def pasza_zuzycie():
        g = gid()
        db = get_db()
        if request.method == "POST":
            d = request.form.get("data", "")
            pf = float(request.form.get("pasza_wydana_kg", 0) or 0)
            if d:
                ex = db.execute(
                    "SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?", (g, d)).fetchone()
                if ex:
                    db.execute("UPDATE produkcja SET pasza_wydana_kg=? WHERE id=?", (pf, ex["id"]))
                else:
                    db.execute(
                        "INSERT INTO produkcja(gospodarstwo_id,data,jaja_zebrane,"
                        "jaja_sprzedane,pasza_wydana_kg) VALUES(?,?,0,0,?)", (g, d, pf))
                db.commit()
                flash("Pasza: " + d + " = " + str(pf) + " kg")
            db.close()
            return redirect("/pasza/zuzycie")

        rows = db.execute(
            "SELECT data, jaja_zebrane, pasza_wydana_kg, "
            "CASE WHEN pasza_wydana_kg>0 AND jaja_zebrane>0 "
            "THEN ROUND(pasza_wydana_kg/jaja_zebrane*1000,1) ELSE NULL END as gnj "
            "FROM produkcja WHERE gospodarstwo_id=? ORDER BY data DESC LIMIT 60", (g,)).fetchall()
        avg = (db.execute(
            "SELECT AVG(pasza_wydana_kg) as a FROM produkcja "
            "WHERE gospodarstwo_id=? AND pasza_wydana_kg>0 "
            "AND data>=date('now','-30 days')", (g,)).fetchone()["a"] or 0)
        db.close()

        rh = ""
        for r in rows:
            gnj = r["gnj"]
            p = str(round(r["pasza_wydana_kg"] or 0, 2))
            kol = ("#888" if not r["pasza_wydana_kg"]
                   else "#A32D2D" if (gnj or 0) > 120
                   else "#BA7517" if (gnj or 0) > 90
                   else "#3B6D11")
            rh += (
                "<tr>"
                "<td style='font-size:13px'>" + r["data"] + "</td>"
                "<td style='text-align:center'>" + str(r["jaja_zebrane"]) + "</td>"
                "<td style='font-weight:600;text-align:center'>" + p + " kg</td>"
                "<td style='text-align:center;color:" + kol + ";font-size:12px'>"
                + (str(gnj) + " g/j" if gnj else "") + "</td>"
                "<td><form method='POST' style='display:flex;gap:4px'>"
                "<input type='hidden' name='data' value='" + r["data"] + "'>"
                "<input name='pasza_wydana_kg' type='number' step='0.1' min='0' value='" + p + "'"
                " style='width:72px;padding:4px;font-size:13px;text-align:center'>"
                "<button class='btn bp bsm'>OK</button>"
                "</form></td></tr>"
            )

        html = (
            "<h1>Edycja zuzycia paszy</h1>"
            "<div class='g2' style='margin-bottom:12px'>"
            "<div class='card stat'>"
            "<div class='v'>" + str(round(avg, 2)) + " kg</div>"
            "<div class='l'>Srednia dzienna (30 dni)</div></div>"
            "<div class='card stat'>"
            "<div class='v'>" + str(round(avg / 15 * 1000, 0) if avg else 0) + " g</div>"
            "<div class='l'>Na nioske dziennie</div></div></div>"
            "<div class='card' style='overflow-x:auto'>"
            "<table style='font-size:13px'><thead><tr>"
            "<th>Data</th><th>Zebrane</th><th>Pasza</th><th>g/jajko</th><th>Edytuj</th>"
            "</tr></thead><tbody>"
            + (rh or "<tr><td colspan=5 style='color:#888;text-align:center;padding:16px'>"
               "Brak danych</td></tr>")
            + "</tbody></table></div>"
            "<a href='/pasza' class='btn bo bsm' style='margin-top:8px'>Pasza</a>"
        )
        return R(html, "pasza")

    @app.route("/backup/gdrive", methods=["GET", "POST"])
    @farm_required
    def backup_gdrive():
        g = gid()
        if request.method == "POST":
            action = request.form.get("action", "")
            if action == "save_config":
                save_setting("gdrive_folder_id",
                             request.form.get("folder_id", "").strip(), g)
                save_setting("gdrive_credentials",
                             request.form.get("creds", "").strip(), g)
                flash("Konfiguracja zapisana.")
                return redirect("/backup/gdrive")
            if action == "backup_now":
                res = _do_backup(g)
                flash("Backup OK: " + res["filename"]
                      if res["ok"] else "Blad: " + res["error"])
                return redirect("/backup/gdrive")

        folder_id = gs("gdrive_folder_id", "")
        has_creds = bool(gs("gdrive_credentials", ""))
        last_bkp = gs("gdrive_last_backup", "")

        ok_cfg = folder_id and has_creds
        status = (
            "<div class='al alok'>Skonfigurowano. Ostatni backup: "
            + (last_bkp or "brak") + "</div>"
            if ok_cfg else
            "<div class='al alw'>Backup nie skonfigurowany.</div>"
        )
        inst = (
            "<details style='margin-bottom:12px'>"
            "<summary style='cursor:pointer;color:#534AB7;font-size:13px'>"
            "Jak skonfigurowac? (kliknij)</summary>"
            "<div class='card' style='margin-top:6px;font-size:13px;line-height:1.9'>"
            "<ol style='padding-left:18px'>"
            "<li>console.cloud.google.com — nowy projekt, wlacz <b>Google Drive API</b></li>"
            "<li>IAM &amp; Admin → Service Accounts → Utwórz → Pobierz klucz JSON</li>"
            "<li>Na Google Drive utwórz folder → Udostepnij emailem Service Account</li>"
            "<li>Skopiuj ID folderu z URL (czesc po /folders/)</li>"
            "<li>Na serwerze RPi: "
            "<code>pip install google-auth google-api-python-client</code></li>"
            "</ol></div></details>"
        )
        bkp_cls = "bp" if ok_cfg else "bo"
        bkp_dis = "" if ok_cfg else " disabled"
        creds_txt = "*** zapisany ***" if has_creds else ""

        html = (
            "<h1>Backup Google Drive</h1>"
            + status + inst
            + "<div class='card'><b>Konfiguracja</b>"
            "<form method='POST' style='margin-top:10px'>"
            "<input type='hidden' name='action' value='save_config'>"
            "<label>Folder ID</label>"
            "<input name='folder_id' value='" + folder_id + "'"
            " placeholder='ID z URL folderu na Drive'>"
            "<label>Service Account JSON</label>"
            "<textarea name='creds' rows='5'"
            " placeholder='{\"type\":\"service_account\",...}'"
            " style='font-family:monospace;font-size:11px'>" + creds_txt + "</textarea>"
            "<button class='btn bp bsm' style='margin-top:8px'>Zapisz</button>"
            "</form></div>"
            "<div class='card'><b>Backup teraz</b>"
            "<p style='font-size:13px;color:#888;margin:6px 0'>"
            "Tworzy kopie ferma.db z data i godzina w nazwie pliku.</p>"
            "<form method='POST'>"
            "<input type='hidden' name='action' value='backup_now'>"
            "<button class='btn " + bkp_cls + "'" + bkp_dis + ">"
            "Backup teraz</button></form></div>"
            "<a href='/ustawienia/farma' class='btn bo bsm' style='margin-top:8px'>"
            "Ustawienia</a>"
        )
        return R(html, "ust")

    return app


def _do_backup(g):
    from db import get_setting, save_setting, DB as DB_PATH
    try:
        folder_id = get_setting("gdrive_folder_id", "", g)
        creds_json = get_setting("gdrive_credentials", "", g)
        if not folder_id or not creds_json:
            return {"ok": False, "error": "Brak konfiguracji"}
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaFileUpload
        except ImportError:
            return {"ok": False,
                    "error": "Brak bibliotek: pip install google-auth google-api-python-client"}

        creds_data = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_data, scopes=["https://www.googleapis.com/auth/drive.file"])
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        now = datetime.now()
        filename = "ferma_backup_" + now.strftime("%Y%m%d_%H%M%S") + ".db"
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(DB_PATH, tmp_path)
        size_kb = round(os.path.getsize(tmp_path) / 1024, 1)

        meta = {"name": filename, "parents": [folder_id]}
        media = MediaFileUpload(tmp_path, mimetype="application/octet-stream")
        service.files().create(body=meta, media_body=media, fields="id").execute()
        os.unlink(tmp_path)

        save_setting("gdrive_last_backup", now.strftime("%Y-%m-%d %H:%M"), g)
        return {"ok": True, "filename": filename + " (" + str(size_kb) + " KB)"}

    except Exception as e:
        return {"ok": False, "error": str(e)}
