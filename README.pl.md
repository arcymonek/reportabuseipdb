[English](README.md) | **Polski**

Wersja: 3.6.32 (`abuseipdb_report.py`)

# reportabuseipdb

Automatyczne, zgodne z polityką zgłaszanie do [AbuseIPDB](https://www.abuseipdb.com/) atakujących wykrytych przez
własną instancję [CrowdSec](https://www.crowdsec.net/).

Projekt to para narzędzi dla samodzielnie hostowanego serwera z Linuksem:

- `abuseipdb_report.py` czyta **lokalnie wykryte** alerty CrowdSeca i buduje CSV do zgłoszeń zbiorczych (bulk),
  sprawdzony pod kątem reguł AbuseIPDB. Sam niczego nie wysyła.
- `abuseipdb_send.sh` to wrapper crona: wyznacza okno czasowe bez luk, uruchamia generator, waliduje plik
  jeszcze raz, wysyła go na endpoint `bulk-report` AbuseIPDB, sprawdza odpowiedź API i przy podejrzanym wyniku
  wysyła alert przez [ntfy](https://ntfy.sh/).

> Projekt nieoficjalny, niezwiązany z AbuseIPDB ani CrowdSec i przez nie niepopierany.
>
> Prace w toku, działa produkcyjnie na jednym samodzielnie hostowanym serwerze.
> Wyniki możesz sprawdzić na moim [profilu AbuseIPDB](https://www.abuseipdb.com/user/339209).
>
> Napisane przez autora we współpracy z Claude Code (Anthropic).
> Autor nie jest zawodowym programistą, dlatego projekt ma rozbudowane testy i dokumentację.
> Przed użyciem na żywo uruchom `--dry-run` i przejrzyj CSV.

## Najważniejsza zasada

Fałszywe zgłoszenie może skończyć się zawieszeniem konta w AbuseIPDB, więc narzędzie opiera się na jednym
priorytecie: **nigdy nie zgłaszać czegoś, co nie jest prawdziwym, lokalnie zaobserwowanym atakiem**, i nigdy nie
zgłaszać własnego adresu operatora. Reszta (wygoda, zasięg) jest wtórna. Pełna lista zabezpieczeń:
[Bezpieczniki](#bezpieczniki).

## Jak to działa

1. Cron o 05:30 uruchamia `abuseipdb_send.sh`, który wyznacza okno czasowe `(znacznik, teraz]`: kolejne przebiegi
   nie nakładają się i nie mają luk.
2. `abuseipdb_report.py` czyta z `cscli alerts list` tylko **lokalnie wykryte** alerty, stosuje filtry i
   bezpieczniki i buduje `reports.csv`.
3. Wrapper waliduje ten plik jeszcze raz, niezależnie od generatora (`--validate`).
4. `curl` wysyła plik na endpoint `bulk-report`; kod HTTP i odpowiedź JSON są sprawdzane.
5. Znacznik czasu przesuwa się dopiero po udanej wysyłce. Przy każdym błędzie operator dostaje alert ntfy.

## Przykład zgłoszenia

Jeden wiersz wysyłanego pliku CSV. Adres pochodzi z zakresu przeznaczonego na dokumentację, więc jest fikcyjny;
prawdziwy przebieg zgłasza prawdziwych atakujących.

```csv
IP,Categories,ReportDate,Comment
203.0.113.45,"14,15,21",2026-10-01T11:09:03+00:00,"Detected by CrowdSec IDS on a self-hosted server. Target: HTTP/HTTPS (ports 80/443). Triggered rules: http-probing, http-sensitive-files. 4 matching log events between 2026-10-01T11:08:42Z and 11:09:03Z (UTC). Sample requests: GET /.env -> 404; GET /wp-login.php -> 404; GET /.git/config -> 404; GET /admin/config.php -> 404"
```

- `Categories` są przypisane per scenariusz CrowdSeca (tu 14 = otwarte porty i podatne usługi, 15 = hacking,
  21 = atak na aplikację webową).
- `ReportDate` to czas ostatniej obserwacji, w UTC.
- `Comment` jest zbudowany ze stałych angielskich zdań, więc nigdy nie zawiera nazwy twojego hosta, twoich domen ani
  zgłaszanego adresu. Próbki żądań pochodzą od atakującego: próbka zawierająca taką nazwę jest pomijana, a wartości
  parametrów wyglądających na dane uwierzytelniające są zastępowane przez `***`.

## Wymagania

- Linux z systemd, `bash`, `curl`, `jq`, `flock` (util-linux), GNU `date`, `journalctl` i `ip`.
- Testowane tylko na Debianie 12 (produkcja) i Ubuntu 24.04 (CI), z CrowdSecem 1.7 i 1.8 oraz nginx jako reverse proxy.
  Inne dystrybucje, serwery WWW i wersje CrowdSeca nie były testowane: uruchom `--dry-run`, przejrzyj CSV i licz się
  z koniecznością dostosowania instalacji. macOS, BSD i systemy bez systemd nie są wspierane (wrapper wymaga GNU
  `date` i `flock`), a `cscli` musi działać na tym samym hoście co skrypty (CrowdSec w kontenerze wymaga własnej
  nakładki).
- Python 3.9 lub nowszy (rozwijany na 3.11, testowany na 3.9 i 3.14), tylko biblioteka standardowa.
- CrowdSec z `cscli`, wywoływanym jako `sudo -n cscli alerts list` przez użytkownika usługi (reguła sudo bez hasła);
  gdy skrypt działa jako root, `cscli` jest wywoływany bezpośrednio i `sudo` nie jest potrzebne.
- Użytkownik usługi może czytać cały journal (grupa `systemd-journal` lub `adm`).
- Klucz API AbuseIPDB.
- Opcjonalnie: temat ntfy dla alertów.

## Zanim uruchomisz na żywo

Każde zgłoszenie jest publikowane z twojego konta AbuseIPDB, więc przed pierwszym przebiegiem na żywo sprawdź te punkty:

- **CrowdSec musi widzieć prawdziwy adres klienta.** Za Cloudflare lub innym CDN, load balancerem albo proxy, które
  nie przekazuje IP klienta (np. userland proxy Dockera), CrowdSec widzi adres proxy i to narzędzie zgłosiłoby CDN.
  Najpierw skonfiguruj moduł real-IP serwera WWW (`set_real_ip_from` / `real_ip_header` w nginx) i rozważ dopisanie
  zakresów CDN jako wpisów `EXCLUDE` na wszelki wypadek.
- **Za NAT wyklucz swój publiczny adres.** Na wielu maszynach w chmurze publiczny IP nie jest na żadnym interfejsie,
  więc bezpiecznik "własne adresy publiczne" (czytany z `ip addr`) go nie widzi. Dopisz go jako wpis `EXCLUDE`.
- **Journal systemd.** Auto-zaufanie SSH czyta udane logowania z journald. Bez niego (np. w kontenerze) bezpiecznik
  jest pusty: wpisz własne adresy jako `EXCLUDE`.
- **Twój ruch, twoje fałszywe alarmy.** Scenariusz, który odpala na twoim legalnym ruchu (masowe uploady, WebDAV,
  monitoring), należy do `EXTRA_EXCLUDE_SCENARIOS`. Uruchamiaj `--dry-run` przez kilka dni i czytaj CSV, zanim
  pozwolisz cronowi cokolwiek wysłać.
- **IPv6 i wspólny /64.** Udane logowanie SSH z adresu IPv6 zaufa całemu jego /64 (twoje urządzenia zmieniają "tymczasowe"
  adresy w jego obrębie), więc inne urządzenia twojej sieci też nie będą zgłaszane. Przy hostingu, w którym jeden /64 dzieli
  wielu klientów, ustaw `SSH_TRUST_IPV6_PREFIX=128`, żeby zaufać tylko dokładnemu adresowi. IPv4 jest zawsze dokładne.
- **Inne porty WWW.** Jeśli serwer WWW nie słucha na 80 i 443, ustaw `HTTP_PORTS`, inaczej zgłoszenia podadzą zły port.

## Szybki start

```bash
sudo apt install jq                  # Debian/Ubuntu; curl, flock i ip zwykle już są
git clone https://github.com/arcymonek/reportabuseipdb.git abuseipdb && cd abuseipdb

mkdir -p ~/.secrets && chmod 700 ~/.secrets
cp abuseipdb.conf.example ~/.secrets/abuseipdb.conf
chmod 600 ~/.secrets/abuseipdb.conf
$EDITOR ~/.secrets/abuseipdb.conf    # każda linia ma komentarz; ustaw klucz, temat i własne nazwy
```

Pozwól użytkownikowi usługi czytać alerty CrowdSeca bez hasła, i tylko je (zamień `<user>`; ścieżkę sprawdź przez
`command -v cscli`):

```bash
echo '<user> ALL=(root) NOPASSWD: /usr/bin/cscli alerts list *' | sudo tee /etc/sudoers.d/abuseipdb
sudo chmod 440 /etc/sudoers.d/abuseipdb && sudo visudo -c
sudo usermod -aG systemd-journal <user>   # auto-zaufanie SSH czyta journal; potem zaloguj się ponownie
sudo -n cscli alerts list --limit 1       # musi działać bez pytania o hasło
```

Potem sprawdź wszystko bez wysyłania czegokolwiek:

```bash
./abuseipdb_send.sh --dry-run        # generuje i sprawdza, nic nie wysyła i nie zapisuje
```

Wpis w crontabie (jedno uruchomienie na dobę to wytyczna AbuseIPDB):

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

## Konfiguracja

Cała konfiguracja leży w **jednym pliku poza repozytorium**, `~/.secrets/abuseipdb.conf` (tryb 600; ścieżkę zmienia
`ABUSEIPDB_CONFIG` lub `--config`). Skopiuj [abuseipdb.conf.example](abuseipdb.conf.example), który objaśnia każdą
linię (komentarze w pliku są po angielsku). Plik to tekst `KEY=value`, czytany jako dane i nigdy nie wykonywany. Jest
sprawdzany ściśle: zniekształcona linia, nieznany klucz, komentarz po wartości albo nieprawidłowy wpis `EXCLUDE`
zatrzymują przebieg z błędem, zamiast po cichu wyłączyć bezpiecznik (komentarze tylko w osobnych liniach):

- `ABUSEIPDB_API_KEY`: klucz API AbuseIPDB (wymagany)
- `NTFY_TOPIC`: temat ntfy dla alertów (wymagany dla alertów; traktować jak sekret)
- `NTFY_URL`: serwer ntfy (opcjonalny, domyślnie `https://ntfy.sh`)
- `OWN_NAME_MARKERS`: fragmenty rozdzielone przecinkami (własne domeny i host), których nigdy nie może zawierać komentarz zgłoszenia; przy pustej liście lub przy wartościach przykładowych wysyłka na żywo jest odmawiana
- `EXCLUDE`: IP lub CIDR, którego nigdy nie zgłaszać; klucz można powtarzać (opcjonalny)
- `HTTP_PORTS`: porty, na których słucha twój serwer WWW, podawane w zgłoszeniach HTTP (opcjonalny, domyślnie `80/443`; np. `443` lub `8080/8443`)
- `SSH_TRUST_IPV6_PREFIX`: długość prefiksu (64-128, domyślnie `64`) sieci zaufanej wokół adresu IPv6 z udanym logowaniem SSH; `128` ufa tylko dokładnemu adresowi (opcjonalnie)
- `EXTRA_EXCLUDE_SCENARIOS`: scenariusze CrowdSeca rozdzielone przecinkami, których nigdy nie zgłaszać, np. taki, który dawał fałszywe alarmy na twoim ruchu; krótka nazwa (`http-probing`) pasuje do każdego autora, pełna (`autor/nazwa`) tylko do tego autora; tylko dodaje do wbudowanych wykluczeń (opcjonalny)

Obok generowany jest `~/.secrets/ssh_trusted_seen.txt` (IP z udanym logowaniem SSH, wpisy wygasają po 60 dniach).
Dawne osobne pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` nadal działają jako przestarzały
zapas na czas migracji; plik konfiguracji ma pierwszeństwo.

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

- Tylko alerty wykryte przez ten serwer (`kind == "crowdsec"`); bany z listy społeczności nigdy nie są zgłaszane.
- Zgłoszenia starsze niż 60 dni są odrzucane w każdym wierszu.
- Adresy prywatne, zarezerwowane, CGNAT i inne nieglobalne nigdy nie są zgłaszane.
- Scenariusze o historii fałszywych alarmów są wykluczone; scenariusze będące tylko słabym sygnałem nie wystarczą same.
- Nieznane scenariusze nigdy nie są zgłaszane (tylko scenariusze `crowdsecurity` z mapy kategorii albo nazwane od CVE);
  scenariusz innego autora wymaga jawnego wpisu w `CATEGORY_MAP` pod pełną nazwą.
- Lista wykluczeń operatora (`EXCLUDE` w pliku konfiguracji, domyślnie włączona) oraz **auto-zaufanie SSH**: każdy adres, z którego w ciągu ostatnich
  60 dni udało się zalogować przez SSH, nigdy nie jest zgłaszany (trwała lista, bo journal bywa przycinany). Logowanie z
  IPv6 zaufa całej sieci /64, bo maszyna IPv6 zmienia adresy w jej obrębie (`SSH_TRUST_IPV6_PREFIX`).
- Własne publiczne adresy serwera są zawsze wykluczone.
- Treść komentarza składa się wyłącznie ze stałych angielskich, jest czystym ASCII, nigdy nie zawiera zgłaszanego
  IP, nazwy hosta serwera ani jego domen (drugie sprawdzenie względem twoich `OWN_NAME_MARKERS`) i ma najwyżej
  1024 bajty. Próbka żądania od atakującego, która zawierałaby taką nazwę, zgłaszany IP albo własny adres serwera,
  jest pomijana w komentarzu, więc jedna wrogia ścieżka nigdy nie blokuje całego pliku.
- Każdy plik jest walidowany dwukrotnie (generator i wrapper), a plik z błędem nigdy nie zastępuje poprzedniego.

Mapowanie na politykę: [docs/pl/COMPLIANCE.md](docs/pl/COMPLIANCE.md).

## Testy

```bash
python3 -m unittest discover -v tests     # testy generatora działają wszędzie; testy wrappera wymagają Linuksa
```

## Dokumentacja

- [docs/pl/ARCHITECTURE.md](docs/pl/ARCHITECTURE.md): przepływ danych, okna czasowe, pliki stanu, kody wyjścia, obsługa błędów
- [docs/pl/COMPLIANCE.md](docs/pl/COMPLIANCE.md): polityka i limity API AbuseIPDB odniesione do implementacji
- [docs/pl/OPERATIONS.md](docs/pl/OPERATIONS.md): cron, monitoring, alerty, diagnostyka, lista kontrolna pierwszego przebiegu
- [docs/pl/DEVELOPMENT.md](docs/pl/DEVELOPMENT.md): workflow, testy, wersjonowanie, zasady językowe, lista przed publikacją
- [docs/pl/CHANGELOG.md](docs/pl/CHANGELOG.md): historia wersji
- [docs/pl/CONTRIBUTING.md](docs/pl/CONTRIBUTING.md): jak zgłosić błąd, zaproponować zmianę i wysłać pull request
- [docs/pl/SECURITY.md](docs/pl/SECURITY.md): jak prywatnie zgłosić podatność
- [docs/pl/CODE_OF_CONDUCT.md](docs/pl/CODE_OF_CONDUCT.md): jak traktujemy się nawzajem (Contributor Covenant 2.1)
- [AGENTS.md](AGENTS.md): zasady dla agentów AI pracujących nad tym repozytorium (tylko po angielsku)

Wszystkie dokumenty istnieją po angielsku i po polsku (`README.pl.md`, `docs/pl/`), z wyjątkiem `AGENTS.md` (tylko po angielsku).

## Współpraca i bezpieczeństwo

Zgłoszenia błędów i pull requesty są mile widziane, po angielsku, także pisane z pomocą asystenta AI; patrz
[docs/pl/CONTRIBUTING.md](docs/pl/CONTRIBUTING.md) i, dla agentów programistycznych, [AGENTS.md](AGENTS.md).\
Pull request osłabiający bezpiecznik wymaga bardzo dobrego powodu.\
Podatności zgłaszaj prywatnie, jak opisano w [docs/pl/SECURITY.md](docs/pl/SECURITY.md), a nie w publicznym zgłoszeniu.

## Licencja i autor

[Licencja MIT](LICENSE).

Copyright (c) 2026 Arkadiusz Polak.

Arkadiusz Polak | <github@arkadiuszpolak.pl> | [arkadiuszpolak.pl](https://arkadiuszpolak.pl)
