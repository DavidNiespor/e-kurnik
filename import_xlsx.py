# -*- coding: utf-8 -*-
"""
Import danych historycznych z Chicken.xlsx
Importuje: produkcja jaj (JAJKA), koszty (Koszta)
Używa: pandas (pip install pandas openpyxl)
"""
import os
from datetime import datetime, date

def import_chicken_xlsx(filepath, gospodarstwo_id, db):
    """
    Importuje dane z Chicken.xlsx do bazy.
    Zwraca dict z liczbą zaimportowanych rekordów.
    """
    try:
        import pandas as pd
    except ImportError:
        return {"error": "Brak pandas — zainstaluj: pip install pandas openpyxl --break-system-packages"}

    if not os.path.exists(filepath):
        return {"error": f"Plik nie istnieje: {filepath}"}

    xl     = pd.read_excel(filepath, sheet_name=None)
    wyniki = {"produkcja": 0, "koszty": 0, "bledy": []}

    # ── Arkusz JAJKA — produkcja ─────────────────────────────────────────────
    if "JAJKA" in xl:
        df = xl["JAJKA"]
        # Kolumny: Data, Ilość Niosek, Ilość Kwok, Ilość Jajek, Niośność,
        #          Sprzedane Jajka po 1,2, Sprzedane Jajka po 1,0,
        #          Suma Sprzedanych, Rozdane Jajka, Zarobek
        df = df.dropna(subset=["Data"])
        for _, row in df.iterrows():
            try:
                data = pd.to_datetime(row["Data"]).strftime("%Y-%m-%d")
                jaja = int(row.get("Ilość Jajek", 0) or 0)
                sprzedane_12 = float(row.get("Sprzedane Jajka po 1,2", 0) or 0)
                sprzedane_10 = float(row.get("Sprzedane Jajka po 1,0", 0) or 0)
                sprzedane = int(sprzedane_12 + sprzedane_10)
                zarobek = float(row.get("Zarobek", 0) or 0)
                cena = round(zarobek / sprzedane, 2) if sprzedane > 0 else 0

                existing = db.execute(
                    "SELECT id FROM produkcja WHERE gospodarstwo_id=? AND data=?",
                    (gospodarstwo_id, data)
                ).fetchone()

                if not existing:
                    db.execute("""INSERT OR IGNORE INTO produkcja
                        (gospodarstwo_id,data,jaja_zebrane,jaja_sprzedane,cena_sprzedazy,pasza_wydana_kg,uwagi)
                        VALUES(?,?,?,?,?,0,'import z Chicken.xlsx')""",
                        (gospodarstwo_id, data, jaja, sprzedane, cena))
                    wyniki["produkcja"] += 1
            except Exception as e:
                wyniki["bledy"].append(f"JAJKA: {str(e)[:80]}")

    # ── Arkusz Koszta ─────────────────────────────────────────────────────────
    if "Koszta" in xl:
        df = xl["Koszta"]
        # Struktura: LP, Rok, Miesiąc, Zwierzęta, Witaminy, Kreda Pastewna...
        # Pomijamy nagłówki i sumy
        try:
            df_clean = df.iloc[3:].copy()  # od wiersza 3 (po nagłówkach)
            df_clean.columns = ["lp","rok","miesiac","zwierzeta","witaminy",
                                "kreda","kukurydza","pszenica","owies",
                                "jeczmien","sorgo","curry","kurkuma"]
            for _, row in df_clean.iterrows():
                try:
                    if pd.isna(row["miesiac"]) or not str(row["miesiac"]).strip():
                        continue
                    rok = int(row["rok"]) if not pd.isna(row["rok"]) else 2024

                    mies_map = {
                        "styczeń":1,"luty":2,"marzec":3,"kwiecień":4,"maj":5,"czerwiec":6,
                        "lipiec":7,"sierpień":8,"śierpień":8,"wrzesień":9,
                        "październik":10,"listopad":11,"grudzień":12,
                        "czewiec":6
                    }
                    m = str(row["miesiac"]).lower().strip()
                    miesiac_nr = mies_map.get(m, 1)
                    data_wyd   = f"{rok}-{miesiac_nr:02d}-01"

                    kategorie = {
                        "zwierzeta": ("Weterynarz", row.get("zwierzeta")),
                        "witaminy":  ("Witaminy/suplementy", row.get("witaminy")),
                        "kreda":     ("Zboże/pasza", row.get("kreda")),
                        "kukurydza": ("Zboże/pasza", row.get("kukurydza")),
                        "pszenica":  ("Zboże/pasza", row.get("pszenica")),
                        "owies":     ("Zboże/pasza", row.get("owies")),
                        "jeczmien":  ("Zboże/pasza", row.get("jeczmien")),
                    }

                    for klucz, (kat, wartosc) in kategorie.items():
                        if not pd.isna(wartosc) and float(wartosc or 0) > 0:
                            db.execute("""INSERT INTO wydatki
                                (gospodarstwo_id,data,kategoria,nazwa,ilosc,jednostka,cena_jednostkowa,wartosc_total,uwagi)
                                VALUES(?,?,?,?,1,'import',?,?,'import z Chicken.xlsx')""",
                                (gospodarstwo_id, data_wyd, kat, klucz,
                                 float(wartosc), float(wartosc)))
                            wyniki["koszty"] += 1
                except Exception as e:
                    wyniki["bledy"].append(f"Koszta: {str(e)[:80]}")
        except Exception as e:
            wyniki["bledy"].append(f"Koszta parse: {str(e)[:80]}")

    db.commit()
    return wyniki


