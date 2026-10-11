[English](../../CHANGELOG.md) | **Polski**

# Historia zmian

Istotne zmiany dla osób, które uruchamiają narzędzie. Każdy wpis ma odpowiednik w [CHANGELOG.md](../../CHANGELOG.md). Format:
[Keep a Changelog](https://keepachangelog.com/), z dwiema własnymi sekcjami: "Uwagi do aktualizacji" we wpisach wersji i
"Development" na końcu pliku. Szczegółowa historia każdego commita jest w `git log`.

Projekt ma jedną wersję `X.Y.Z`, wspólną dla obu skryptów (pokazuje ją `--version`). Rośnie tylko wtedy, gdy zmienia się
**program**: `Z` przy poprawce, `Y` przy nowej funkcji lub nowym kluczu konfiguracji. Pełne zasady są w
[DEVELOPMENT.md](DEVELOPMENT.md#wersjonowanie). Nie każda wersja jest wydaniem: wersje, które opiekun oznaczy tagiem git,
pojawiają się jako [GitHub Releases](https://github.com/arcymonek/reportabuseipdb/releases), a każdy Release zawiera
wszystkie wpisy nowsze niż poprzedni Release.

## Niewydane

- Na razie nic.

## 3.6.34 - 2026-10-04

### Zmieniono

- Przestarzałe osobne pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` nie są już czytane, a opcja
  `--exclude-file` w `abuseipdb_report.py` zniknęła. Wszystkie lokalne ustawienia pochodzą wyłącznie z
  `~/.secrets/abuseipdb.conf` (klucze `ABUSEIPDB_API_KEY`, `NTFY_TOPIC` i wpisy `EXCLUDE`). Generowane CSV się nie zmienia.

### Uwagi do aktualizacji

- Jeśli nadal używasz któregoś ze starych plików, przenieś jego zawartość do `~/.secrets/abuseipdb.conf` **przed**
  aktualizacją: inaczej zabraknie klucza API lub tematu ntfy, a adresy ze starego pliku wykluczeń staną się zgłaszalne.

## 3.6.33 - 2026-10-02

### Zmieniono

- Linia w logu o scenariuszu CrowdSeca bez znanej kategorii (`unknown scenario ... - not reported`) prosi teraz o
  otwarcie issue z nazwą scenariusza, zamiast sugerować edycję `CATEGORY_MAP` na twoim serwerze. Edycja śledzonego kodu
  psuje `git pull --ff-only`, a opiekun sprawdza, co scenariusz wykrywa, zanim trafi do publicznej bazy. Generowane CSV
  się nie zmienia. Przy aktualizacji nie trzeba nic robić.

## 3.6.32 - 2026-10-01

Pierwsza wersja przygotowana pod publiczne repozytorium. Zbiera wszystkie zmiany od 3.6.0 (2026-09-28).

### Uwagi do aktualizacji

- **Utwórz jeden plik konfiguracji.** Wszystkie lokalne ustawienia są teraz w `~/.secrets/abuseipdb.conf` (skopiuj
  `abuseipdb.conf.example`). W 3.6.32 stare pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` nadal
  działają jako przestarzały zapas (konfiguracja ma pierwszeństwo), ale od 3.6.34 nie są już czytane: przenieś ich
  zawartość do konfiguracji i usuń je.
- **`OWN_NAME_MARKERS` jest wymagane do przebiegu na żywo.** Wysyłka na żywo jest odmawiana, dopóki lista jest pusta
  albo zawiera wartości przykładowe. Próba bez wysyłki (dry-run) tylko ostrzega.
- **Konfiguracja jest sprawdzana ściśle.** Nieznany klucz, zniekształcona linia, komentarz po wartości albo niepoprawny
  wpis `EXCLUDE` zatrzymuje przebieg (kod wyjścia 2) zamiast być pomijany. Komentarze pisz w osobnych liniach.
  Konfiguracja, która istnieje, ale nie da się jej odczytać (uprawnienia, nie UTF-8), też zatrzymuje przebieg.
- **Nieznane scenariusze CrowdSeca nie są już zgłaszane** (wcześniej jako "hacking"). Zgłaszane są tylko scenariusze
  `crowdsecurity` z `CATEGORY_MAP` albo nazwane od CVE; scenariusz innego autora wymaga wpisu pod pełną nazwą.
- **Logowania SSH z IPv6 zaufają całej sieci /64** (`SSH_TRUST_IPV6_PREFIX`, domyślnie 64, dozwolone 64-128, inna
  wartość zatrzymuje przebieg; ustaw 128 dla dokładnego adresu, np. u dostawcy hostingu, który dzieli jeden /64 między
  klientów). IPv4 jest zawsze dokładne.
- Po aktualizacji uruchom `./abuseipdb_send.sh --dry-run` i przejrzyj CSV.

### Dodano

- Klucze konfiguracji: `ABUSEIPDB_API_KEY`, `NTFY_TOPIC`, `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE` (powtarzalny),
  `HTTP_PORTS` (domyślnie `80/443`), `EXTRA_EXCLUDE_SCENARIOS`, `SSH_TRUST_IPV6_PREFIX`; `--config` i
  `ABUSEIPDB_CONFIG`; `--version`.
- Wrapper: `ALERT_LIMIT` (zmienna w linii crontab, liczba od 1 do 9999999, domyślnie 5000) podnosi liczbę czytanych
  alertów; nowe alerty ntfy "data cut off" i "safeguard not working".
- Auto-zaufanie SSH rozpoznaje logowania `keyboard-interactive/<urządzenie>`, `hostbased` i `gssapi-*` oraz czyta
  dziennik systemowy zarówno `ssh`, jak i `sshd`.

### Zmieniono

- Alerty do ntfy idą przez IPv4 (`curl -4`) i nie zawierają już ścieżki instalacji ani katalogu domowego.
- Pobieranie z `cscli` sięga godzinę przed okno, więc alert, który zaczyna się przed granicą, a powstaje wewnątrz okna,
  nie ginie.
- `ReportDate` i wszystkie czasy są przeliczane na UTC; adresy mają jeden kanoniczny zapis (skompresowane IPv6, adresy
  IPv4 zmapowane do IPv6 jako zwykłe IPv4).
- Próbka żądania zawierająca własną nazwę, zgłaszane IP, jeden z własnych adresów serwera albo adres e-mail jest
  pomijana w komentarzu (także zapisana procentowo), zamiast blokować cały plik.

### Naprawiono

- Awaria generatora nie wygląda już jak "brak kwalifikujących się zgłoszeń": każdy nieoczekiwany błąd kończy się kodem 2,
  a wrapper ufa kodowi 1 tylko razem z jego komunikatem. Wcześniej taka awaria mogła po cichu zamknąć okno czasowe.
- Python 3.9 i 3.10 poprawnie czytają znaczniki czasu z dziennika systemowego i CrowdSeca (przesunięcie UTC bez dwukropka, długie
  ułamki sekund).
- Ścieżka z przecinkiem lub średnikiem nie psuje już wysyłki (ścieżka w `curl -F` jest ujęta w cudzysłów).
- `--limit 0` nie wywołuje już fałszywego alertu "data cut off".

### Bezpieczeństwo

- Wartości parametrów zapytania wyglądających na dane uwierzytelniające (`token`, `key`, `password`, `session`, `jwt` i
  podobne) są zastępowane przez `***` w próbkach żądań (najlepsza próba, nie gwarancja).
- Cudzysłów w próbce jest zapisywany jako `%22`, a komentarz nigdy nie kończy się ukośnikiem odwrotnym (parser CSV
  AbuseIPDB traktuje go jako znak ucieczki).
- Kontrole własnych nazw, zgłaszanego IP i e-maili sprawdzają także tekst zdekodowany z zapisu procentowego.
- Scenariusz nazwany od CVE jest zaufany tylko dla autora `crowdsecurity`.

## 3.5 i wcześniej

Wersje sprzed wydzielenia projektu do własnego repozytorium (2026-09-28). Najważniejsze cechy:

- Rozłączne okna czasowe ze znacznikiem i 20-godzinny bezpiecznik.
- `Accept: application/json`, kontrole odpowiedzi HTTP i JSON, klucz API przez stdin, ponowienia tylko przy błędach
  przejściowych.
- Alerty ntfy i licznik unikalnych zdarzeń.
- Ścisłe dopasowanie logowań SSH i trwała lista zaufania SSH.
- Tryb `--validate`.
- `http-open-proxy` zgłaszany jako kategoria 14 (9 twierdziłaby, że zgłaszany host jest otwartym proxy).

## Development

Hooki, testy, CI, pliki GitHuba i dokumentacja. Bez numeru wersji: te zmiany nie wpływają na to, co działa na twoim serwerze.

- 2026-10-11 - Dokumentacja: drobne poprawki spójności po przepisaniu. `docs/pl/COMPLIANCE.md` mówi teraz, że końcowy
  backslash komentarza zamienia się na `%5C`, a ten, który zostanie po obcięciu do 1024 bajtów, jest usuwany, i nie
  podaje już liczby bezpieczników. README mówi, że `--dry-run` pokazuje tylko kilka przykładowych wierszy, i
  wskazuje, gdzie jest cały CSV. `CONTRIBUTING.md` wymienia przedrostek gałęzi `docs-`, a `docs/pl/DEVELOPMENT.md`
  zaznacza, że `EN_ONLY=1` służy też opiekunowi do poprawki jednej strony. Żaden bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: `SECURITY.md` został napisany od nowa i sprawdzony względem kodu. Na początku jest zgłaszanie
  (prywatne zgłoszenie na GitHubie albo e-mail, po polsku lub angielsku, co dołączyć, bez żywych wysyłek na próbę).
  Nowe: "Co nie jest podatnością" (dostęp do konta usługi, znane ograniczenia maskowania, konfiguracja niezgodna z
  listą przed uruchomieniem, fałszywe alarmy scenariuszy CrowdSeca, błędy w innym oprogramowaniu), czego się
  spodziewać po zgłoszeniu oraz jak poprawki trafiają na `main` i do wydań. Lista podatności nie wymienia już CDN
  (narzędzie nie potrafi go rozpoznać), a obejmuje adresy podsunięte z zewnątrz i treść alertów ntfy. Żaden
  bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: `docs/OPERATIONS.md` został uporządkowany według życia instalacji (nowa sekcja "Jak
  czytać wynik dry-run", diagnostyka podzielona na sześć małych tabel, wycofanie zmian obok aktualizacji) i poprawiony
  względem kodu: co `--dry-run` sprawdza, a czego nie, jak wygląda spokojny dzień w logu, skutek uboczny `--force` dla
  następnego zaplanowanego przebiegu, skąd próg monitora 36 h, priorytety alertów, test `sudo -n cscli alerts list
  --limit 1`, czym naprawdę jest blokada, jak wycofać wydanie i wszystkie klucze konfiguracji, które zatrzymują
  generator. Dodano brakujące komunikaty (brak tematu ntfy, brak dziennika systemowego, awarie wysyłki) i kroki po
  zgłoszeniu własnego adresu. Żaden bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: `docs/DEVELOPMENT.md` został uporządkowany (najpierw część dla każdego, potem workflow
  opiekuna; nowe sekcje "Przygotowanie środowiska", "Hooki" i "Stałe kontrole") i poprawiony względem kodu: co naprawdę
  sprawdza każdy hook (`commit-msg` skanuje tylko wzorzec klucza i `OWN_NAME_MARKERS`), krok `shellcheck` w CI, oba
  workflow przypinające `actions/checkout`, `--force-with-lease` po rebase gałęzi roboczej, wdrożenie po każdym pushu
  oraz to, że opublikowanego tagu i Release nie da się cofnąć. `docs/ARCHITECTURE.md` opisuje `commit-msg` tak samo.
  Żaden bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: `CONTRIBUTING.md` został uporządkowany (tabela "dokąd z czym", przygotowanie i testy przed
  krokami wysyłania zmiany) i poprawiony: propozycje i pytania idą do Discussions, błędy i nieznane scenariusze do
  Issues; dopisano regułę Pythona 3.9 i samej biblioteki standardowej, drugi hook (`commit-msg`), powód użycia publicznych
  resolverów w testach oraz to, że gałąź po rebase wypycha się przez `--force-with-lease`. Szablon pull requesta i
  `AGENTS.md` idą w ślad za tym. Żaden bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: `docs/pl/ARCHITECTURE.md` został przepisany zgodnie z kodem (okno bez zgłoszeń, alerty
  `[TRUNCATED]` i `[SAFEGUARD-OFF]`, uszkodzony znacznik, kontrole konfiguracji), a jego tabela błędów pokazuje teraz,
  co dzieje się ze znacznikiem w każdej sytuacji. Odsyła do COMPLIANCE.md i OPERATIONS.md zamiast je powtarzać. Żaden
  bezpiecznik się nie zmienił.
- 2026-10-11 - Dokumentacja: README jest krótsze i jaśniejsze (ponumerowany szybki start, bezpieczniki po jednej linii,
  zaproszenie dla kontrybutorów), projekt opisany jako ukończony, a wyjaśnienie kontroli przed uruchomieniem na żywo
  przeniesiono do [OPERATIONS.md](OPERATIONS.md#przed-pierwszym-przebiegiem-na-żywo). Żaden bezpiecznik się nie zmienił.
- 2026-10-08 - Nowy skrypt opiekuna `tools/deploy-check.sh`: po pushu lub wdrożeniu pobiera `origin` i `github` i pokazuje,
  czy lokalny `main` oraz oba zdalne repozytoria stoją na tym samym commicie (jeszcze niewypchnięty, wyprzedzony,
  rozbieżny, zła kolejność pushy). Tylko odczyt, tryb offline z `--no-fetch`, nigdy nie wypisuje adresu zdalnego
  repozytorium. Ma testy, a CI sprawdza teraz jego składnię i uruchamia na nim `shellcheck`.
- 2026-10-08 - Hook pre-commit uruchamia testy generatora (około 15 s), gdy commit zmienia `abuseipdb_report.py` albo jego
  plik testów. Testuje kopię indeksu, a nie katalog roboczy, i pomija testy po wcześniejszym błędzie; `NO_TESTS=1`
  pomija tylko je (dla commitów roboczych opiekuna). Zachowanie hooka ma testy.
- 2026-10-08 - Workflow testów ma 10-minutowy limit czasu zadania (domyślnie 6 godzin), a `actions/checkout` nie zostawia
  już tokenu GitHuba w `.git/config` (`persist-credentials: false`).
- 2026-10-02 - Uproszczone wersjonowanie: jedna wersja dla obu skryptów (wrapper przejmuje wersję generatora, więc
  `abuseipdb_send.sh --version` pokazuje teraz wersję projektu zamiast 1.1.7), `Z` nie ma górnej granicy (bez przeskoku
  przy 99), dokumenty nie mają już linii "Wersja:", a hook pre-commit przyjmuje krok `Y` lub `X`, który wcześniej odrzucał.
- 2026-10-02 - Tagi i GitHub Releases: tag wersji `vX.Y.Z` wypchnięty na GitHub uruchamia `.github/workflows/release.yml`,
  który sprawdza tag względem kodu i changeloga i tworzy Release (notatki buduje `tools/release_notes.sh`).
- 2026-10-02 - Test potwierdza, że alerty z blocklist społeczności (`kind` `capi`) nigdy nie są zgłaszane.
- 2026-10-01 - Polskie wersje `CHANGELOG`, `CONTRIBUTING`, `SECURITY` i `CODE_OF_CONDUCT` przeniesione z katalogu głównego
  do `docs/pl/` (jako `docs/pl/X.md`); `README.pl.md` zostaje w katalogu głównym. Hook pre-commit i testy uwzględniają
  nowe pary.
- 2026-10-01 - Hook pre-commit pilnuje pary EN/PL pliku `CODE_OF_CONDUCT.md`; reguła parowania ma teraz testy.
- 2026-10-01 - Kodeks postępowania (Contributor Covenant 2.1, z nieoficjalnym tłumaczeniem na polski) i szablon pull requestu.
- 2026-10-01 - Akcje CI są przypięte do skrótów commitów; sprawdzanie nowszych wersji jest ręczne (patrz
  `docs/pl/DEVELOPMENT.md`).
- 2026-10-01 - Hooki prywatności: zamknięta dziura (nazwa hosta pod domeną autora przechodziła skan), nowy hook
  `tools/commit-msg` skanuje komunikaty commitów, reguły są w `tools/lib-privacy.sh`, a hooki mają testy.
- 2026-10-01 - Testy wbudowanego wykluczenia scenariusza, cięcia przy 8 MB i `ReportDate` z przyszłości.
- 2026-09-30 - Formularze zgłoszenia błędu i Discussions; CI działa przy pushach na `main` i na pull requestach, na
  przypiętym `ubuntu-24.04`; workflow gałęzi dla kodu (patrz `docs/pl/DEVELOPMENT.md`); `AGENTS.md` dla agentów AI;
  `EN_ONLY=1` pozwala commitować kontrybutorom piszącym tylko po angielsku.
- 2026-09-29 - `CONTRIBUTING.md`, `SECURITY.md`, workflow CI (Python 3.9 i najnowszy Python, `shellcheck`).
- 2026-09-28 - Hook pre-commit: kontrola składni, reguła parowania EN/PL, reguły wersji i skan prywatności.
