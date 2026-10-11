[English](../ARCHITECTURE.md) | **Polski**

# Architektura

Ten dokument opisuje, jak program działa: kolejność kroków, stan, kody wyjścia i zachowanie przy błędach. Reguły
AbuseIPDB i bezpieczniki są w [COMPLIANCE.md](COMPLIANCE.md), obsługa (cron, alerty, diagnostyka) w
[OPERATIONS.md](OPERATIONS.md), a praca nad kodem w [DEVELOPMENT.md](DEVELOPMENT.md).

## Komponenty

### Na serwerze

| Komponent | Rola |
|---|---|
| `abuseipdb_report.py` | Buduje i waliduje CSV do zgłoszeń zbiorczych z lokalnych alertów CrowdSeca. Nie łączy się z AbuseIPDB ani z Internetem (z CrowdSecem rozmawia przez `cscli`). |
| `abuseipdb_send.sh` | Wrapper crona: wybór okna, wywołanie generatora, druga walidacja, wysyłka, kontrola odpowiedzi API, alerty, znacznik. |
| zewnętrzny monitor (opcjonalny) | Poza tym repozytorium. Co godzinę sprawdza, czy znacznik jest świeży (patrz [OPERATIONS.md](OPERATIONS.md#monitoring)). |

### W repozytorium

| Komponent | Rola |
|---|---|
| `tests/` | Testy jednostkowe i end-to-end (Python `unittest`; wrapper jest testowany z atrapami `curl`, generatora i `ntfy`, bez sieci) oraz testy hooków, wersjonowania i narzędzi. |
| `tools/pre-commit` | Hook repozytorium: kontrola składni, reguła parowania dokumentacji EN/PL, reguły wersji, skan prywatności i testy generatora. |
| `tools/commit-msg` | Hook repozytorium: wzorzec klucza API i skan `OWN_NAME_MARKERS` zastosowane do komunikatu commita, który też jest publikowany. |
| `tools/lib-privacy.sh` | Reguły prywatności wspólne dla obu hooków (wczytywany, nie jest hookiem). |
| `tools/deploy-check.sh` | Narzędzie opiekuna: sprawdza (tylko odczyt), czy lokalny `main`, `origin` i `github` stoją na tym samym commicie. |
| `tools/release_notes.sh` | Buduje notatki wydania z `CHANGELOG.md`. |
| `.github/workflows/tests.yml` | CI: uruchamia cały zestaw testów na Ubuntu z najstarszym i najnowszym wspieranym Pythonem przy każdym pushu na `main` i każdym pull requeście. |
| `.github/workflows/release.yml` | Po wypchnięciu tagu `vX.Y.Z` na GitHub sprawdza tag względem kodu i changeloga i tworzy Release. |
| `AGENTS.md` | Zasady dla agentów AI: bezpieczniki, czego nigdy nie robić, konwencje. Tylko po angielsku. |

## Przepływ danych

1. Cron uruchamia `abuseipdb_send.sh` raz na dobę. Wrapper zakłada blokadę `flock` na `.state/abuseipdb-send.lock`;
   drugi równoległy przebieg kończy się od razu kodem 0 z wpisem w logu (bez alertu). Potem przycina log i sprawdza,
   czy jest `jq`.
2. Wrapper odmawia żywej wysyłki, gdy `OWN_NAME_MARKERS` jest puste albo ma wartości przykładowe (patrz
   [Konfiguracja](#konfiguracja)); `--dry-run` tylko ostrzega.
3. Wrapper czyta znacznik (watermark) `.state/abuseipdb_last_ok`: epoch w sekundach końca ostatniego udanego okna.
   Bez znacznika oknem jest ostatnie 24 h.
4. Okno `(AFTER, NOW]`: `AFTER` to znacznik, `NOW` to bieżący czas. Oba trafiają do generatora jako `--after` /
   `--before`, a generator filtruje alerty po ich `created_at`. Przedział jest półotwarty, więc kolejne okna mają
   wspólną granicę i nigdy się nie nakładają. Do `cscli` idzie dodatkowo `--since` szersze o godzinę
   (`SINCE_MARGIN_S`), bo `cscli` filtruje po starcie alertu, a wolny alert jest tworzony dopiero po swoim starcie
   (mierzono do ok. 2 minut); dokładne okno i tak tnie generator.
5. Generator sprawdza konfigurację, wywołuje `sudo -n cscli alerts list -o json` (`cscli` bezpośrednio, gdy działa
   jako root; domyślny limit to 5000 alertów), odczytuje z dziennika systemowego udane logowania SSH (poza
   `--dry-run` zapisuje je też w `ssh_trusted_seen.txt`), ustala własne adresy publiczne serwera (`ip addr`) i
   odrzuca wszystko, czego nie wolno zgłaszać (patrz [COMPLIANCE.md](COMPLIANCE.md)). Resztę grupuje per IP w jeden
   wiersz CSV na IP.
6. Generator sam waliduje plik i podmienia `reports.csv` atomowo (zapis do `reports.csv.tmp`, walidacja,
   `os.replace`).
7. Wrapper uruchamia `abuseipdb_report.py --validate reports.csv` jako drugą kontrolę: ten sam walidator, osobne
   uruchomienie na gotowym pliku.
8. Tuż przed wysyłką wrapper sprawdza klucz API (jest, nie jest wartością przykładową, ma poprawny format), po czym
   wysyła plik przez `curl` (`Accept: application/json`, klucz przez stdin) i sprawdza status HTTP oraz treść JSON
   (`savedReports`, `invalidReports`).
9. Dopiero po poprawnej odpowiedzi znacznik jest ustawiany na koniec okna. Odrzucone wiersze (zły IP lub kategoria)
   nie zmieniłyby się przy ponownej wysyłce, więc w tym przypadku znacznik też się przesuwa, z alertem.

Gdy po filtrach nie zostaje żaden wiersz, generator nie tworzy pliku, wypisuje `No qualifying reports` i kończy się
kodem 1. Wrapper uznaje wtedy okno za zamknięte: przesuwa znacznik i kończy się kodem 0, bez wysyłki i bez alertu.

`--dry-run` generuje i sprawdza plik, ale niczego nie wysyła: CSV trafia do pliku tymczasowego (`reports.csv` zostaje),
znacznik i lista zaufanych IP się nie zmieniają, a alerty ntfy są tylko wypisywane. Tworzy jednak katalog `.state/` i
plik blokady oraz przycina log. `--force` omija wyłącznie strażnika 20 h. Użycie: [README](../../README.pl.md#użycie),
procedury: [OPERATIONS.md](OPERATIONS.md).

## Okna czasowe i znacznik

- Znacznik to **koniec** okna (`--before`), a nie czas zakończenia przebiegu. Alerty utworzone w trakcie przebiegu
  trafiają więc do następnego okna zamiast do luki.
- Po awarii następny przebieg nadrabia najwyżej 48 h wstecz (`MAX_LOOKBACK_H`); dłuższa luka jest ucinana i zgłaszana,
  a starsze alerty przepadają.
- Przebieg wykonany krócej niż 20 h po poprzednim sukcesie jest pomijany (`MIN_INTERVAL_H`; wytyczna AbuseIPDB mówi o
  zgłaszaniu tego samego IP mniej więcej raz na dobę). `--force` omija strażnika.
- Uszkodzony znacznik powoduje powrót do domyślnego okna 24 h z alertem; w tym przebiegu strażnik 20 h nie działa
  (nie ma wiarygodnego czasu ostatniego sukcesu), a plik zostaje nadpisany po następnym sukcesie. Znacznik z
  przyszłości (rozjazd zegara) jest błędem w każdym przebiegu, dopóki ktoś go nie poprawi ręcznie.
- Znacznik przesuwa się po poprawnej odpowiedzi API, także gdy część wierszy odrzucono, oraz gdy nie było czego
  wysyłać. Przy awarii zostaje bez zmian, więc następny przebieg nadrabia to samo okno. Tabela w sekcji
  [Obsługa błędów](#obsługa-błędów) podaje to dla każdej sytuacji.

## Konfiguracja

Wrapper i generator czytają ten sam plik (`~/.secrets/abuseipdb.conf`; inną ścieżkę ustawia `ABUSEIPDB_CONFIG`,
a generatorowi także `--config`, które wrapper zawsze mu przekazuje). Plik jest czytany jako tekst `KEY=value` i nigdy
nie jest wykonywany. Klucze opisuje [README](../../README.pl.md#konfiguracja) i `abuseipdb.conf.example`.
Wykluczenia pochodzą wyłącznie z wpisów `EXCLUDE` w configu. Zmienne środowiskowe wrappera (np. `CURL_BIN`,
`RETRIES`) służą testom; tam, gdzie to samo ustawienie jest też w pliku (np. `NTFY_URL`), wygrywa zmienna. Cron ich nie
ustawia, poza opcjonalnym `ALERT_LIMIT` (patrz [OPERATIONS.md](OPERATIONS.md#alerty)).

Config jest sprawdzany ściśle w każdym trybie generatora (także `--validate`). Przy błędzie generator kończy się
kodem 2, bo każdy taki błąd po cichu wyłączyłby bezpiecznik. Zatrzymuje go:
- zniekształcona linia, nieznany klucz (literówka) albo komentarz po wartości,
- wartość w złym formacie lub poza zakresem (np. `EXCLUDE`, `HTTP_PORTS`, `EXTRA_EXCLUDE_SCENARIOS`,
  `SSH_TRUST_IPV6_PREFIX`, znacznik własnej nazwy ze spacją lub `#`),
- plik, który istnieje, ale nie da się go przeczytać (uprawnienia, kodowanie).

**Brak** pliku jest łagodniejszy: generator tylko o tym informuje, a wrapper i tak nie wyśle niczego, bo lista
znaczników własnych nazw jest wtedy pusta. Komunikaty i naprawa: [OPERATIONS.md](OPERATIONS.md#diagnostyka).

Znaczniki własnych nazw działają zasadą „odmów, gdy brakuje danych” (fail closed). Pusta lista wyłącza kontrolę, że
komentarz nie zdradza nazw operatora, więc żywy przebieg wrappera kończy się awarią z alertem, a wartości przykładowe z
`abuseipdb.conf.example` są traktowane tak samo jak pusta lista. Generator sam ostrzega tylko przy pustej liście;
wartości przykładowe rozpoznaje wyłącznie wrapper. Wrapper nie użyje też przykładowego klucza API i nigdy nie wyśle
alertów na przykładowy `NTFY_TOPIC`.

## Pliki stanu i danych

| Ścieżka | Właściciel | Uwagi |
|---|---|---|
| `.state/abuseipdb_last_ok` | wrapper | znacznik, epoch w sekundach, zapisywany tylko po udanym przebiegu |
| `.state/abuseipdb-send.lock` | wrapper | plik blokady `flock` |
| `reports.csv` | generator | kasowany przez wrapper przed każdym prawdziwym przebiegiem, żeby nieaktualny plik nigdy nie został wysłany |
| `reports.csv.tmp` | generator | plik tymczasowy: znika po podmianie albo po nieudanej walidacji |
| `abuseipdb_cron.log` | cron | przycinany w miejscu przez wrapper: gdy przekroczy 2500 linii, zostaje 2000 ostatnich |
| `~/.secrets/abuseipdb.conf` | operator | jedyny plik konfiguracji, tryb 600. Klucz API nigdy nie trafia do argumentów ani logów, a adres alertów ntfy (z tematem) dociera do `curl` przez stdin |
| `~/.secrets/ssh_trusted_seen.txt` | generator | zaufane adresy SSH (pojedyncze adresy; IPv6 jest poszerzane do `SSH_TRUST_IPV6_PREFIX` przy odczycie), tryb 600, wpisy wygasają po 60 dniach |

## Obsługa błędów

| Sytuacja | Zachowanie | Alert | Znacznik |
|---|---|---|---|
| błąd sieci, timeout, HTTP 5xx lub 408 | do 3 prób, przerwy 60 s i 120 s, potem awaria | tak | bez zmian |
| inny kod HTTP niż 200 (np. 401, 403, 422, 429) | bez powtórek, awaria; przy 429 komunikat podaje `Retry-After` | tak | bez zmian |
| HTTP 200 bez pól `savedReports` / `invalidReports` | awaria | tak | bez zmian |
| niepuste `invalidReports` | wiersze odrzucone przez API; ponowna wysyłka by ich nie zmieniła | tak | przesuwa się |
| zapisane + odrzucone różni się od wysłanych | ostrzeżenie w logu | tak | przesuwa się |
| awaria generatora lub walidacji | nic nie wysłano, stary `reports.csv` już skasowany | tak | bez zmian |
| konfiguracja do odrzucenia, brak `jq`, brak lub przykładowy klucz API | awaria przed wysyłką | tak | bez zmian |
| brak kwalifikujących się zgłoszeń | nic do wysłania, kod 0 | nie | przesuwa się |
| dane obcięte przez limit (`[TRUNCATED]`: 5000 alertów z `cscli`, 10 000 wierszy, 8 MB) | przebieg trwa; obcięte alerty nie zostaną zgłoszone | tak | przesuwa się |
| bezpiecznik nie działa (`[SAFEGUARD-OFF]`, np. dziennika nie da się czytać) | przebieg trwa z pozostałymi bezpiecznikami | tak | przesuwa się |
| uszkodzony znacznik | okno 24 h, strażnik 20 h wyłączony w tym przebiegu | tak | nadpisany po sukcesie |
| luka dłuższa niż 48 h | okno ucięte do 48 h | tak | przesuwa się |
| znacznik z przyszłości | awaria | tak | bez zmian (do ręcznej poprawki) |
| poprzedni przebieg jeszcze trwa (blokada) | pominięcie, kod 0 | nie | bez zmian |
| mniej niż 20 h od ostatniego sukcesu | pominięcie, kod 0 | nie | bez zmian |

Tytuły alertów, priorytety i co robić po każdym z nich: [OPERATIONS.md](OPERATIONS.md#alerty). Ponowna wysyłka tego
samego pliku jest bezpieczna: AbuseIPDB scala zgłoszenia o identycznym komentarzu i kategoriach z okna 24 h.

## Kody wyjścia

| Program | Kod | Znaczenie |
|---|---|---|
| `abuseipdb_report.py` | 0 | plik zapisany (albo dry-run / walidacja zakończona sukcesem) |
| | 1 | brak kwalifikujących się zgłoszeń; nic nie zapisano |
| | 2 | błąd (złe argumenty, awaria cscli, zła konfiguracja, nieudana walidacja, nieczytelne lub nieoczekiwane dane wejściowe, każda nieoczekiwana awaria wewnętrzna); poprzedni plik nienaruszony |
| `abuseipdb_send.sh` | 0 | sukces, pominięcie przez blokadę lub strażnika 20 h albo brak czego wysyłać |
| | 1 | awaria; znacznik bez zmian, następny przebieg nadrobi |
| | 2 | nieznany argument |

Dlaczego kod 1 generatora jest „pustym dniem” tylko razem z linią `No qualifying reports`: awaria przed `main()` (np.
błąd składni) też kończy się kodem 1, a wrapper nie może jej pomylić z pustym dniem, bo zamknąłby okno i zgubił
zgłoszenia. Dlatego wrapper traktuje kod 1 bez tej linii jako awarię, a nieoczekiwany wyjątek w generatorze kończy się
kodem 2, nie 1.

## Komentarz zgłoszenia

Komentarz jest składany wyłącznie ze stałych angielskich `TPL_*` w generatorze, w stałej kolejności: zdanie o źródle;
protokół i porty celu; uruchomione scenariusze; liczba pasujących zdarzeń z zakresem czasu w UTC; próbka prawdziwych
żądań HTTP (metoda, ścieżka, status). CrowdSec nie zapisuje numeru portu, więc porty HTTP pochodzą z klucza
`HTTP_PORTS` (domyślnie `80/443`). Komentarz ma najwyżej 1024 bajty, a próbki, które zdradziłyby nazwy operatora lub
dane osobowe, są pomijane. Zasady, ich uzasadnienie i ograniczenia:
[COMPLIANCE.md](COMPLIANCE.md#poprawność-danych-w-zgłoszeniu).

Przykład jednego wiersza (fikcyjny adres z zakresu dokumentacyjnego; wygenerowany przez program z syntetycznych
alertów):

```csv
IP,Categories,ReportDate,Comment
203.0.113.45,"14,15,21",2026-10-01T11:09:03+00:00,"Detected by CrowdSec IDS on a self-hosted server. Target: HTTP/HTTPS (ports 80/443). Triggered rules: http-probing, http-sensitive-files. 4 matching log events between 2026-10-01T11:08:42Z and 11:09:03Z (UTC). Sample requests: GET /.env -> 404; GET /wp-login.php -> 404; GET /.git/config -> 404; GET /admin/config.php -> 404"
```

Ten sam przykład jest w [README](../../README.pl.md).

## Powiązanie z zewnętrznymi monitorami

Zewnętrzny monitor może czytać `abuseipdb_send.sh` i `.state/abuseipdb_last_ok` z katalogu instalacji. Traktuj obie
nazwy jako stabilny interfejs: zmiana którejkolwiek wymaga odpowiedniej zmiany w monitorze. Do czego służy monitor
i jaki próg ustawić: [OPERATIONS.md](OPERATIONS.md#monitoring).
