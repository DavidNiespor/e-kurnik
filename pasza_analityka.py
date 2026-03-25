# -*- coding: utf-8 -*-
"""
Analityka paszowa:
- Oblicza wartości odżywcze receptury na podstawie bazy składników
- Porównuje z normami dla niosek
- Generuje rekomendacje co zmienić aby poprawić nieśność
- Koreluje zmiany receptury ze zmianami nieśności w historii
"""
import json
from datetime import datetime, date, timedelta
from db import get_db
from baza_skladnikow import NORMY_NIOSEK

def oblicz_recepture(receptura_id):
    """
    Oblicz wartości odżywcze receptury na podstawie składników z bazy.
    Zwraca dict z wynikami i porównaniem do norm.
    """
    db = get_db()
    skladniki_rec = db.execute("""
        SELECT rs.procent, sb.nazwa, sb.bialko_pct, sb.energia_me,
               sb.tluszcz_pct, sb.wlokno_pct, sb.wapn_g_kg,
               sb.fosfor_g_kg, sb.lizyna_g_kg, sb.metionina_g_kg,
               sb.cena_pln_t, sb.kategoria
        FROM receptura_skladnik rs
        JOIN stan_magazynu sm ON rs.magazyn_id = sm.id
        LEFT JOIN skladniki_baza sb ON LOWER(TRIM(sb.nazwa)) = LOWER(TRIM(sm.nazwa))
        WHERE rs.receptura_id = ?
    """, (receptura_id,)).fetchall()

    if not skladniki_rec:
        db.close()
        return None

    wyniki = {
        "bialko_pct":    0.0,
        "energia_me":    0.0,
        "tluszcz_pct":   0.0,
        "wlokno_pct":    0.0,
        "wapn_g_kg":     0.0,
        "fosfor_g_kg":   0.0,
        "lizyna_g_kg":   0.0,
        "metionina_g_kg":0.0,
        "koszt_pln_t":   0.0,
        "skladniki":     [],
        "suma_procent":  0.0,
    }

    for s in skladniki_rec:
        pct = float(s["procent"] or 0)
        wyniki["suma_procent"] += pct
        wyniki["bialko_pct"]     += (s["bialko_pct"]     or 0) * pct
        wyniki["energia_me"]     += (s["energia_me"]      or 0) * pct
        wyniki["tluszcz_pct"]    += (s["tluszcz_pct"]     or 0) * pct
        wyniki["wlokno_pct"]     += (s["wlokno_pct"]      or 0) * pct
        wyniki["wapn_g_kg"]      += (s["wapn_g_kg"]       or 0) * pct * 10  # g/kg paszy
        wyniki["fosfor_g_kg"]    += (s["fosfor_g_kg"]      or 0) * pct * 10
        wyniki["lizyna_g_kg"]    += (s["lizyna_g_kg"]      or 0) * pct * 10
        wyniki["metionina_g_kg"] += (s["metionina_g_kg"]   or 0) * pct * 10
        wyniki["koszt_pln_t"]    += (s["cena_pln_t"]       or 0) * pct
        wyniki["skladniki"].append({
            "nazwa":    s["nazwa"],
            "procent":  pct,
            "kategoria":s["kategoria"] or "nieznana",
        })

    db.close()

    # Porównanie z normami
    N = NORMY_NIOSEK
    wyniki["ocena"] = {}
    def _ocen(val, mn, mx=None):
        if val < mn: return "nisko"
        if mx and val > mx: return "wysoko"
        return "ok"

    wyniki["ocena"]["bialko"]    = _ocen(wyniki["bialko_pct"], N["bialko_min"], N["bialko_max"])
    wyniki["ocena"]["energia"]   = _ocen(wyniki["energia_me"], N["energia_me_min"], N["energia_me_max"])
    wyniki["ocena"]["wapn"]      = _ocen(wyniki["wapn_g_kg"], N["wapn_min"], N["wapn_max"])
    wyniki["ocena"]["fosfor"]    = _ocen(wyniki["fosfor_g_kg"], N["fosfor_min"], N["fosfor_max"])
    wyniki["ocena"]["lizyna"]    = _ocen(wyniki["lizyna_g_kg"], N["lizyna_min"])
    wyniki["ocena"]["metionina"] = _ocen(wyniki["metionina_g_kg"], N["metionina_min"])
    wyniki["ocena"]["tluszcz"]   = _ocen(wyniki["tluszcz_pct"], N["tluszcz_min"], N["tluszcz_max"])
    wyniki["ocena"]["wlokno"]    = _ocen(wyniki["wlokno_pct"], 0, N["wlokno_max"])

    return wyniki

