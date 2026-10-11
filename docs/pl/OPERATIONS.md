[English](../OPERATIONS.md) | **Polski**

# Eksploatacja

Ta strona jest dla osoby, która uruchamia narzędzie: pierwszy start, zadanie crona, alerty, co robić przy awarii i
aktualizacje. Jak program działa w środku, opisuje [ARCHITECTURE.md](ARCHITECTURE.md), a co jest zgłaszane i dlaczego,
[COMPLIANCE.md](COMPLIANCE.md). Sekcje idą w kolejności życia instalacji.

## Przed pierwszym przebiegiem na żywo

Każde zgłoszenie jest publikowane z twojego konta AbuseIPDB. README wymienia te punkty po jednej linii; tu jest
dłuższe wyjaśnienie.

- **CrowdSec musi widzieć prawdziwy adres klienta.** Za Cloudflare lub innym CDN, load balancerem albo proxy, które
  nie przekazuje IP klienta (np. userland proxy Dockera), CrowdSec widzi adres proxy i to narzędzie zgłosiłoby CDN.
  Najpierw skonfiguruj moduł real-IP serwera WWW (`set_real_ip_from` / `real_ip_header` w nginx) i rozważ dopisanie
  zakresów CDN jako wpisów `EXCLUDE` na wszelki wypadek.
- **Za NAT wyklucz swój publiczny adres.** Na wielu maszynach w chmurze publiczny IP nie jest na żadnym interfejsie,
  więc bezpiecznik "własne adresy publiczne" (czytany z `ip addr`) go nie widzi. Dopisz go jako wpis `EXCLUDE`.
- **Dziennik systemowy (journal).** Auto-zaufanie SSH czyta udane logowania z journald. Bez niego (np. w kontenerze)
  bezpiecznik jest pusty: wpisz własne adresy jako `EXCLUDE`.
- **Twój ruch, twoje fałszywe alarmy.** Scenariusz, który odpala na twoim legalnym ruchu (masowe uploady, WebDAV,
  monitoring), należy do `EXTRA_EXCLUDE_SCENARIOS`. Auto-zaufanie SSH chroni tylko adresy, z których ktoś zalogował się
  przez SSH, więc urządzenie, które tylko korzysta z twoich usług (telefon, sieć biura, sonda monitoringu), wymaga
  wpisu `EXCLUDE`. Uruchamiaj `--dry-run` przez kilka dni i czytaj CSV, zanim pozwolisz cronowi cokolwiek wysłać
  (patrz "Jak czytać wynik dry-run").
- **IPv6 i wspólny /64.** Udane logowanie SSH z adresu IPv6 zaufa całemu jego /64 (twoje urządzenia zmieniają
  "tymczasowe" adresy w jego obrębie), więc inne urządzenia twojej sieci też nie będą zgłaszane. Przy hostingu, w
  którym jeden /64 dzieli wielu klientów, ustaw `SSH_TRUST_IPV6_PREFIX=128`, żeby zaufać tylko dokładnemu adresowi.
  IPv4 jest zawsze dokładne.
- **Inne porty WWW.** Jeśli serwer WWW nie słucha na 80 i 443, ustaw `HTTP_PORTS`, inaczej zgłoszenia podadzą zły port.

## Harmonogram

```bash
30 5 * * * /path/to/abuseipdb/abuseipdb_send.sh >> /path/to/abuseipdb/abuseipdb_cron.log 2>&1
```

Jedno uruchomienie na dobę. Przed zmianą crontaba zachowaj kopię (`crontab -l > ~/crontab.bak-DATA`) i instaluj nową
wersję z pliku, nigdy przez potok, który może być pusty.

Nie uruchamiaj narzędzia ręcznie bez powodu. Wrapper pomija drugi przebieg w ciągu 20 h od ostatniego sukcesu
("strażnik 20 h"), więc ręczny przebieg zwykle kończy się odmową z linią w logu. `--force` świadomie omija strażnika i ma
skutek uboczny: znacznik przesuwa się na czas twojego przebiegu, następny zaplanowany przebieg jest pomijany przez
strażnika (kod 0, to nie błąd), a dopiero kolejny pokrywa całą lukę. Alerty nie przepadają, bo okno zawsze zaczyna się od
znacznika. Przy zewnętrznym monitorze (patrz niżej) przebieg z `--force` między ok. 09:30 a 17:30 (dla crona o 05:30
powyżej) sprawia jednak, że plik jest starszy niż 36 h na kilka godzin przed przebiegiem, który to naprawia, i monitor
ostrzega bez powodu.

