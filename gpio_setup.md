# GPIO w Docker na RPi — konfiguracja

## Opcja 1: pigpio daemon (ZALECANA)

pigpio działa jako daemon na HOŚCIE RPi, kontener łączy się przez TCP localhost:8888.
Nie wymaga --privileged ani dodatkowych uprawnień w kontenerze.

### Na hoście RPi (raz, przy starcie):
```bash
sudo apt install pigpio python3-pigpio
sudo pigpiod            # uruchom daemon
sudo systemctl enable pigpiod  # autostart przy boot
sudo systemctl start pigpiod
```

### W requirements.txt dodaj:
```
pigpio
```

### W docker-compose.yml NIE trzeba nic zmieniać — pigpio łączy się przez localhost:8888.

---

## Opcja 2: lgpio (alternatywa)

### W docker-compose.yml dodaj:
```yaml
services:
  ekurnik:
    devices:
      - /dev/gpiochip0:/dev/gpiochip0
```

### W requirements.txt:
```
lgpio
```

---

## Jak działa teraz app:

Kolejność prób (automatycznie):
1. pigpio przez TCP → localhost:8888
2. lgpio → /dev/gpiochip0
3. RPi.GPIO (tylko poza Docker)

Jeśli żadne nie działa → czytelny komunikat z instrukcją.
