[English](../OPERATIONS.md) | **Polski**

Wersja: 3.6.21 (`abuseipdb_report.py`)

# Eksploatacja

## Harmonogram

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

Jedno uruchomienie na dobę. Nie uruchamiaj narzędzia ręcznie tego samego dnia bez powodu: wrapper pomija drugi
przebieg w ciągu 20 h, a `--force` świadomie omija tę blokadę. Przed zmianą crontaba zachowaj kopię
(`crontab -l > ~/crontab.bak-DATA`) i instaluj nową wersję z pliku, nigdy przez potok, który może być pusty.

## Monitoring

Wrapper sam alarmuje przy awariach, ale nie zaalarmuje, gdy w ogóle przestanie się uruchamiać (martwy cron,
usunięty skrypt, wisząca blokada). Pokryj to zewnętrznym monitorem (poza tym repozytorium), który co godzinę
ostrzega, gdy `.state/abuseipdb_last_ok` jest starszy niż 36 h. Nazwa tego pliku jest stabilnym interfejsem dla takiego
monitora.

## Alerty

| Tytuł ntfy | Znaczenie | Co zrobić |
|---|---|---|
| `abuseipdb: reporting ERROR` | awaria generatora, walidacji lub wysyłki; treść podaje powód; znacznik się nie przesunął | przeczytaj końcówkę `abuseipdb_cron.log`; następny przebieg nadrobi sam |
| `abuseipdb: corrupted watermark` | `.state/abuseipdb_last_ok` ma nieprawidłową zawartość; użyto domyślnego okna 24 h | sprawdź plik, po następnym sukcesie zostanie nadpisany |
| `abuseipdb: gap in reports` | ostatni sukces starszy niż 48 h; okno ucięto do 48 h | ustal, czemu przebiegi zawodziły; starsze alerty przepadły |
| `abuseipdb: rejected reports` | AbuseIPDB odrzuciło część wierszy | zobacz linie `rejected:` w logu; znacznik się przesunął |
| `abuseipdb: data cut off` | limit uciął dane (`--limit` alertów czytanych z `cscli` albo limit 10 000 wierszy / 8 MB pliku CSV); okno i tak zamknięto, więc ucięte alerty nie zostaną zgłoszone | zwiększ limit alertów przez `ALERT_LIMIT` w linii crontaba (`30 5 * * * ALERT_LIMIT=20000 /sciezka/do/abuseipdb_send.sh >> ...`; domyślnie 5 000) albo zbadaj falę alertów; linia w logu zaczyna się od `[TRUNCATED]` |
| `abuseipdb: count mismatch` | zapisane + odrzucone różni się od wysłanych | sprawdź odpowiedź API w logu |
| ostrzeżenie z twojego zewnętrznego monitora | brak udanego przebiegu od ponad 36 h albo brak/uszkodzenie skryptu lub znacznika | sprawdź `crontab -l`, `systemctl status cron`, log |

## Lista kontrolna pierwszego przebiegu (po świeżej instalacji lub przeprowadzce)

1. `./abuseipdb_send.sh --version` i `python3 abuseipdb_report.py --version`.
   Utwórz konfigurację: `cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf`, `chmod 600 ~/.secrets/abuseipdb.conf`,
   potem ustaw klucz API, temat ntfy i `OWN_NAME_MARKERS` (przy pustych znacznikach lub przy wartościach przykładowych przebieg na żywo jest odmawiany).
2. `./abuseipdb_send.sh --dry-run`: oczekuj `window: (...)`, linii `generator:` oraz `DRY-RUN: would send N reports`.
3. `crontab -l` pokazuje nową ścieżkę zarówno w poleceniu, jak i w przekierowaniu logu.
4. Po pierwszym zaplanowanym przebiegu w `abuseipdb_cron.log`: `OK: sent N, saved N, rejected 0` i `watermark updated`.
5. `cat .state/abuseipdb_last_ok` zawiera świeży epoch; twój zewnętrzny monitor, jeśli go masz, pokazuje OK.

## Codzienne kontrole

```bash
tail -n 30 abuseipdb_cron.log     # ostatni przebieg, linie z tagiem [send]
cat .state/abuseipdb_last_ok      # epoch końca ostatniego udanego okna
date -u -d @"$(cat .state/abuseipdb_last_ok)"
```