## Lista kontrolna pierwszego przebiegu

Wykonaj ją po świeżej instalacji lub przeprowadzce.

1. `./abuseipdb_send.sh --version` i `python3 abuseipdb_report.py --version`.
   Utwórz plik konfiguracji (polecenia są w szybkim starcie w README) i ustaw klucz API, temat ntfy oraz
   `OWN_NAME_MARKERS`. Przebieg na żywo jest odmawiany, dopóki znaczniki są puste lub mają wartości przykładowe.
2. `./abuseipdb_send.sh --dry-run` i przeczytaj wynik (patrz "Jak czytać wynik dry-run" niżej).
3. Dodaj linię crona. `crontab -l` pokazuje nową ścieżkę zarówno w poleceniu, jak i w przekierowaniu logu.
4. Po pierwszym zaplanowanym przebiegu `abuseipdb_cron.log` kończy się liniami takimi jak te (skrócone, liczby będą
   inne):

   ```
   2026-10-12 05:30:01 [send] start v3.6.34
   2026-10-12 05:30:01 [send] window: (2026-10-11T03:30:01Z, 2026-10-12T03:30:01Z] = 24.0 h
   2026-10-12 05:30:04 [send]   generator: Wrote 7 unique IPs to /path/to/abuseipdb/reports.csv (...)
   2026-10-12 05:30:04 [send] file ready: 7 reports, validation OK
   2026-10-12 05:30:06 [send] OK: sent 7, saved 7, rejected 0; window (...]; remaining bulk-report limit: 19
   2026-10-12 05:30:06 [send] watermark updated: 2026-10-12T03:30:01Z
   ```

   W dzień bez niczego do zgłoszenia log pokazuje zamiast tego `no qualifying reports in the window - nothing to send`;
   to normalne, a znacznik i tak się przesuwa.
5. `cat .state/abuseipdb_last_ok` zawiera świeży epoch; twój zewnętrzny monitor, jeśli go masz, pokazuje OK.

### Jak czytać wynik dry-run

`--dry-run` generuje i sprawdza CSV, ale niczego nie wysyła i nie zapisuje ani znacznika, ani listy zaufanych IP.
Alerty są tylko wypisywane (`[DRY-RUN ntfy ...]`). Nie sprawdza też klucza API i nie łączy się z AbuseIPDB ani z ntfy,
więc udany dry-run nie dowodzi, że wysyłka działa: dowodem jest dopiero pierwszy zaplanowany przebieg.

```bash
./abuseipdb_send.sh --dry-run | grep 'generator:'
```

Linie `generator:` mówią, czy bezpieczniki działają:

- `SSH auto-trust: N addresses with a successful login`: na serwerze, na który się logujesz, N ma być co najmniej 1.
  Ostrzeżenie `SSH auto-trust: NO successful login found` znaczy, że narzędzie nie widzi twoich logowań (patrz
  Diagnostyka).
- `excluded N own public addresses of the server`: gdy tej linii nie ma, narzędzie nie znalazło żadnego (za NAT dopisz
  własny adres jako `EXCLUDE`). Linia `[SAFEGUARD-OFF]` znaczy, że bezpiecznik nie działa: napraw to przed uruchomieniem
  na żywo.
- `loaded N exclusion entries from the config file`: pojawia się tylko wtedy, gdy masz wpisy `EXCLUDE`.
- `[filter] skipped N alerts - powód`: dlaczego alerty odrzucono (stare, zaufane, wykluczony scenariusz, nieznany
  scenariusz).

Potem wrapper wypisuje `DRY-RUN: would send N reports` i do trzech przykładowych wierszy uciętych do 170 znaków. Żeby
zobaczyć całe CSV, uruchom sam generator (ostatnie 24 h, wynik tylko na ekranie):

```bash
python3 abuseipdb_report.py --dry-run --since 24h
```