def generuj_rekomendacje(wyniki):
    """Generuje listę konkretnych rekomendacji na podstawie analizy."""
    if not wyniki:
        return ["Brak danych do analizy — upewnij się że składniki receptury są w bazie składników."]

    N = NORMY_NIOSEK
    rec = []
    oc  = wyniki.get("ocena", {})

    if oc.get("bialko") == "nisko":
        diff = N["bialko_min"] - wyniki["bialko_pct"]
        rec.append({
            "priorytet": "wysoki",
            "parametr":  "Białko",
            "problem":   f"Za niskie: {wyniki['bialko_pct']:.1f}% (min {N['bialko_min']}%)",
            "rozwiazanie": f"Dodaj +{diff*2:.1f}% grochu, łubinu lub soi. Białko bezpośrednio wpływa na nieśność i masę jaja.",
            "oczekiwany_efekt": "Wzrost nieśności o 5-10% w ciągu 2-3 tygodni"
        })
    elif oc.get("bialko") == "wysoko":
        rec.append({
            "priorytet": "sredni",
            "parametr":  "Białko",
            "problem":   f"Za wysokie: {wyniki['bialko_pct']:.1f}% (max {N['bialko_max']}%)",
            "rozwiazanie": "Zmniejsz udział grochu/soi na rzecz kukurydzy. Nadmiar białka obciąża nerki.",
            "oczekiwany_efekt": "Lepsza konwersja paszy, mniejsze koszty"
        })

    if oc.get("wapn") == "nisko":
        diff = N["wapn_min"] - wyniki["wapn_g_kg"]
        rec.append({
            "priorytet": "krytyczny",
            "parametr":  "Wapń",
            "problem":   f"Krytycznie niski: {wyniki['wapn_g_kg']:.1f} g/kg (min {N['wapn_min']} g/kg)",
            "rozwiazanie": f"Zwiększ kredę pastewną grubą o +{diff/37:.2f}% (gruba frakcja dla skorupek, drobna wchłanialna). Niedobór wapnia = miękkie skorupki, pękające jaja.",
            "oczekiwany_efekt": "Poprawa jakości skorupek w 5-7 dni"
        })

    if oc.get("energia") == "nisko":
        rec.append({
            "priorytet": "wysoki",
            "parametr":  "Energia",
            "problem":   f"Za niska: {wyniki['energia_me']:.0f} kcal/kg (min {N['energia_me_min']} kcal/kg)",
            "rozwiazanie": "Zwiększ udział kukurydzy lub dodaj 0.5-1% oleju roślinnego. Niedobór energii = kury jedzą więcej ale mniej się niosą.",
            "oczekiwany_efekt": "Lepsza nieśność, kury nie szukają dodatkowego pokarmu"
        })

    if oc.get("lizyna") == "nisko":
        rec.append({
            "priorytet": "sredni",
            "parametr":  "Lizyna",
            "problem":   f"Za mała: {wyniki['lizyna_g_kg']:.1f} g/kg (min {N['lizyna_min']} g/kg)",
            "rozwiazanie": "Dodaj drożdże browarniane (+0.2%) lub zwiększ sję grochu. Lizyna to aminokwas limitujący produkcję jaj.",
            "oczekiwany_efekt": "Lepsza masa jaja i nieśność"
        })

    if oc.get("metionina") == "nisko":
        rec.append({
            "priorytet": "sredni",
            "parametr":  "Metionina",
            "problem":   f"Za mała: {wyniki['metionina_g_kg']:.1f} g/kg (min {N['metionina_min']} g/kg)",
            "rozwiazanie": "Zwiększ słonecznik (+0.5%) — naturalne źródło metioniny. Metionina = jakość piór i jaj.",
            "oczekiwany_efekt": "Lepszy stan piór, jakość jaj"
        })

    if oc.get("wlokno") == "wysoko":
        rec.append({
            "priorytet": "niski",
            "parametr":  "Włókno",
            "problem":   f"Za dużo: {wyniki['wlokno_pct']:.1f}% (max {N['wlokno_max']}%)",
            "rozwiazanie": "Zmniejsz owies i lucernę. Nadmiar włókna obniża strawność paszy.",
            "oczekiwany_efekt": "Lepsza konwersja paszy"
        })

    if not rec:
        rec.append({
            "priorytet": "brak",
            "parametr":  "Ogólna ocena",
            "problem":   "Receptura w normach",
            "rozwiazanie": "Receptura wygląda dobrze! Możesz eksperymentować z naturalnymi dodatkami (czosnek, kurkuma, oregano) dla zdrowia i aromatu.",
            "oczekiwany_efekt": "Utrzymanie dobrej nieśności"
        })

    return rec

