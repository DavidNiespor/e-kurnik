# -*- coding: utf-8 -*-
"""
sterowanie_views.py — widok /sterowanie z sekcjami Lokalnie/Supla/Ręczne/Harmonogramy
Importowany przez routes.py
"""

KI = {
    "swiatlo": "💡", "brama": "🚪", "grzanie": "🔥",
    "wentylacja": "💨", "pojenie": "💧", "inne": "⚡", "": "⚡"
}


def _row(k, harm_cnt):
    on     = bool(k["stan"])
    opis   = k["k_opis"] or k["opis"] or k["kanal"]
    ico    = KI.get(k["kategoria"] or "", "⚡")
    hn     = harm_cnt.get((k["urzadzenie_id"], k["kanal"]), 0)
    ns     = "false" if on else "true"
    dot    = "🟢" if (k["status"] or "") == "online" else "⚪"
    href   = f"/sterowanie/kanal/{k['urzadzenie_id']}/{k['kanal']}"
    cmd    = f"tR({k['urzadzenie_id']},'{k['kanal']}',{ns})"
    harm_s = f" ⏰×{hn}" if hn else ""
    badge  = "b-green" if on else "b-gray"
    btn_kl = "br" if on else "bg"
    btn_l  = "Wyłącz" if on else "Włącz"
    return (
        f"<tr>"
        f"<td style='font-size:18px;width:30px;padding:6px 4px'>{ico}</td>"
        f"<td style='padding:6px 8px'>"
        f"<b style='font-size:13px'>{opis}</b><br>"
        f"<span style='font-size:11px;color:#888'>{dot} {k['urz_nazwa']} "
        f"<code>{k['kanal']}</code>{harm_s}</span></td>"
        f"<td style='padding:6px 8px'>"
        f"<span class='badge {badge}'>{'ON' if on else 'OFF'}</span></td>"
        f"<td class='nowrap' style='padding:6px 4px'>"
        f"<button class='btn {btn_kl} bsm' onclick=\"{cmd}\">{btn_l}</button> "
        f"<a href='{href}' class='btn bo bsm'>⚙</a>"
        f"</td></tr>"
    )


def _card(title, sub, items, harm_cnt, btn=""):
    rows = "".join(_row(k, harm_cnt) for k in items)
    if not rows:
        rows = (
            "<tr><td colspan=4 style='color:#aaa;text-align:center;"
            "padding:14px;font-size:13px'>Brak kanałów w tym trybie</td></tr>"
        )
    return (
        "<div class='card' style='margin-bottom:10px'>"
        "<div style='display:flex;align-items:flex-start;"
        "justify-content:space-between;margin-bottom:8px;gap:8px;flex-wrap:wrap'>"
        f"<div><b>{title}</b>"
        + (f"<div style='font-size:12px;color:#888;margin-top:2px'>{sub}</div>" if sub else "")
        + f"</div>{btn}</div>"
        "<div style='overflow-x:auto'><table style='font-size:13px'>"
        "<thead><tr><th></th><th>Kanał / opis</th><th>Stan</th><th>Akcja</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div></div>"
    )


def render_sterowanie(g, kanaly, harm_cnt, supla_ok, _TRYBY, R):
    lok  = [k for k in kanaly if (k["tryb"] or "") in ("rpi_gpio", "rpi_siec", "esphome")]
    supl = [k for k in kanaly if (k["tryb"] or "") in ("supla", "supla+rpi")]
    rucz = [k for k in kanaly if not (k["tryb"] or "").strip() or k["tryb"] == "reczny"]
    pozo = [k for k in kanaly if k not in lok + supl + rucz]

    supla_kol = "bo" if supla_ok else "bp"
    supla_lbl = "Panel Supla" if supla_ok else "Połącz Supla"
    supla_sub = "✓ Połączono z Supla Cloud" if supla_ok else "⚠ Brak połączenia — skonfiguruj OAuth"
    supla_btn = f"<a href='/supla' class='btn {supla_kol} bsm'>{supla_lbl}</a>"

    tryby_html = "".join(
        f"<div style='padding:3px 0;font-size:13px'>"
        f"<span style='font-size:15px'>{t[3]}</span> <b>{t[1]}</b> — "
        f"<span style='color:#5f5e5a'>{t[2]}</span></div>"
        for t in _TRYBY
    )

    html = (
        "<h1>Sterowanie</h1>"
        "<div style='display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap'>"
        "<a href='/gpio' class='btn bp bsm'>⚡ Przekaźniki</a>"
        "<a href='/harmonogramy' class='btn bo bsm'>⏰ Harmonogramy</a>"
        "<a href='/urzadzenia/dodaj' class='btn bo bsm'>+ Urządzenie</a>"
        "</div>"

        + _card(
            "🔌 Lokalnie — RPi / ESPHome",
            "Działa offline: RPi GPIO bezpośrednie, RPi/ESP32 po sieci LAN, ESPHome REST",
            lok, harm_cnt,
            "<a href='/urzadzenia' class='btn bo bsm'>Urządzenia</a>"
        )

        + _card(
            "☁️ Supla Cloud",
            supla_sub,
            supl, harm_cnt,
            supla_btn
        )

        + _card(
            "🖱️ Ręczne / nieskonfigurowane",
            "Tylko sterowanie z panelu — kliknij ⚙ aby przypisać tryb",
            rucz + pozo, harm_cnt
        )

        + "<div class='card'>"
          "<div style='display:flex;justify-content:space-between;align-items:center'>"
          "<div><b>⏰ Harmonogramy automatyczne</b>"
          "<div style='font-size:12px;color:#888;margin-top:2px'>"
          "Wschód/zachód słońca, stałe godziny, dni tygodnia — bez internetu"
          "</div></div>"
          "<a href='/harmonogramy' class='btn bp bsm'>Zarządzaj</a>"
          "</div></div>"

        "<script>"
        "function tR(d,c,s){"
        "fetch('/sterowanie/cmd',{method:'POST',"
        "headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({urzadzenie_id:d,kanal:c,stan:s})})"
        ".then(r=>r.json())"
        ".then(function(j){if(j.ok)location.reload();"
        "else alert('Błąd sterowania: '+(j.msg||'spróbuj ponownie'));});"
        "}"
        "</script>"

        "<details style='margin-top:8px'>"
        "<summary style='cursor:pointer;font-size:13px;color:#534AB7;padding:6px 0'>"
        "Opis trybów →</summary>"
        "<div class='card' style='margin-top:6px'>"
        + tryby_html +
        "<p style='font-size:12px;color:#888;margin-top:8px'>"
        "Kliknij ⚙ przy kanale aby zmienić tryb.</p>"
        "</div></details>"
    )
    return R(html, "gpio")