Gdy nic się nie kwalifikuje, wrapper wypisuje `no qualifying reports in the window - nothing to send` i nie ma linii
`DRY-RUN: would send`. W spokojny dzień to normalne. Jeśli ostatnie zgłoszenie było mniej niż 20 h temu, pojawia się
`(dry-run) a normal run would be SKIPPED`.

## Monitoring

Wrapper sam alarmuje przy awariach, ale nie zaalarmuje, gdy w ogóle przestanie się uruchamiać: martwy cron, usunięty
skrypt, przebieg, który się zawiesił (trzyma blokadę, więc kolejne są pomijane), albo alerty, które nie docierają (ntfy
nie działa, zły temat, wyczerpany limit). Pokryj to zewnętrznym monitorem (poza tym repozytorium), który co godzinę
ostrzega, gdy `.state/abuseipdb_last_ok` nie istnieje albo jest starszy niż 36 h. Nazwa tego pliku jest stabilnym
interfejsem dla takiego monitora.

Dlaczego 36 h: normalny cykl to 24 h, a 12 h zapasu wyłapuje jeden pominięty przebieg jeszcze tego samego dnia. Dzień bez
niczego do zgłoszenia też przesuwa plik, więc spokojny serwer nie daje fałszywych ostrzeżeń. Po awarii możesz dostać dwa
ostrzeżenia, jedno z wrappera i jedno z monitora; to nie jest usterka.

## Alerty

Alerty idą na twój temat ntfy (priorytet 4 to "wysoki", 3 to "domyślny") i trafiają też do logu. Ścieżka instalacji i
twój katalog domowy są w tekście opuszczającym serwer zamaskowane.

| Tytuł ntfy | Priorytet | Znaczenie | Co zrobić |
|---|---|---|---|
| `abuseipdb: reporting ERROR` | 4 | przebieg zatrzymał się, zanim znacznik się przesunął: awaria generatora, walidacji, klucza API, konfiguracji lub wysyłki (przyczyny są w Diagnostyce); treść podaje powód, gdy wrapper go zna, a przy awarii generatora przyczyna jest w liniach `generator:` w logu | przeczytaj końcówkę `abuseipdb_cron.log`; błąd przejściowy nadrobi następny przebieg (najwyżej 48 h wstecz), błąd konfiguracji powtarza się codziennie, dopóki go nie naprawisz |
| `abuseipdb: corrupted watermark` | 3 | `.state/abuseipdb_last_ok` ma nieprawidłową zawartość; użyto domyślnego okna 24 h | sprawdź plik, po następnym sukcesie zostanie nadpisany |
| `abuseipdb: gap in reports` | 3 | ostatni sukces starszy niż 48 h; okno ucięto do 48 h | ustal, czemu przebiegi zawodziły; starsze alerty przepadły |
| `abuseipdb: rejected reports` | 3 | AbuseIPDB odrzuciło część wierszy | zobacz linie `rejected:` w logu; znacznik się przesunął |
| `abuseipdb: data cut off` | 3 | limit uciął dane: `--limit` alertów czytanych z `cscli` albo limit 10 000 wierszy / 8 MB pliku CSV; okno i tak zamknięto, więc ucięte alerty nie zostaną zgłoszone | w logu linia ma postać `generator: [TRUNCATED] ...`. Podnieść można tylko limit alertów: ustaw `ALERT_LIMIT` w linii crontaba (`30 5 * * * ALERT_LIMIT=20000 /path/to/abuseipdb_send.sh >> ...`; domyślnie 5 000). Limity wierszy i rozmiaru ustala AbuseIPDB, więc zbadaj raczej falę alertów |
| `abuseipdb: safeguard not working` | 4 | generator wypisał linię zaczynającą się od `[SAFEGUARD-OFF]`: nie da się czytać dziennika systemowego (auto-zaufanie SSH niepełne), brak programu `ip` (nieznane własne publiczne adresy serwera) albo listy zaufanych IP nie da się odczytać lub zapisać; przebieg trwał dalej z pozostałymi bezpiecznikami | przeczytaj podany powód: dodaj użytkownika usługi do `systemd-journal` lub `adm`, zainstaluj `iproute2`, popraw uprawnienia `~/.secrets`; do tego czasu wpisz własne adresy jako `EXCLUDE` |
| `abuseipdb: count mismatch` | 3 | zapisane + odrzucone różni się od wysłanych | sprawdź odpowiedź API w logu |

