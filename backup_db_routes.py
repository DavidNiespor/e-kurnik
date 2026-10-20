# backup_db_routes.py — register_db_backup(app)
import os, shutil, sqlite3
from datetime import datetime


def register_db_backup(app):
    from flask import request, redirect, flash, send_file
    from auth import farm_required
    from app import R
    from db import get_db

    def gid():
        from flask import session
        return session.get("gid")

    def gs(k, d=""):
        from db import get_setting
        db = get_db()
        v = get_setting(db, k, gid())
        db.close()
        return v or d

    @app.route("/backup/db")
    @farm_required
    def backup_db_page():
        db_dir  = os.environ.get("FERMA_DATA_DIR", "/data")
        db_path = os.path.join(db_dir, "ferma.db")
        db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.exists(db_path) else 0

        # Lista archiwów (backupów przed importem)
        archives = sorted(
            [f for f in os.listdir(db_dir) if f.startswith("ferma_before_import_") and f.endswith(".db")],
            reverse=True
        )[:5] if os.path.isdir(db_dir) else []

        arch_html = ""
        if archives:
            arch_html = (
                "<div class='card' style='margin-top:12px'>"
                "<b>Archiwum (przed importem)</b>"
                "<div style='margin-top:8px;font-size:13px'>"
            )
            for a in archives:
                ts = a.replace("ferma_before_import_", "").replace(".db", "")
                arch_html += (
                    "<div style='display:flex;justify-content:space-between;padding:5px 0;"
                    "border-bottom:1px solid #f0ede4'>"
                    "<span style='color:#888'>" + ts + "</span>"
                    "<a href='/backup/db/restore/" + a + "' class='btn bo bsm'"
                    " onclick=\"return confirm('Przywrócić tę kopię? Aktualna baza zostanie zarchiwizowana.')\""
                    ">Przywróć</a>"
                    "</div>"
                )
            arch_html += "</div></div>"

        html = (
            "<h1>Import / Export bazy</h1>"
            "<div class='g2' style='gap:12px'>"

            "<div class='card'>"
            "<b>Pobierz kopię bazy</b>"
            "<p style='font-size:13px;color:#888;margin:8px 0'>"
            "Pobiera aktualny plik <code>ferma.db</code> jako backup. "
            "Rozmiar: <b>" + str(db_size_kb) + " KB</b></p>"
            "<a href='/backup/db/export' class='btn bp' style='display:inline-block'>"
            "Pobierz bazę (.db)</a>"
            "</div>"

            "<div class='card'>"
            "<b>Wgraj kopię bazy</b>"
            "<p style='font-size:13px;color:#888;margin:8px 0'>"
            "Zastępuje aktualną bazę wgranym plikiem. "
            "<b style='color:#A32D2D'>Obecna baza zostaje automatycznie zarchiwizowana.</b></p>"
            "<form method='POST' action='/backup/db/import' enctype='multipart/form-data'>"
            "<input type='file' name='db_file' accept='.db' required style='font-size:13px;margin-bottom:10px'>"
            "<br>"
            "<button class='btn br' onclick=\"return confirm('Zastąpić aktualną bazę? Kopia zostanie zachowana.')\">"
            "Wgraj i zastąp bazę</button>"
            "</form>"
            "</div>"

            "</div>"
            + arch_html +
            "<div style='margin-top:12px;display:flex;gap:8px'>"
            "<a href='/backup/gdrive' class='btn bo bsm'>Backup Google Drive</a>"
            "<a href='/ustawienia' class='btn bo bsm'>Ustawienia</a>"
            "</div>"
        )
        return R(html, "ust")

    @app.route("/backup/db/export")
    @farm_required
    def backup_db_export():
        import tempfile
        db_dir  = os.environ.get("FERMA_DATA_DIR", "/data")
        db_path = os.path.join(db_dir, "ferma.db")
        if not os.path.exists(db_path):
            flash("Nie znaleziono pliku bazy.")
            return redirect("/backup/db")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Spojna kopia (uwzglednia zapisy z pliku WAL), nie surowe kopiowanie pliku
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        src_con = sqlite3.connect(db_path)
        dst_con = sqlite3.connect(tmp.name)
        try:
            src_con.backup(dst_con)
        finally:
            dst_con.close(); src_con.close()
        resp = send_file(
            tmp.name,
            as_attachment=True,
            download_name="ferma_backup_" + ts + ".db",
            mimetype="application/octet-stream"
        )
        resp.call_on_close(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
        return resp

    @app.route("/backup/db/import", methods=["POST"])
    @farm_required
    def backup_db_import():
        import tempfile
        db_dir  = os.environ.get("FERMA_DATA_DIR", "/data")
        db_path = os.path.join(db_dir, "ferma.db")
        f_up    = request.files.get("db_file")

        if not f_up or not f_up.filename.lower().endswith(".db"):
            flash("Wgraj plik .db")
            return redirect("/backup/db")

        # 1. zapisz do pliku tymczasowego i zwaliduj ZANIM dotkniemy dzialajacej bazy
        tmp = tempfile.NamedTemporaryFile(suffix=".db", dir=db_dir, delete=False)
        tmp.close()
        f_up.save(tmp.name)
        try:
            con = sqlite3.connect(tmp.name)
            ok = con.execute("PRAGMA integrity_check").fetchone()[0]
            tables = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            con.close()
            if ok != "ok":
                raise ValueError("plik bazy jest uszkodzony")
            if "produkcja" not in tables or "gospodarstwa" not in tables:
                raise ValueError("to nie jest baza Ferma Jaj")
        except Exception as e:
            os.remove(tmp.name)
            flash("BŁĄD: " + str(e) + " — aktualna baza nie została zmieniona.")
            return redirect("/backup/db")

        # 2. archiwizuj obecna baze (spojna kopia)
        if os.path.exists(db_path):
            ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak = os.path.join(db_dir, "ferma_before_import_" + ts + ".db")
            s = sqlite3.connect(db_path); d = sqlite3.connect(bak)
            try: s.backup(d)
            finally: d.close(); s.close()

        # 3. podmien plik i usun resztki WAL starej bazy
        os.replace(tmp.name, db_path)
        os.chmod(db_path, 0o644)
        for ext in ("-wal", "-shm"):
            p = db_path + ext
            if os.path.exists(p):
                os.remove(p)

        flash("Baza wgrana — " + str(len(tables)) + " tabel. "
              "Poprzednia wersja zapisana w archiwum poniżej.")
        return redirect("/backup/db")

    @app.route("/backup/db/restore/<filename>")
    @farm_required
    def backup_db_restore(filename):
        db_dir  = os.environ.get("FERMA_DATA_DIR", "/data")
        db_path = os.path.join(db_dir, "ferma.db")
        src     = os.path.join(db_dir, filename)

        # tylko pliki archiwum z katalogu danych
        if not (filename.startswith("ferma_before_import_") and filename.endswith(".db")):
            flash("Niedozwolony plik.")
            return redirect("/backup/db")
        if not os.path.exists(src):
            flash("Plik nie istnieje.")
            return redirect("/backup/db")

        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = os.path.join(db_dir, "ferma_before_import_" + ts + ".db")
        if os.path.exists(db_path):
            s = sqlite3.connect(db_path); d = sqlite3.connect(bak)
            try: s.backup(d)
            finally: d.close(); s.close()
        shutil.copy2(src, db_path)
        for ext in ("-wal", "-shm"):
            p = db_path + ext
            if os.path.exists(p):
                os.remove(p)
        flash("Baza przywrócona z archiwum " + filename)
        return redirect("/backup/db")

