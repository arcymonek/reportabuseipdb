[English](../ARCHITECTURE.md) | **Polski**

Wersja: 3.6.20 (`abuseipdb_report.py`)

# Architektura

## Komponenty

| Komponent | Rola |
|---|---|
| `abuseipdb_report.py` | Buduje i waliduje CSV do zgłoszeń zbiorczych z lokalnych alertów CrowdSeca. Nigdy nie używa sieci. |
| `abuseipdb_send.sh` | Wrapper crona: wybór okna, wywołanie generatora, druga walidacja, wysyłka, kontrola odpowiedzi API, alerty, znacznik. |
| `tests/` | Testy jednostkowe i end-to-end (Python `unittest`, atrapy `curl`, generatora i `ntfy`). |
| `tools/pre-commit` | Hook repozytorium: kontrola składni, reguła parowania dokumentacji EN/PL, reguły wersji i skan prywatności. |
| `AGENTS.md` | Zasady dla agentów AI: bezpieczniki, czego nigdy nie robić, konwencje. Tylko po angielsku. |
| zewnętrzny monitor (opcjonalny) | Poza tym repozytorium. Co godzinę sprawdza, czy znacznik nie jest starszy niż 36 h. |

## Przepływ danych

1. Cron uruchamia `abuseipdb_send.sh` raz na dobę. `flock` na `.state/abuseipdb-send.lock` zapobiega nakładaniu się
   przebiegów.
2. Wrapper czyta znacznik `.state/abuseipdb_last_ok` (epoch w sekundach końca ostatniego udanego okna). Bez znacznika
   oknem jest ostatnie 24 h.
3. Okno `(AFTER, NOW]`: `AFTER` to znacznik, `NOW` to bieżący czas. Oba trafiają do generatora jako `--after` /
   `--before`, a generator filtruje alerty po ich `created_at`. Przedział jest półotwarty, więc kolejne okna mają
   wspólną granicę i nigdy się nie nakładają.
4. Generator wywołuje `sudo -n cscli alerts list -o json` (`cscli` bezpośrednio jako root), odrzuca wszystko, czego nie wolno zgłaszać (patrz
   [COMPLIANCE.md](COMPLIANCE.md)), grupuje alerty per IP i buduje jeden wiersz CSV na IP.
5. Generator sam waliduje plik i podmienia `reports.csv` atomowo (zapis do `reports.csv.tmp`, walidacja,
   `os.replace`).
6. Wrapper uruchamia `abuseipdb_report.py --validate reports.csv` jako niezależną drugą kontrolę.
7. Wrapper wysyła plik przez `curl` (`Accept: application/json`, klucz API przez stdin) i sprawdza status HTTP oraz
   treść JSON (`savedReports`, `invalidReports`).
8. Dopiero po poprawnej odpowiedzi znacznik jest ustawiany na koniec okna. Odrzucone wiersze (zły IP lub kategoria)
   nie zmieniłyby się przy ponownej wysyłce, więc w tym przypadku znacznik też się przesuwa, z alertem.

## Okna czasowe i znacznik

- Znacznik to **koniec** okna (`--before`), a nie czas zakończenia przebiegu. Alerty utworzone w trakcie przebiegu
  trafiają więc do następnego okna zamiast do luki.
- Po awarii następny przebieg nadrabia najwyżej 48 h wstecz (`MAX_LOOKBACK_H`); dłuższa luka jest ucinana i zgłaszana.
- Przebieg wykonany krócej niż 20 h po poprzednim sukcesie jest pomijany (`MIN_INTERVAL_H`); `--force` omija blokadę.
- Uszkodzony znacznik powoduje powrót do domyślnego okna 24 h z alertem; znacznik z przyszłości jest błędem.

## Pliki stanu i danych

| Ścieżka | Właściciel | Uwagi |
|---|---|---|
| `.state/abuseipdb_last_ok` | wrapper | znacznik, epoch w sekundach, zapisywany tylko po udanym przebiegu |
| `.state/abuseipdb-send.lock` | wrapper | plik blokady `flock` |
| `reports.csv`, `reports.csv.tmp` | generator | kasowane przez wrapper przed każdym prawdziwym przebiegiem, żeby nieaktualny plik nigdy nie został wysłany |
| `abuseipdb_cron.log` | cron | przycinany w miejscu przez wrapper do około 2000 linii |
| `~/.secrets/abuseipdb.conf` | operator | jedyny plik konfiguracji, tryb 600, tekst `KEY=value` nigdy nie wykonywany: `ABUSEIPDB_API_KEY` (nigdy w argumentach ani logach), `NTFY_TOPIC` (do `curl` przez stdin), `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE`, `HTTP_PORTS`, `EXTRA_EXCLUDE_SCENARIOS` |
| `~/.secrets/abuseipdb_api_key`, `ntfy_topic`, `abuseipdb_exclude.txt` | operator | przestarzały zapas na czas migracji; config ma pierwszeństwo, wykluczenia z obu źródeł są łączone |
| `~/.secrets/ssh_trusted_seen.txt` | generator | zaufane adresy SSH, tryb 600, wpisy wygasają po 60 dniach |