## Szybka kontrola stanu

```bash
tail -n 30 abuseipdb_cron.log     # ostatni przebieg, linie z tagiem [send]
cat .state/abuseipdb_last_ok      # epoch końca ostatniego udanego okna (spokojny dzień też go przesuwa)
date -u -d @"$(cat .state/abuseipdb_last_ok)"
```

Nie musisz tego robić codziennie, bo o problemie informują alerty i zewnętrzny monitor.

## Diagnostyka

Pierwsza kolumna to tekst, który widzisz w logu (albo w alercie).

### Konfiguracja

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| `OWN_NAME_MARKERS is empty ... NOT sending` | plik konfiguracji nie istnieje, jest nieczytelny albo nie ma `OWN_NAME_MARKERS`; popraw `~/.secrets/abuseipdb.conf` (wzór: `abuseipdb.conf.example`) |
| `OWN_NAME_MARKERS still holds the example values ... NOT sending` | `OWN_NAME_MARKERS` to nadal `your-domain.example,your-host.example` z szablonu; wpisz własne domeny i nazwę hosta |
| `config file ... is invalid`, `invalid EXCLUDE entry`, `OWN_NAME_MARKERS has ... invalid entries`, `HTTP_PORTS ... is invalid`, `SSH_TRUST_IPV6_PREFIX ... is invalid`, `EXTRA_EXCLUDE_SCENARIOS has invalid names` | plik ma zniekształconą linię, nieznany klucz (literówkę), komentarz po wartości, wartość spoza zakresu lub w złym formacie albo istnieje, ale nie da się go przeczytać (uprawnienia, kodowanie inne niż UTF-8); generator kończy się kodem 2, a wrapper alarmuje codziennie, dopóki tego nie naprawisz; popraw wskazaną linię (komentarze tylko w osobnych liniach) |
| `API key missing`, `ABUSEIPDB_API_KEY is still the example value`, `API key has an unexpected format` | ustaw własny klucz w `~/.secrets/abuseipdb.conf`: co najmniej 20 liter lub cyfr, bez cudzysłowów i bez niczego po nim |
| `ALERT_LIMIT must be a whole number` | popraw wartość `ALERT_LIMIT=` w linii crontaba (od 1 do 9 999 999) |

### CrowdSec, dziennik systemowy i narzędzia

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| `cscli failed` / błędy `sudo -n` | brak lub zmiana reguły sudo bez hasła dla `cscli`; przetestuj `sudo -n cscli alerts list --limit 1` (reguła z README pozwala na `alerts list` z argumentami, więc samo polecenie bez argumentów jest odrzucane) |
| `generator exited with code 2` | generator zatrzymał się celowo; powód jest w liniach `generator:` tuż powyżej (konfiguracja, `cscli`, nieczytelne dane wejściowe) |
| `generator exited with code 1 without its 'No qualifying reports' message` | skrypt padł, zanim zdążył cokolwiek zgłosić: uszkodzony plik albo Python starszy niż 3.9. Sprawdź `python3 --version`, `python3 abuseipdb_report.py --version` i `git status` (ręcznie edytowany plik) |
| `journalctl returned code ... new SSH logins may be MISSING from the auto-trust` | użytkownik usługi nie czyta całego dziennika (albo `journalctl` nie ma `--grep`); dodaj go do grupy `adm` lub `systemd-journal` (`sudo usermod -aG systemd-journal <user>`, potem zaloguj się ponownie) i sprawdź `journalctl -u ssh --grep Accepted` |
| `[SAFEGUARD-OFF] could not read the SSH logs` przy każdym przebiegu | nie ma `journalctl` albo działającego journald (kontener, host bez systemd): auto-zaufanie używa tylko zapamiętanej listy `ssh_trusted_seen.txt`, a przy każdym przebiegu dostajesz alert o priorytecie 4, bo wrapper nie ma przełącznika, który by go wyciszył. Wpisz własne adresy jako `EXCLUDE`; narzędzie jest przeznaczone dla hostów z systemd |
| `SSH auto-trust: NO successful login found` (ostrzeżenie, bez alertu) | nikt nie logował się przez SSH w ostatnich 60 dniach albo użytkownik nie może czytać dziennika; sprawdź grupę i `journalctl -u ssh --grep Accepted` |
| `ALL N alerts were skipped because their kind is not 'crowdsec'` | wszystkie alerty pochodziły z blocklist albo twoja wersja `cscli` nie ma pola `kind`; jeśli to się powtarza codziennie, sprawdź `cscli alerts list -o json` |
| `jq is not installed` | `apt install jq` |

