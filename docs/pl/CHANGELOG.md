[English](../../CHANGELOG.md) | **Polski**

Wersja: 3.6.33 (`abuseipdb_report.py`)

# Historia zmian

Istotne zmiany dla osób, które uruchamiają narzędzie. Każdy wpis ma odpowiednik w [CHANGELOG.md](../../CHANGELOG.md). Format:
[Keep a Changelog](https://keepachangelog.com/). Szczegółowa historia każdego commita jest w `git log`.

Numeracja to `X.Y.Z`. Wersją projektu jest wersja `abuseipdb_report.py`. Rośnie, gdy zmienia się **program**: dwa
skrypty albo znaczenie linii w `abuseipdb.conf.example` (`Z` przy poprawce, `Y` przy nowej funkcji lub nowym kluczu
konfiguracji, `X` to świadoma decyzja). Zmiany hooków, testów, CI, szablonów i dokumentacji jej nie podnoszą; te, które
są ważne dla opiekuna i kontrybutorów, są wypisane w sekcji "Development" z datą. `abuseipdb_send.sh` ma własną wersję
(obecnie 1.1.7) i podlega tej samej regule.

## Niewydane

- Na razie nic.

## Development

Hooki, testy, CI i pliki GitHuba. Bez numeru wersji: te zmiany nie wpływają na to, co działa na twoim serwerze.

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
  `abuseipdb.conf.example`). Stare pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` nadal działają jako
  przestarzały zapas; konfiguracja ma pierwszeństwo. Po migracji usuń stare pliki.
- **`OWN_NAME_MARKERS` jest wymagane do przebiegu na żywo.** Wysyłka na żywo jest odmawiana, dopóki lista jest pusta
  albo zawiera wartości przykładowe. Próba bez wysyłki (dry-run) tylko ostrzega.
- **Konfiguracja jest sprawdzana ściśle.** Nieznany klucz, zniekształcona linia, komentarz po wartości albo niepoprawny
  wpis `EXCLUDE` zatrzymuje przebieg (kod wyjścia 2) zamiast być pomijany. Komentarze pisz w osobnych liniach.
  Konfiguracja, która istnieje, ale nie da się jej odczytać (uprawnienia, nie UTF-8), też zatrzymuje przebieg.
- **Nieznane scenariusze CrowdSeca nie są już zgłaszane** (wcześniej jako "hacking"). Zgłaszane są tylko scenariusze
  `crowdsecurity` z `CATEGORY_MAP` albo nazwane od CVE; scenariusz innego autora wymaga wpisu pod pełną nazwą.
- **Logowania SSH z IPv6 zaufają całej sieci /64** (`SSH_TRUST_IPV6_PREFIX`, domyślnie 64; ustaw 128 dla dokładnego
  adresu, np. u dostawcy hostingu, który dzieli jeden /64 między klientów). IPv4 jest zawsze dokładne.
- Po aktualizacji uruchom `./abuseipdb_send.sh --dry-run` i przejrzyj CSV.

### Dodano

- Klucze konfiguracji: `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE` (powtarzalny), `HTTP_PORTS` (domyślnie `80/443`),
  `EXTRA_EXCLUDE_SCENARIOS`, `SSH_TRUST_IPV6_PREFIX`; `--config` i `ABUSEIPDB_CONFIG`; `--version`.
- Wrapper: `ALERT_LIMIT` (zmienna w linii crontab) podnosi liczbę czytanych alertów; nowe alerty ntfy "data cut off" i
  "safeguard not working".
- Auto-zaufanie SSH rozpoznaje logowania `keyboard-interactive/<urządzenie>`, `hostbased` i `gssapi-*` oraz czyta
  journal zarówno `ssh`, jak i `sshd`.

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
- Python 3.9 i 3.10 poprawnie czytają znaczniki czasu z journala i CrowdSeca (przesunięcie UTC bez dwukropka, długie
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

## 3.5 i wcześniej - 2026-09-28 i wcześniej

Rozłączne okna czasowe ze znacznikiem, 20-godzinny bezpiecznik, `Accept: application/json`, kontrole odpowiedzi HTTP i
JSON, klucz API przez stdin, ponowienia tylko przy błędach przejściowych, alerty ntfy, licznik unikalnych zdarzeń, ścisłe
dopasowanie logowań SSH, trwała lista zaufania SSH, tryb `--validate`, `http-open-proxy` zgłaszany jako kategoria 14 (9 twierdziłaby, że
zgłaszany host jest otwartym proxy).