## Kody wyjścia

| Program | Kod | Znaczenie |
|---|---|---|
| `abuseipdb_report.py` | 0 | plik zapisany (albo dry-run / walidacja zakończona sukcesem) |
| | 1 | brak kwalifikujących się zgłoszeń; nic nie zapisano |
| | 2 | błąd (złe argumenty, awaria cscli, nieudana walidacja, nieczytelne lub nieoczekiwane dane wejściowe, każda nieoczekiwana awaria wewnętrzna); poprzedni plik nienaruszony |
| `abuseipdb_send.sh` | 0 | sukces, pominięcie przez blokadę albo brak czego wysyłać |
| | 1 | awaria; znacznik bez zmian, następny przebieg nadrobi |
| | 2 | nieznany argument |

## Obsługa błędów

| Sytuacja | Zachowanie |
|---|---|
| błąd sieci, timeout, HTTP 5xx lub 408 | do 3 prób z rosnącymi przerwami, potem awaria i alert |
| HTTP 401, 403, 422, 429 | bez powtórek; awaria i alert (429 zawiera `Retry-After`) |
| HTTP 200 z nieoczekiwaną treścią | awaria i alert |
| niepuste `invalidReports` | alert, znacznik się przesuwa |
| zapisane + odrzucone różni się od wysłanych | alert |
| awaria generatora lub walidacji | awaria i alert, stary CSV już skasowany, nic nie wysłano |

Ponowna wysyłka tego samego pliku jest bezpieczna: AbuseIPDB scala zgłoszenia o identycznym komentarzu i
kategoriach z okna 24 h.

## Komentarz zgłoszenia

Komentarz jest składany wyłącznie ze stałych angielskich `TPL_*` w generatorze: zdanie o źródle, protokół i porty
celu, uruchomione scenariusze, liczba pasujących zdarzeń, zakres czasu w UTC oraz próbka prawdziwych żądań HTTP
(metoda, ścieżka, status). Próbka zawierająca znacznik własnej nazwy, zgłaszany IP, jeden z własnych adresów
publicznych serwera albo adres e-mail jest pomijana (ścieżki pochodzą od atakującego). Liczba zdarzeń jest zachowawcza (unikalne żądania, nigdy suma po nakładających się
scenariuszach). Tekst jest sprowadzany do ASCII, znaki sterujące są usuwane, a prefiksy formuł arkusza
neutralizowane. Cudzysłów jest zapisywany jako `%22`, a komentarz nigdy nie kończy się backslashem, bo parser CSV
AbuseIPDB traktuje backslash jako znak ucieczki; pozostałe backslashe zostają (są dowodem, np. `\x5Cthink`).

## Powiązanie z zewnętrznymi monitorami

Zewnętrzny monitor może czytać `abuseipdb_send.sh` i `.state/abuseipdb_last_ok` z katalogu instalacji. Traktuj obie
nazwy jako stabilny interfejs: zmiana którejkolwiek wymaga odpowiedniej zmiany w monitorze.

## Źródła konfiguracji

Wrapper i generator czytają ten sam plik konfiguracji (`ABUSEIPDB_CONFIG`, domyślnie `~/.secrets/abuseipdb.conf`;
wrapper przekazuje go generatorowi przez `--config`). Pierwszeństwo, od najwyższego: jawne nadpisania ze środowiska
(używane przez testy), plik konfiguracji, przestarzałe osobne pliki. Wykluczenia to zawsze suma wpisów `EXCLUDE` z
configu i starego pliku wykluczeń, nigdy zamiennik, więc migracja nie może po cichu zgubić żadnego wpisu. Znaczniki
własnych nazw działają fail-closed: przy pustej liście, albo takiej, która nadal ma wartości przykładowe z
`abuseipdb.conf.example`, generator ostrzega, a wrapper na żywo odmawia wysyłki i wysyła alert. Przykładowy
`NTFY_TOPIC` nigdy nie dostaje alertów. Config jest też sprawdzany ściśle w każdym trybie generatora (także
`--validate`): zniekształcona linia, nieznany klucz, komentarz po wartości, znacznik ze spacją lub `#` w środku albo
nieprawidłowy wpis `EXCLUDE` zatrzymują przebieg z kodem 2, bo każdy z nich wyłączyłby bezpiecznik bez śladu.