### Wysyłka do AbuseIPDB

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| HTTP 401 lub 403 | zły lub cofnięty klucz API; sprawdź `ABUSEIPDB_API_KEY` w `~/.secrets/abuseipdb.conf` |
| HTTP 429 (`daily limit exceeded`) | wyczerpany dzienny limit `bulk-report` (możliwe po ręcznych przebiegach); powtórek nie ma, poczekaj na czas z `Retry-After`; następny zaplanowany przebieg pokryje to samo okno |
| HTTP 422 | zniekształcone CSV; szczegół z API jest w logu; uruchom `python3 abuseipdb_report.py --validate reports.csv` |
| `upload to AbuseIPDB failed after 3 attempts` | błąd sieci, timeout albo HTTP 5xx; wrapper czekał 60 s, potem 120 s między próbami; następny przebieg spróbuje to samo okno. Jeśli się powtarza, sprawdź sieć hosta i stan AbuseIPDB |
| `file ... failed validation ... NOT sending` | linie `validation:` powyżej podają przyczynę; zły plik nigdy nie zastępuje poprzedniego. Jeśli przyczyna jest niejasna, otwórz issue |
| `HTTP 200 reply without the data.savedReports field` | AbuseIPDB odpowiedziało w nieoczekiwanym formacie; znacznik się nie przesunął. Jeśli się powtarza, otwórz issue |

### Alerty ntfy

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| `no ntfy topic ... alert not sent` | w pliku konfiguracji brak `NTFY_TOPIC`; alerty trafiają tylko do logu, dopóki go nie ustawisz |
| `NTFY_TOPIC has invalid characters` lub `NTFY_URL is not a plain http(s) URL` | komentarz lub zbędny znak po wartości; temat to tylko litery, cyfry, `_` i `-` |
| `NTFY_TOPIC is still the example value` | `NTFY_TOPIC` to nadal `your-private-ntfy-topic`; alerty celowo tam nie idą, ustaw własny prywatny temat |
| brak alertów, w logu `ntfy ERROR ... 429` | dzienny limit wiadomości `ntfy.sh` dla twojego adresu; wrapper wysyła już przez IPv4 (`curl -4`), bo wspólną pulę IPv6 łatwo wyczerpać. Sprawdź treść odpowiedzi (`code 42908` = limit dzienny). Lepiej postawić własny ntfy (`NTFY_URL`); na hoście tylko z IPv6 jedyną inną drogą jest usunięcie `-4` z `abuseipdb_send.sh`, a ręcznie edytowany plik sprawia, że `git pull --ff-only` odmawia |

### Okno, blokada i strażnik

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| `previous run is still in progress` | inny przebieg trzyma blokadę. Blokada należy do działającego procesu (`flock`) i znika, gdy on się kończy; skasowanie pliku jej nie zwalnia i mogłoby dopuścić dwa przebiegi naraz. Sprawdź `pgrep -af abuseipdb_send`; jeśli ten przebieg się zawiesił, zatrzymaj sam proces |
| `skipping: last report was ... ago` | strażnik 20 h; normalne po ręcznym przebiegu |
| `watermark from the future` | rozjazd zegara; sprawdź `timedatectl`, potem świadomie popraw lub usuń znacznik |

### Dlaczego coś zostało lub nie zostało zgłoszone

