# reportabuseipdb

[English](README.md) | **Polski**

[![testy](https://github.com/arcymonek/reportabuseipdb/actions/workflows/tests.yml/badge.svg)](https://github.com/arcymonek/reportabuseipdb/actions/workflows/tests.yml)
![licencja: MIT](https://img.shields.io/badge/licencja-MIT-blue)
![python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![platforma: Linux (systemd)](https://img.shields.io/badge/platforma-Linux%20%28systemd%29-blue)
![zależności pythona: brak](https://img.shields.io/badge/zale%C5%BCno%C5%9Bci%20pythona-brak-brightgreen)
![zgłasza: tylko lokalne wykrycia](https://img.shields.io/badge/zg%C5%82asza-tylko%20lokalne%20wykrycia-brightgreen)

[Szybki start](#szybki-start) · [Konfiguracja](#konfiguracja) · [Bezpieczniki](#bezpieczniki) ·
[Dokumentacja](#dokumentacja) · [Changelog](docs/pl/CHANGELOG.md) ·
[Współpraca i bezpieczeństwo](#współpraca-i-bezpieczeństwo) · [Licencja i autor](#licencja-i-autor)

Automatyczne zgłaszanie do [AbuseIPDB](https://www.abuseipdb.com/) atakujących wykrytych przez własną instancję
[CrowdSec](https://www.crowdsec.net/), zbudowane tak, by trzymać się polityki zgłoszeń AbuseIPDB.

Projekt to para narzędzi dla samodzielnie hostowanego serwera z Linuksem:

- `abuseipdb_report.py` czyta **lokalnie wykryte** alerty CrowdSeca i buduje CSV do zgłoszeń zbiorczych (bulk),
  sprawdzony pod kątem reguł AbuseIPDB. Sam niczego nie wysyła.
- `abuseipdb_send.sh` to wrapper crona: wyznacza okno czasowe bez luk, uruchamia generator, waliduje plik
  jeszcze raz, wysyła go na endpoint `bulk-report` AbuseIPDB, sprawdza odpowiedź API i przy podejrzanym wyniku
  wysyła alert przez [ntfy](https://ntfy.sh/).

> Projekt jest ukończony i działa produkcyjnie na jednym samodzielnie hostowanym serwerze. Chętnie przyjmę poprawki
> i uwagi. Wyniki możesz sprawdzić na moim [profilu AbuseIPDB](https://www.abuseipdb.com/user/339209).
>
> Projekt nieoficjalny: nie jest powiązany z AbuseIPDB ani CrowdSec i nie jest przez nie firmowany.
>
> Napisane przez autora we współpracy z Claude Code (Anthropic).
> Autor nie jest zawodowym programistą, dlatego projekt ma rozbudowane testy i dokumentację.
>
> Przed użyciem na żywo uruchom `--dry-run` i przejrzyj CSV.

## Najważniejsza zasada

Fałszywe zgłoszenie może skończyć się zawieszeniem konta w AbuseIPDB, więc narzędzie opiera się na jednym
priorytecie: **nigdy nie zgłaszać czegoś, co nie jest prawdziwym, lokalnie zaobserwowanym atakiem**, i nigdy nie
zgłaszać własnego adresu operatora. Reszta (wygoda, zasięg) jest wtórna. Pełna lista zabezpieczeń:
[Bezpieczniki](#bezpieczniki).

## Przykład zgłoszenia

Przykładowy wiersz pliku CSV.

```csv
IP,Categories,ReportDate,Comment
203.0.113.45,"14,15,21",2026-10-01T11:09:03+00:00,"Detected by CrowdSec IDS on a self-hosted server. Target: HTTP/HTTPS (ports 80/443). Triggered rules: http-probing, http-sensitive-files. 4 matching log events between 2026-10-01T11:08:42Z and 11:09:03Z (UTC). Sample requests: GET /.env -> 404; GET /wp-login.php -> 404; GET /.git/config -> 404; GET /admin/config.php -> 404"
```

- `Categories` są przypisane per scenariusz CrowdSeca (tu 14 = Port Scan, 15 = Hacking, 21 = Web App Attack).
- `ReportDate` to czas ostatniej obserwacji, w UTC.
- `Comment` jest zbudowany ze stałych angielskich zdań i nigdy nie zawiera nazwy twojego hosta, twoich domen ani
  zgłaszanego adresu (szczegóły w sekcji [Bezpieczniki](#bezpieczniki)).
- Adres IP w przykładzie jest fikcyjny (zakres zarezerwowany na dokumentację); prawdziwy przebieg zgłasza prawdziwych
  atakujących.

## Jak to działa

1. Cron uruchamia `abuseipdb_send.sh` raz na dobę (w przykładzie o 05:30). Wrapper wyznacza okno czasowe
   `(znacznik, teraz]`: kolejne przebiegi nie nakładają się i nie mają luk czasowych.
2. `abuseipdb_report.py` czyta z `cscli alerts list` tylko **lokalnie wykryte** alerty, stosuje filtry i
   bezpieczniki i buduje `reports.csv`.
3. Wrapper waliduje ten plik jeszcze raz, niezależnie od generatora (`--validate`).
4. Wrapper wysyła plik do AbuseIPDB i sprawdza w odpowiedzi, czy zgłoszenia zostały przyjęte.
5. Znacznik czasu przesuwa się dopiero po udanej wysyłce.

Przy błędzie na dowolnym etapie operator dostaje alert ntfy.

## Wymagania

- Linux z systemd, `bash`, `curl`, `jq`, `flock` (util-linux), GNU `date`, `journalctl` i `ip`.
- Testowane tylko na Debianie 12 (produkcja) i Ubuntu 24.04 (CI).
- Testowane z CrowdSec 1.8 i nginx jako reverse proxy. Inne wersje, dystrybucje i serwery WWW nie były testowane:
  uruchom `--dry-run`, przejrzyj CSV i daj znać, jak poszło.
- Niewspierane: macOS i BSD (wrapper wymaga GNU `date` i `flock`). Bez systemd (np. w kontenerze) auto-zaufanie SSH
  nie ma journala do czytania: patrz [Zanim uruchomisz na żywo](#zanim-uruchomisz-na-żywo).
- `cscli` musi działać na tym samym hoście co skrypty (CrowdSec w kontenerze wymaga własnej nakładki).
- Python 3.9 lub nowszy (rozwijany na 3.11, testowany w CI na 3.9 i na najnowszym Pythonie), tylko biblioteka standardowa.
- CrowdSec z `cscli`, wywoływanym jako `sudo -n cscli alerts list` przez użytkownika usługi (reguła sudo bez hasła);
  gdy skrypt działa jako root, `cscli` jest wywoływany bezpośrednio i `sudo` nie jest potrzebne.
- Użytkownik usługi musi mieć prawo odczytu całego journala (grupa `systemd-journal` lub `adm`); bez niego przebieg
  trwa, ale auto-zaufanie SSH jest niepełne i operator dostaje alert.
- Klucz API AbuseIPDB.
- Opcjonalnie: temat ntfy dla alertów.

## Zanim uruchomisz na żywo

Każde zgłoszenie jest publikowane z twojego konta AbuseIPDB, więc przed pierwszym przebiegiem na żywo sprawdź te punkty:

- **Prawdziwy adres klienta.** Za CDN, load balancerem albo proxy upewnij się, że CrowdSec widzi IP klienta.
- **NAT.** Jeśli publiczny IP nie jest na żadnym interfejsie, dopisz go jako wpis `EXCLUDE`.
- **Brak journala systemd.** Auto-zaufanie SSH jest wtedy puste: wpisz własne adresy jako `EXCLUDE`.
- **Własny ruch.** Scenariusz, który na nim odpala, wpisz do `EXTRA_EXCLUDE_SCENARIOS`; uruchamiaj `--dry-run` przez kilka dni.
- **Wspólny /64 w IPv6.** Jeśli dostawca dzieli jeden /64 między klientów, ustaw `SSH_TRUST_IPV6_PREFIX=128`.
- **Inne porty WWW.** Jeśli serwer WWW nie słucha na 80 i 443, ustaw `HTTP_PORTS`.

Dlaczego i jak: [docs/pl/OPERATIONS.md](docs/pl/OPERATIONS.md#przed-pierwszym-przebiegiem-na-żywo).

## Szybki start

1. Zainstaluj `jq` (Debian/Ubuntu; `curl`, `flock` i `ip` zwykle już są) i sklonuj repozytorium:

   ```bash
   sudo apt install jq
   git clone https://github.com/arcymonek/reportabuseipdb.git abuseipdb && cd abuseipdb
   ```

2. Utwórz plik konfiguracji poza repozytorium i ustaw klucz, temat i własne nazwy (każda linia ma komentarz):

   ```bash
   mkdir -p ~/.secrets && chmod 700 ~/.secrets
   cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf
   chmod 600 ~/.secrets/abuseipdb.conf
   $EDITOR ~/.secrets/abuseipdb.conf
   ```

3. Pozwól użytkownikowi usługi czytać alerty CrowdSeca bez hasła, i tylko je, oraz czytać journal dla auto-zaufania
   SSH (zamień `<user>`; ścieżkę sprawdź przez `command -v cscli`; po `usermod` zaloguj się ponownie). Ostatnie
   polecenie musi zadziałać bez pytania o hasło:

   ```bash
   echo '<user> ALL=(root) NOPASSWD: /usr/bin/cscli alerts list *' | sudo tee /etc/sudoers.d/abuseipdb
   sudo chmod 440 /etc/sudoers.d/abuseipdb && sudo visudo -c
   sudo usermod -aG systemd-journal <user>
   sudo -n cscli alerts list --limit 1
   ```

4. Sprawdź wszystko bez wysyłania czegokolwiek (generuje i sprawdza, nic nie wysyła i nie zapisuje):

   ```bash
   ./abuseipdb_send.sh --dry-run
   ```

5. Dodaj wpis w crontabie. Jedno uruchomienie na dobę: AbuseIPDB prosi, by ten sam adres zgłaszać mniej więcej raz na dobę.

   ```bash
   30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
   ```

## Konfiguracja

Cała konfiguracja leży w **jednym pliku poza repozytorium**, `~/.secrets/abuseipdb.conf` (tryb 600; ścieżkę zmienia
`ABUSEIPDB_CONFIG` lub `--config`). Skopiuj [abuseipdb.conf.example](abuseipdb.conf.example), który objaśnia każdą
linię (komentarze w pliku są po angielsku). Plik to tekst `KEY=value`, czytany jako dane i nigdy nie wykonywany. Jest
sprawdzany ściśle: zniekształcona linia, nieznany klucz, komentarz po wartości albo nieprawidłowy wpis `EXCLUDE`
zatrzymują przebieg z błędem, zamiast po cichu wyłączyć bezpiecznik (komentarze tylko w osobnych liniach).

- `ABUSEIPDB_API_KEY`: klucz API AbuseIPDB (wymagany)
- `NTFY_TOPIC`: temat ntfy dla alertów (wymagany dla alertów; traktować jak sekret)
- `NTFY_URL`: serwer ntfy (opcjonalny, domyślnie `https://ntfy.sh`)
- `OWN_NAME_MARKERS`: własne domeny i nazwa hosta, rozdzielone przecinkami; nigdy nie mogą pojawić się w komentarzu
  zgłoszenia, a przy pustej liście lub przy wartościach przykładowych wysyłka na żywo jest odmawiana
- `EXCLUDE`: IP lub CIDR, którego nigdy nie zgłaszać; klucz można powtarzać (opcjonalny)
- `HTTP_PORTS`: porty, na których słucha twój serwer WWW, podawane w zgłoszeniach HTTP (opcjonalny, domyślnie `80/443`)
- `SSH_TRUST_IPV6_PREFIX`: jak szeroka sieć jest zaufana wokół adresu IPv6 z udanym logowaniem SSH
  (opcjonalny, 64-128, domyślnie `64`; `128` ufa tylko dokładnemu adresowi)
- `EXTRA_EXCLUDE_SCENARIOS`: scenariusze CrowdSeca rozdzielone przecinkami, których nigdy nie zgłaszać, dodatkowo do
  wbudowanych wykluczeń; krótka nazwa (`http-probing`) pasuje do każdego autora, pełna (`autor/nazwa`) tylko do tego autora (opcjonalny)

Obok generowany jest `~/.secrets/ssh_trusted_seen.txt` (IP z udanym logowaniem SSH, wpisy wygasają po
60 dniach).

Dane robocze obok skryptów (ignorowane przez git): `reports.csv`, `abuseipdb_cron.log`, `.state/`.

## Użycie

```bash
./abuseipdb_send.sh                  # zwykły przebieg (to robi cron)
./abuseipdb_send.sh --dry-run        # bez wysyłki, bez znacznika, bez aktualizacji listy zaufanych IP
./abuseipdb_send.sh --force          # pomija blokadę "ostatnie zgłoszenie < 20 h temu" (używać świadomie)
python3 abuseipdb_report.py --validate reports.csv   # sprawdza CSV wg reguł AbuseIPDB
python3 abuseipdb_report.py --help
```

## Bezpieczniki

- **Tylko lokalne wykrycia** (`kind == "crowdsec"`): adresy z blocklist to cudze obserwacje i nigdy nie są
  zgłaszane.
- **Wiek**: nic starszego niż 60 dni nie jest zgłaszane.
- **Rodzaj adresu**: adresy prywatne, zarezerwowane, CGNAT i inne nieglobalne nigdy nie są zgłaszane.
- **Scenariusze**: te o historii fałszywych alarmów są wykluczone; sam słaby sygnał nie wystarcza.
- **Nieznane scenariusze** nigdy nie są zgłaszane, tylko pomijane i wypisywane w logu (`unknown scenario ...`); zgłoś
  nazwę w issue, a opiekun sprawdzi, co scenariusz wykrywa, zanim go doda.
- **Twoje wykluczenia**: wpisy `EXCLUDE` z pliku konfiguracji oraz **auto-zaufanie SSH**: każdy adres z udanym logowaniem
  SSH w ostatnich 60 dniach (logowanie z IPv6 zaufa całej sieci /64, patrz `SSH_TRUST_IPV6_PREFIX`).
- **Własne adresy**: własne publiczne adresy serwera są zawsze wykluczone.
- **Komentarz**: wyłącznie stałe angielskie zdania, czyste ASCII, najwyżej 1024 bajty, nigdy zgłaszany IP, nazwa hosta
  serwera ani jego domeny (sprawdzane drugi raz względem twoich `OWN_NAME_MARKERS`).
- **Podwójna walidacja**: każdy plik jest walidowany dwukrotnie (generator i wrapper), a plik z błędem nigdy nie zastępuje
  poprzedniego.

Szczegóły: [docs/pl/COMPLIANCE.md](docs/pl/COMPLIANCE.md) (mapowanie na politykę i każdy bezpiecznik) oraz
[docs/pl/ARCHITECTURE.md](docs/pl/ARCHITECTURE.md) (walidacja i obsługa błędów).

## Testy

Testy używają atrap: nie łączą się z AbuseIPDB ani ntfy i nie potrzebują klucza API.

```bash
python3 -m unittest discover -v tests     # testy generatora działają wszędzie; testy wrappera wymagają Linuksa
```

## Dokumentacja

- [docs/pl/ARCHITECTURE.md](docs/pl/ARCHITECTURE.md): przepływ danych, okna czasowe, pliki stanu, kody wyjścia, obsługa błędów
- [docs/pl/COMPLIANCE.md](docs/pl/COMPLIANCE.md): polityka i limity API AbuseIPDB odniesione do implementacji
- [docs/pl/OPERATIONS.md](docs/pl/OPERATIONS.md): cron, monitoring, alerty, diagnostyka, lista kontrolna pierwszego przebiegu
- [docs/pl/DEVELOPMENT.md](docs/pl/DEVELOPMENT.md): przygotowanie środowiska, testy, hooki, zasady językowe, workflow, wersjonowanie, stałe kontrole
- [docs/pl/CHANGELOG.md](docs/pl/CHANGELOG.md): historia wersji
- [docs/pl/CONTRIBUTING.md](docs/pl/CONTRIBUTING.md): jak zgłosić błąd, zaproponować zmianę i wysłać pull request
- [docs/pl/SECURITY.md](docs/pl/SECURITY.md): jak prywatnie zgłosić podatność
- [docs/pl/CODE_OF_CONDUCT.md](docs/pl/CODE_OF_CONDUCT.md): jak traktujemy się nawzajem (Contributor Covenant 2.1)
- [AGENTS.md](AGENTS.md): zasady dla agentów AI pracujących nad tym repozytorium (tylko po angielsku)

Wszystkie dokumenty istnieją po angielsku i po polsku (`README.pl.md`, `docs/pl/`), z wyjątkiem `AGENTS.md` (tylko po angielsku).

## Współpraca i bezpieczeństwo

Forki, zgłoszenia błędów i pull requesty są mile widziane (licencja MIT), po angielsku, także pisane z pomocą
asystenta AI. Szczególnie przydatne:

- jak narzędzie zadziałało na innej dystrybucji, serwerze WWW lub wersji CrowdSeca;
- scenariusz CrowdSeca pomijany jako nieznany;
- poprawki dokumentacji.

Zacznij od [docs/pl/CONTRIBUTING.md](docs/pl/CONTRIBUTING.md); agenci programistyczni czytają [AGENTS.md](AGENTS.md).\
Pull request osłabiający bezpiecznik wymaga bardzo dobrego powodu.\
Podatności zgłaszaj prywatnie, jak opisano w [docs/pl/SECURITY.md](docs/pl/SECURITY.md), a nie w publicznym zgłoszeniu.

## Licencja i autor

[Licencja MIT](LICENSE).

Copyright (c) 2026 Arkadiusz Polak.

<github@arkadiuszpolak.pl> | [arkadiuszpolak.pl](https://arkadiuszpolak.pl)