def korelacja_pasza_niesnosc(gospodarstwo_id, dni_lookback=90):
    """
    Analizuje historię mieszań i nieśności.
    Szuka korelacji między zmianami receptury a zmianą nieśności.
    """
    db = get_db()
    kur = db.execute(
        "SELECT COALESCE(SUM(liczba),0) as s FROM stado WHERE gospodarstwo_id=? AND aktywne=1 AND gatunek='nioski'",
        (gospodarstwo_id,)
    ).fetchone()["s"] or 50

    prod = db.execute("""
        SELECT data, jaja_zebrane,
               ROUND(CAST(jaja_zebrane AS REAL)/? * 100, 1) as niesnosc
        FROM produkcja
        WHERE gospodarstwo_id=? AND data >= date('now',?)
        ORDER BY data
    """, (kur, gospodarstwo_id, f"-{dni_lookback} days")).fetchall()

    mieszania = db.execute("""
        SELECT m.data, r.nazwa as receptura
        FROM mieszania m
        LEFT JOIN receptura r ON m.receptura_id = r.id
        WHERE m.gospodarstwo_id=? AND m.data >= date('now',?)
        ORDER BY m.data
    """, (gospodarstwo_id, f"-{dni_lookback} days")).fetchall()

    db.close()

    if len(prod) < 7:
        return {"brak_danych": True, "min_dni": 7}

    # Znajdź punkty zmiany receptury i nieśność przed/po
    zdarzenia = []
    prod_list = [dict(p) for p in prod]

    for m in mieszania:
        data_miesz = str(m["data"])[:10]
        # Nieśność 7 dni przed
        przed = [p["niesnosc"] for p in prod_list if p["data"] < data_miesz][-7:]
        # Nieśność 7-14 dni po (receptura wpływa z opóźnieniem)
        po    = [p["niesnosc"] for p in prod_list if p["data"] > data_miesz][:14]

        if len(przed) >= 3 and len(po) >= 7:
            avg_przed = sum(przed) / len(przed)
            avg_po    = sum(po)    / len(po)
            delta     = round(avg_po - avg_przed, 1)
            zdarzenia.append({
                "data":       data_miesz,
                "receptura":  m["receptura"] or "nieznana",
                "niesnosc_przed": round(avg_przed, 1),
                "niesnosc_po":    round(avg_po, 1),
                "delta":          delta,
                "ocena": "poprawa" if delta > 2 else "pogorszenie" if delta < -2 else "neutralna"
            })

    # Ogólny trend
    if len(prod_list) >= 14:
        pierwsza_polowa = prod_list[:len(prod_list)//2]
        druga_polowa    = prod_list[len(prod_list)//2:]
        avg1 = sum(p["niesnosc"] for p in pierwsza_polowa) / len(pierwsza_polowa)
        avg2 = sum(p["niesnosc"] for p in druga_polowa)    / len(druga_polowa)
        trend_delta = round(avg2 - avg1, 1)
        trend = "rosnący" if trend_delta > 3 else "malejący" if trend_delta < -3 else "stabilny"
    else:
        trend = "niewystarczająco danych"
        trend_delta = 0

    return {
        "brak_danych":    False,
        "zdarzenia":      zdarzenia,
        "trend":          trend,
        "trend_delta":    trend_delta,
        "dni_analizy":    len(prod_list),
        "avg_niesnosc":   round(sum(p["niesnosc"] for p in prod_list)/len(prod_list),1) if prod_list else 0,
    }

def porownaj_receptury(r1_id, r2_id):
    """Porównaj dwie receptury pod kątem wartości odżywczych i kosztu."""
    w1 = oblicz_recepture(r1_id)
    w2 = oblicz_recepture(r2_id)
    if not w1 or not w2:
        return None
    pola = ["bialko_pct","energia_me","wapn_g_kg","fosfor_g_kg",
            "lizyna_g_kg","metionina_g_kg","tluszcz_pct","wlokno_pct","koszt_pln_t"]
    diff = {}
    for p in pola:
        v1 = w1.get(p, 0)
        v2 = w2.get(p, 0)
        diff[p] = round(v2 - v1, 3)
    return {"receptura1": w1, "receptura2": w2, "roznica": diff}