| Objaw | Prawdopodobna przyczyna i naprawa |
|---|---|
| brakuje atakującego, którego się spodziewasz | uruchom dry-run i przeczytaj linie `[filter] skipped`: alert może być starszy niż 60 dni, z adresu zaufanego przez SSH albo z `EXCLUDE`, z wykluczonego scenariusza, spoza okna albo nie być lokalnym wykryciem |
| w logu `unknown scenario <autor/nazwa> - not reported` | kolekcja CrowdSeca, którą zainstalowano (albo scenariusz innego autora), nie ma znanej kategorii, więc jego alerty są celowo pomijane. To normalne po `cscli collections install`. Zgłoś nazwę scenariusza w issue; nie edytuj `CATEGORY_MAP` na serwerze, bo to psuje `git pull --ff-only` |
| adresy z subskrybowanej blocklisty nie są zgłaszane | tak ma być: wpisy z blocklist (`kind` `capi`, scenariusz `update : +N/-M IPs`) to cudze obserwacje, a do AbuseIPDB trafiają tylko ataki, które ten serwer sam zobaczył |
| zgłoszono jeden z twoich własnych adresów | najpierw usuń swoje zgłoszenia tego adresu w AbuseIPDB (API ma wywołanie `clear-address`, które usuwa tylko twoje własne zgłoszenia; patrz dokumentacja API AbuseIPDB, a klucz trzymaj z dala od linii poleceń i historii powłoki). Potem dopisz adres jako linię `EXCLUDE=` w `~/.secrets/abuseipdb.conf` i zbadaj, czemu auto-zaufanie SSH go nie złapało |

## Aktualizacja i wycofanie zmian

Plik konfiguracji jest sprawdzany ściśle (nieznany lub zniekształcony klucz zatrzymuje przebieg), a nowe wersje
czasem dodają klucze albo zaostrzają kontrolę, więc nie wystarczy zrobić pull i zostawić crona w spokoju.

1. W katalogu instalacji: `git pull --ff-only`. Nie edytuj tam plików ręcznie, bo pull odmówi.
2. Przeczytaj `CHANGELOG.md` od swojej starej wersji (pokazują ją `./abuseipdb_send.sh --version` i
   `python3 abuseipdb_report.py --version`) do nowej. Szukaj nowych lub przemianowanych kluczy konfiguracji i zmian w
   tym, co jest wykluczane.
3. `./abuseipdb_send.sh --dry-run`: ma się skończyć bez błędu, a CSV ma wyglądać jak dotąd. Niczego nie wysyła.
4. Po następnym zaplanowanym przebiegu sprawdź `abuseipdb_cron.log` (patrz "Lista kontrolna pierwszego przebiegu",
   punkt 4).

Żeby wycofać złe wydanie, przełącz katalog instalacji na starszą wersję, sprawdź ją i zostaw linię crona bez zmian:

```bash
git log --oneline                          # znajdź commit (tagi istnieją tylko dla niektórych wydań)
git switch --detach <commit lub tag>
./abuseipdb_send.sh --dry-run
```

Starsza wersja odrzuci klucze konfiguracji dodane przez nowszą (`unknown key`), więc na czas wycofania je usuń; pomaga
kopia pliku sprzed aktualizacji. Gdy problem zostanie naprawiony, `git switch main` i `git pull --ff-only` przywrócą
aktualną wersję. Crontab przywracaj z kopii tylko wtedy, gdy zmieniły się ścieżki.

## Sekrety i kopie zapasowe

- Cała konfiguracja to jeden plik, `~/.secrets/abuseipdb.conf` (tryb 600, katalog w trybie 700); wzór to
  `abuseipdb.conf.example`. Klucz API i temat ntfy nigdy nie pojawiają się w repozytorium, argumentach, logach ani na
  liście procesów. Plik jest parsowany jako tekst i nigdy nie jest wykonywany.
- Plik konfiguracji (wykluczenia, znaczniki własnych nazw) i lista zaufanych IP `ssh_trusted_seen.txt` to stan trudny
  do odtworzenia, chroniący przed zgłoszeniem własnego adresu. Dodaj `~/.secrets/` do własnej rutyny kopii zapasowych i
  chroń kopię tak samo jak oryginał: zawiera twój klucz API i temat ntfy.
- Jeśli klucz API wycieknie, utwórz nowy na stronie konta AbuseIPDB (link jest w `abuseipdb.conf.example`), wpisz go do
  pliku i usuń stary. Jeśli wycieknie temat ntfy, każdy może czytać twoje alerty i wysyłać fałszywe: wybierz nowy
  losowy temat i zmień `NTFY_TOPIC`.
