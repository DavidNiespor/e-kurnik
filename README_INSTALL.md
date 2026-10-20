# Ferma Jaj — instalacja (RPi i zwykły PC/VPS)

Jeden obraz `ghcr.io/davidniespor/e-kurnik:latest` zawiera warianty **amd64** i **arm64**.
Docker sam wybiera właściwy — nic nie zmieniasz w kodzie.

## PC / VPS (x86_64)
Portainer → Stacks → Add stack → wklej `docker-compose.yml`.
Zmienne: `SECRET_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`.

## Raspberry Pi (arm64) z GPIO
To samo, ale w sekcji `ferma:` dopisz:
    devices:
      - /dev/gpiochip0:/dev/gpiochip0
(CLI: `docker compose -f docker-compose.yml -f docker-compose.rpi.yml up -d`)

## Przeniesienie danych między maszynami
1. Stara instancja: menu Ustawienia → **Import / Export bazy** → "Pobierz bazę".
2. Nowa instancja (po pierwszym starcie): ta sama strona → "Wgraj kopię bazy".
   Poprzednia baza trafia do archiwum na serwerze i można ją przywrócić jednym kliknięciem.

## GitHub Actions
`deploy.yml` buduje `linux/amd64,linux/arm64`. Pierwszy build jest dłuższy (emulacja arm64),
kolejne korzystają z cache.