def import_receptury_xlsx(filepath, gospodarstwo_id, db):
    """
    Importuje receptury z arkuszy Paszav2/v3 do bazy systemu.
    """
    try:
        import pandas as pd
    except ImportError:
        return {"error": "Brak pandas"}

    xl = pd.read_excel(filepath, sheet_name=None)
    wyniki = {"receptury": 0, "bledy": []}

    arkusze_receptur = {
        "Paszav2":     "Z Soją (30 kur)",
        "Paszav3":     "Bez Soi (50 kur)",
        "Pasza Zimowa":"Zimowa",
    }

    for ark, nazwa_rec in arkusze_receptur.items():
        if ark not in xl:
            continue
        df = xl[ark]
        try:
            # Nagłówki: Składnik, KG, %, KG/MSC, KG/ROK, Do zamówienia, CENA PLN/T
            df = df.dropna(subset=[df.columns[0]])
            df = df[df.iloc[:,0].apply(lambda x: isinstance(x,str) and
                    x.strip() not in ["Składnik","Liczba Kur","KG/KURA",""] and
                    not str(x).startswith("NaN"))]

            # Sprawdź czy receptura już istnieje
            existing = db.execute(
                "SELECT id FROM receptura WHERE gospodarstwo_id=? AND nazwa=?",
                (gospodarstwo_id, nazwa_rec)
            ).fetchone()

            if existing:
                rid = existing["id"]
            else:
                rid = db.execute(
                    "INSERT INTO receptura(gospodarstwo_id,nazwa,sezon,aktywna) VALUES(?,?,?,0)",
                    (gospodarstwo_id, nazwa_rec, "caly_rok")
                ).lastrowid

            # Dodaj składniki do magazynu i receptury
            col_kg = df.columns[2]   # KG na 30kg partię
            col_pct= df.columns[3]   # %

            for _, row in df.iterrows():
                try:
                    nazwa_skl = str(row.iloc[0]).strip()
                    kg_val    = float(row[col_kg] or 0)
                    pct_val   = float(row[col_pct] or 0)

                    if kg_val <= 0 or pct_val <= 0:
                        continue

                    # Dodaj do magazynu jeśli nie istnieje
                    mag = db.execute(
                        "SELECT id FROM stan_magazynu WHERE gospodarstwo_id=? AND nazwa=?",
                        (gospodarstwo_id, nazwa_skl)
                    ).fetchone()

                    if not mag:
                        mag_id = db.execute(
                            "INSERT INTO stan_magazynu(gospodarstwo_id,kategoria,nazwa,jednostka,stan,cena_aktualna) VALUES(?,?,?,?,0,0)",
                            (gospodarstwo_id, "Zboże/pasza", nazwa_skl, "kg")
                        ).lastrowid
                    else:
                        mag_id = mag["id"]

                    # Dodaj do receptury
                    existing_skl = db.execute(
                        "SELECT id FROM receptura_skladnik WHERE receptura_id=? AND magazyn_id=?",
                        (rid, mag_id)
                    ).fetchone()

                    if not existing_skl:
                        db.execute(
                            "INSERT INTO receptura_skladnik(receptura_id,magazyn_id,procent) VALUES(?,?,?)",
                            (rid, mag_id, pct_val)
                        )
                except Exception as e:
                    wyniki["bledy"].append(f"{ark}: {str(e)[:60]}")

            wyniki["receptury"] += 1
        except Exception as e:
            wyniki["bledy"].append(f"{ark} parse: {str(e)[:80]}")

    db.commit()
    return wyniki