## Diagnostyka

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| `cscli failed` / błędy `sudo -n` | brak lub zmiana reguły sudo bez hasła dla `cscli`; przetestuj `sudo -n cscli alerts list` |
| HTTP 401 lub 403 | zły lub cofnięty klucz API; sprawdź `ABUSEIPDB_API_KEY` w `~/.secrets/abuseipdb.conf` (tryb 600, co najmniej 20 znaków alfanumerycznych) |
| `OWN_NAME_MARKERS is empty ... NOT sending` | plik konfiguracji nie istnieje, jest nieczytelny albo nie ma `OWN_NAME_MARKERS`; popraw `~/.secrets/abuseipdb.conf` (wzór: `abuseipdb.conf.example`) |
| `OWN_NAME_MARKERS still holds the example values ... NOT sending` | `OWN_NAME_MARKERS` to nadal `your-domain.example,your-host.example` z szablonu; wpisz własne domeny i nazwę hosta |
| `config file ... is invalid`, `invalid EXCLUDE entry`, `OWN_NAME_MARKERS has ... invalid entries` | config ma zniekształconą linię, nieznany klucz (literówkę), komentarz po wartości albo wpis, który nie jest adresem; generator kończy się kodem 2, a wrapper wysyła alert; popraw wskazaną linię (komentarze tylko w osobnych liniach) |
| `ABUSEIPDB_API_KEY is still the example value` | klucz to nadal `YOUR_ABUSEIPDB_API_KEY` z szablonu; ustaw własny klucz |
| w logu `NTFY_TOPIC has invalid characters` lub `NTFY_URL is not a plain http(s) URL` | komentarz lub zbędny znak po wartości; temat to tylko litery, cyfry, `_` i `-` |
| w logu `NTFY_TOPIC is still the example value` | `NTFY_TOPIC` to nadal `your-private-ntfy-topic`; alerty celowo tam nie idą, ustaw własny prywatny temat |
| HTTP 429 | wyczerpany dzienny limit `bulk-report` (możliwe po ręcznych przebiegach); poczekaj na `Retry-After`, powtórek nie ma |
| HTTP 422 | zniekształcone CSV; szczegół z API jest w logu; uruchom `--validate` na `reports.csv` |
| brak alertów ntfy, w logu `ntfy ERROR ... 429` | dzienny limit wiadomości `ntfy.sh` dla twojego adresu; wrapper wysyła już przez IPv4 (`curl -4`), bo wspólną pulę IPv6 łatwo wyczerpać. Sprawdź treść odpowiedzi (`code 42908` = limit dzienny); na hoście tylko z IPv6 usuń `-4` albo postaw własny ntfy (`NTFY_URL`) |
| `jq is not installed` | `apt install jq` |
| `previous run is still in progress` | inny przebieg trzyma blokadę; sprawdź `pgrep -af abuseipdb_send` zanim ruszysz plik blokady |
| `skipping: last report was ... ago` | blokada 20 h; normalne po ręcznym przebiegu |
| `watermark from the future` | rozjazd zegara; sprawdź `timedatectl`, potem świadomie popraw lub usuń znacznik |
| `journalctl returned code ... new SSH logins may be MISSING from the auto-trust` | użytkownik usługi nie czyta całego journala (albo `journalctl` nie ma `--grep`); dodaj go do grupy `adm` lub `systemd-journal` (`sudo usermod -aG systemd-journal <user>`, potem zaloguj się ponownie) i sprawdź `journalctl -u ssh --grep Accepted` |
| `ALERT_LIMIT must be a whole number` | popraw wartość `ALERT_LIMIT=` w linii crontaba (od 1 do 9 999 999) |
| zgłoszono własny, udokumentowany IP | dopisz go jako linię `EXCLUDE=` w `~/.secrets/abuseipdb.conf` i zbadaj, czemu auto-zaufanie SSH go nie złapało |

## Sekrety i kopie zapasowe

- Cała konfiguracja to jeden plik, `~/.secrets/abuseipdb.conf` (tryb 600, katalog w trybie 700); wzór to
  `abuseipdb.conf.example`. Klucz API i temat ntfy nigdy nie pojawiają się w repozytorium, argumentach, logach ani na
  liście procesów. Plik jest parsowany jako tekst i nigdy nie jest wykonywany.
- Dawne osobne pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` to przestarzały zapas: config ma
  pierwszeństwo, a wrapper loguje ostrzeżenie, gdy musi czytać stary plik klucza. Po migracji usuń je.
- Config (wykluczenia, znaczniki własnych nazw) i trwała lista zaufanych IP z SSH to stan trudny do odtworzenia,
  chroniący przed zgłoszeniem własnego adresu. Dodaj `~/.secrets/` do własnej rutyny kopii zapasowych.
- Cofnięcie złego wydania: `git checkout <poprzedni tag lub commit>` w katalogu instalacji, `--dry-run`, a jeśli
  zmieniły się ścieżki, przywróć crontab z kopii.
