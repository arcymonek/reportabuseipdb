[English](CHANGELOG.md) | **Polski**

Wersja: 3.6.32 (`abuseipdb_report.py`)

# Historia zmian

Wszystkie istotne zmiany w projekcie. Każdy wpis ma odpowiednik w [CHANGELOG.md](CHANGELOG.md).

Numeracja wersji to `X.Y.Z`. Wersją projektu jest wersja `abuseipdb_report.py`. Każda zmiana, która trafia
na `main` (bezpośredni push albo scalona gałąź), podnosi `Z` o 1; gdy `Z` dojdzie do 99, następna wersja podnosi `Y` o 1 i zeruje `Z`
(po 3.6.99 następna to 3.7.0). `abuseipdb_send.sh` ma własną wersję i podlega tej samej regule, gdy się zmienia.

## Niewydane

- Na razie nic.

## 2026-10-01 - hook pilnuje pary kodeksu postępowania (3.6.32)

Tylko narzędzia; program i wygenerowany CSV bez zmian (ruszył tylko numer wersji).

- **`tools/pre-commit`:** reguła parowania EN/PL obejmuje teraz `CODE_OF_CONDUCT.md` i `CODE_OF_CONDUCT.pl.md`. Wcześniej
  hook znał tylko pary z listy w `pair_of()`, więc jedna strona mogła się zmienić bez drugiej i nic nie protestowało.
- **Testy:** reguła parowania nie miała żadnego testu. `tests/test_hooks.py` sprawdza teraz każdą parę w katalogu
  głównym (sama jedna strona jest odrzucana, obie strony przechodzą), różną liczbę nagłówków oraz to, że `EN_ONLY=1`
  pomija tylko tę regułę. Sprawdzone mutacją: bez poprawki czerwone były oba przypadki `CODE_OF_CONDUCT` i test
  nagłówków, a pozostałe pary zielone.

## 2026-10-01 - kodeks postępowania i szablon pull requestu (3.6.31)

Tylko pliki społeczności; program i wygenerowany CSV bez zmian (ruszył tylko numer wersji).

- **`CODE_OF_CONDUCT.md`** (Contributor Covenant 2.1, CC BY 4.0, zgłoszenia na publiczny adres autora) wraz z
  nieoficjalnym tłumaczeniem `CODE_OF_CONDUCT.pl.md`; linki z `README.pl.md` i `CONTRIBUTING.pl.md`.
- **`.github/pull_request_template.md`:** lista kontrolna odpowiadająca `CONTRIBUTING.md` (testy, bezpieczniki, test
  mutacyjny, tylko fikcyjne dane, dokumentacja po angielsku, bez podnoszenia wersji) i sekcja "What I did not verify".

## 2026-10-01 - poprawki po audycie dokumentacji (3.6.30)

Tylko dokumentacja; program i wygenerowany CSV bez zmian (ruszył tylko numer wersji).

- **README:** uwagi o statusie (prace w toku, link do profilu AbuseIPDB autora, napisane z Claude Code, najpierw
  `--dry-run`) są teraz w jednym bloku pod opisem projektu; osobna sekcja "Status" zniknęła.
- **`docs/pl/ARCHITECTURE.md`:** sekcja "Komentarz zgłoszenia" zawiera teraz ten sam przykładowy wiersz co README; tabela komponentów wymienia teraz `tools/commit-msg`, `tools/lib-privacy.sh` i workflow CI.
- **`docs/pl/OPERATIONS.md`:** nowa sekcja "Aktualizacja do nowej wersji" (pull, przeczytanie changelogu pod kątem
  nowych kluczy konfiguracji, `--dry-run`, sprawdzenie następnego przebiegu); literówka dotyczyła tylko wersji angielskiej.
- **README:** nowa sekcja "Przykład zgłoszenia" z jednym wierszem CSV (fikcyjny adres, wygenerowany przez prawdziwy
  program) i krótkim objaśnieniem kolumn.

## 2026-10-01 - akcje CI przypięte do skrótów commitów (3.6.29)

Higiena przed upublicznieniem repozytorium; program się nie zmienia: `abuseipdb_report.py` i wygenerowany CSV bez zmian
(ruszył tylko numer wersji).

- **`actions/checkout` i `actions/setup-python` są przypięte do pełnego skrótu commita** w `.github/workflows/tests.yml`
  (komentarz podaje tag, `v7`). Tag to ruchoma etykieta: kto kontroluje repozytorium akcji, mógłby wskazać nią inny
  kod. Skrótu nie da się przestawić. Ryzyko było małe (`permissions: contents: read`, brak sekretów, tylko oficjalne
  akcje), więc to rutynowa higiena łańcucha dostaw.
- **Aktualizacja jest ręczna** i opisana w `docs/DEVELOPMENT.md` ("Przypięte akcje CI"); Dependabota nie ma, celowo (jego
  pull requesty kolidowałyby ze scalaniem lokalnie przez `--ff-only`).

## 2026-10-01 - auto-zaufanie SSH obejmuje cały IPv6 /64 (3.6.28)

Znalezione przy przygotowaniu repozytorium do publikacji: kto loguje się przez IPv6, ma „tymczasowe" adresy zmieniające
się w obrębie jednej sieci /64, a zaufanie do dokładnego adresu nie mogło za nimi nadążyć, więc narzędzie mogło
zgłosić własny komputer operatora. IPv4 bez zmian. Wygenerowany CSV jest bajt w bajt taki sam jak w 3.6.27 dla danych
bez logowania IPv6 (sprawdzone na syntetycznych alertach z adresami IPv4 i IPv6).

- **Logowania IPv6 są zaufane jako sieć.** Adres z udanym logowaniem SSH wyklucza teraz cały swój /64 (wcześniej: tylko
  dokładny adres). Nowy klucz konfiguracji `SSH_TRUST_IPV6_PREFIX` (domyślnie `64`) ustawia długość: dozwolony zakres to
  64-128, każda inna wartość zatrzymuje przebieg (kod wyjścia 2). `128` przywraca zaufanie do dokładnego adresu, dla
  hostingu, w którym jeden /64 dzieli wielu klientów. Sieć szersza niż /64 jest celowo niemożliwa: zaufałaby cudzym
  sieciom. IPv4 jest zawsze zaufane dokładnie.
- **Koszt:** inne urządzenia w tym samym /64 (domownicy, goście) też nie będą zgłaszane, nawet jeśli atakują. To
  niedoraportowanie, nigdy fałszywe zgłoszenie, czyli bezpieczny kierunek błędu dla tego narzędzia.
- **Lista zapamiętanych bez zmian.** `ssh_trusted_seen.txt` nadal trzyma pojedyncze adresy; rozszerzenie następuje
  przy odczycie listy, więc zmieniony `SSH_TRUST_IPV6_PREFIX` działa od razu i nic nie trzeba migrować. Własne adresy
  serwera zostają dokładne. Linia startowa podaje teraz, ile adresów stało się iloma sieciami.
- **Naprawione logowania IPv4-mapped:** logowanie zapisane w logu jako `::ffff:8.8.8.8` jest teraz zapamiętywane jako
  zwykłe IPv4 `8.8.8.8`. Wcześniej trafiało na listę jako adres IPv6, który nigdy nie pasował do (już odmapowanego)
  adresu z alertu, więc niczego nie chroniło, a przy regule /64 zamieniłoby się w `::/64`.
- **Dokumentacja:** `docs/COMPLIANCE.md` stwierdza teraz, że format bulk AbuseIPDB przyjmuje adresy IPv4 i IPv6 (źródło:
  formularz bulk-report, sprawdzone 2026-10-01). Dokumentacja AbuseIPDB nic nie mówi o traktowaniu /64 po ich stronie.
- **Niesprawdzone:** w danych autora nie ma prawdziwego logowania IPv6 (31 logowań w 60 dniach, wszystkie IPv4), więc
  zachowanie przetestowano tylko na syntetycznych liniach journala i testem mutacyjnym (każdy celowo zepsuty bezpiecznik
  zaczerwienił test), nie na prawdziwym łączu IPv6, i to narzędzie nigdy nie wysłało zgłoszenia IPv6.

## 2026-10-01 - jedna pisownia adresu i UTC w każdym znaczniku czasu (3.6.27)

Znalezione audytem kodu z 2026-10-01. Higiena: nic w danych działającego serwera nie wywoływało żadnego z problemów (437
prawdziwych alertów: każdy adres już kanoniczny, każdy znacznik `...Z`), więc wygenerowany CSV jest bajt w bajt taki sam
jak w 3.6.26.

- **Adresy są kanonizowane** przed grupowaniem alertów i zapisem (`canonical_ip()`): IPv6 w formie skompresowanej, a
  adres IPv6 mapowany na IPv4 (`::ffff:8.8.8.8`) jako zwykły IPv4. Wcześniej ten sam host w dwóch zapisach dawał dwa
  wiersze, a walidator (porównujący jedną formę kanoniczną) nie widział duplikatu.
- **Znaczniki czasu z innym przesunięciem są przeliczane, nie tylko przemianowywane** (`parse_ts()`):
  `...T07:46:35+02:00` drukowało się jako `07:46:35 UTC`, czyli dwie godziny za późno (data zgłoszenia z przyszłości,
  którą walidator odrzuci i zatrzyma cały przebieg; przy ujemnym przesunięciu data po cichu trafiłaby w przeszłość).
  cscli drukuje dziś `Z`, więc to tylko zabezpiecza przed zmianą formatu.
- Testy: forma kanoniczna (skompresowana, mapowana, wielkie litery, nie-adres), dwa zapisy w jednym wierszu, wykluczenia
  nadal pasujące do każdego zapisu, przesunięcia `+02:00` / `-05:00` przeliczane, a `Z` bez zmian. Sprawdzone mutacją.

## 2026-10-01 - kontrola własnych nazw, IP i e-maili widzi też tekst zakodowany procentowo (3.6.26)

Znalezione audytem kodu z 2026-10-01 (próbka `www%2Eexample%2Eorg` przechodziła obok znacznika `example.org`).

- Ścieżka żądania pochodzi od atakującego, który (albo jego skaner) może zakodować dokładnie te znaki, których szukają
  kontrole. `leaks_identity()` (pomija wrogą próbkę) i walidator CSV (odrzuca plik) sprawdzają teraz także tekst po jednej
  i po dwóch rundach dekodowania procentowego (`decoded_views()`): własna nazwa zapisana `www%2Eexample%2Eorg`, e-mail
  zapisany `jane%40mail.example.net` albo zgłaszany IP zapisany `8%2E8%2E8%2E8` jest wychwytywany tak jak zwykła forma.
  Zwykłe kodowanie (`%20`, `%2F`, `%3C`) zostaje bez zmian, a uszkodzona sekwencja nigdy nie rzuca wyjątku.
- To wzmacnia twardy bezpiecznik (kontrolę własnych nazw); może tylko pominąć WIĘCEJ próbek, nigdy żadnej nie dodać.
  Na 437 prawdziwych alertach (8 dni) wygenerowany CSV jest bajt w bajt identyczny z poprzednią wersją.
- Testy: zakodowana nazwa, podwójnie zakodowana nazwa, zakodowany e-mail, zakodowany zgłaszany IP, zwykłe kodowanie bez
  zmian, odrzucenie przez walidator, uszkodzone sekwencje. Sprawdzone mutacją (każdy wariant tylko na zwykłym tekście
  robi czerwony test).

## 2026-10-01 - hooki prywatności: koniec ogólnej zgody na domenę autora, skan komunikatów commitów (3.6.25)

Znalezione audytem kodu z 2026-10-01; potwierdzone uruchomieniem hooka w tymczasowym repozytorium.

- **Naprawiona dziura w `tools/pre-commit`.** Kilka ciągów dozwolonych w repozytorium (dane kontaktowe autora) było
  usuwanych ze skanu jako zwykłe podciągi, więc nazwa hosta POD domeną autora (`host.<domena>`) traciła domenę,
  zostawało `host.` i przechodziła skan własnych nazw, choć domena jest jednym z własnych znaczników operatora. Teraz
  domena jest usuwana tylko wtedy, gdy stoi samodzielnie (nie po znaku nazwy hosta ani lokalnej części adresu e-mail);
  `github@<domena>`, strona, imię i nazwisko autora oraz ścieżka profilu GitHuba pozostają dozwolone, każda inna
  skrzynka lub host w tej domenie jest odrzucany.
- **Nowy hook `tools/commit-msg`.** Skan pre-commit patrzy tylko na pliki, a komunikat commita też trafia do publicznej
  historii. Nowy hook stosuje te same reguły do komunikatu (własne nazwy, ciąg podobny do klucza), pomija linie
  komentarza `#` gita i, tak jak drugi hook, bez lokalnego configu niczego nie skanuje. Włącza się tym samym
  `git config core.hooksPath tools`.
- **`tools/lib-privacy.sh`**: reguły prywatności (czytanie `OWN_NAME_MARKERS`, dozwolone ciągi) są teraz w jednym pliku,
  który wczytują oba hooki, więc nie mogą się rozjechać.
- `tools/pre-commit` wypisuje notkę, gdy nie ma `shellcheck`, zamiast pomijać sprawdzenie po cichu (CI nadal je robi).
- **Pierwsze testy hooków** (`tests/test_hooks.py`, 15 testów, każdy w tymczasowym repozytorium): zmiana bez zastrzeżeń,
  własne nazwy, dozwolone dane autora, hosty pod domeną autora odrzucane, prawdziwy plik konfiguracji, ciągi podobne do
  klucza, brak configu, skan tylko dodanych linii, hook komunikatu oraz oba hooki uruchamiane jako prawdziwe hooki
  gita. Sprawdzone mutacją: dawne zachowanie z podciągiem i każde usunięte sprawdzenie robi czerwony test.
- CI: `bash -n` i `shellcheck` obejmują teraz także nowe pliki hooków.

## 2026-10-01 - błędna konfiguracja zatrzymuje przebieg, alert przy osłabionym zabezpieczeniu, szersze pobieranie (3.6.24)

Znalezione audytem kodu z 2026-10-01 i sprawdzone na działającym serwerze. Wrapper `abuseipdb_send.sh` ma wersję 1.1.7.

- **Konfiguracja, której nie da się odczytać, zatrzymuje przebieg** (`abuseipdb_report.py`). Dotąd plik konfiguracji,
  który istniał, ale nie dało się go użyć (złe uprawnienia, bajty niebędące UTF-8, np. komentarz wpisany w starym
  kodowaniu), dawał tylko ostrzeżenie, a przebieg szedł dalej BEZ kontroli nazw własnych i bez wszystkich wpisów
  `EXCLUDE`. Wrapper tego nie zauważał, bo czyta znaczniki przez `sed`. Teraz to `ConfigError` (kod wyjścia 2) w każdym
  trybie, tak jak literówka w kluczu. To samo dla przestarzałego pliku wykluczeń. Brak pliku to nadal tylko informacja.
- **Kod wyjścia 1 jest honorowany tylko razem ze swoim komunikatem** (`abuseipdb_send.sh`). Kod 1 znaczy "nie ma
  czego zgłaszać", ale awaria przed `main()` (błąd składni, brak modułu) też kończy się kodem 1, a wrapper po cichu
  zamknąłby okno. Wrapper wymaga teraz linii `No qualifying reports` (stała generatora), a kod 1 bez niej uznaje za
  awarię: znacznik stoi i leci alert.
- **Nowy alert ntfy "safeguard not working"** (`abuseipdb_send.sh`). Generator oznacza `[SAFEGUARD-OFF]` każdą linię,
  która mówi, że zabezpieczenie nie działa, choć przebieg trwa dalej: nie da się czytać journala (auto-zaufanie SSH
  niepełne), brak programu `ip` (nieznane własne adresy serwera), listy zaufanych IP nie da się odczytać lub zapisać.
  Wcześniej były to linie w logu, którego nikt nie czyta. Przebieg nadal trwa z pozostałymi zabezpieczeniami.
- **Pobieranie sięga 1 godzinę przed okno** (`abuseipdb_send.sh`). `cscli --since` filtruje po POCZĄTKU alertu, a okno
  po czasie jego utworzenia, więc wolny kubełek utworzony w oknie mógł zginąć na granicy (zmierzone na działającym
  serwerze: do ok. 2 minut między początkiem a utworzeniem, 3 z 441 alertów powyżej 30 s). `--after`/`--before` nadal
  wyznaczają okno dokładnie; zapas (`SINCE_MARGIN_S`, domyślnie 3600) tylko zapobiega utracie.
- **Alerty ntfy nie niosą już ścieżki instalacji ani katalogu domowego** (`abuseipdb_send.sh`): wiadomość idzie przez
  publiczny serwer ntfy, więc `<dir>` i `~` je zastępują; lokalny log zachowuje pełny tekst.
- `--limit` musi być liczbą całkowitą 1 lub większą (`0` powodowało, że "limit osiągnięty" było zawsze prawdą i szedł
  fałszywy alert `[TRUNCATED]`).
- Testy: zastąpiono test utrwalający dawne "ostrzeż i idź dalej"; nowe testy dla konfiguracji nie-UTF-8 w każdym trybie,
  znacznika każdego osłabionego zabezpieczenia, kodu 1 z komunikatem i bez, zasięgu 1 godziny oraz treści alertu.
  Sprawdzone mutacją: zepsucie każdej z tych zmian robi czerwony test.

## 2026-10-01 - testy wbudowanego wykluczenia scenariusza i dwóch limitów (3.6.23)

- Tylko testy, zachowanie bez zmian. Test mutacyjny (celowe zepsucie bezpiecznika) pokazał, że opróżnienie
  `EXCLUDE_SCENARIOS` nie robiło czerwonym żadnego testu: `http-crawl-non_statics` nie ma w `CATEGORY_MAP`, więc
  reguła "nieznany scenariusz" i tak go odrzucała i ukrywała zepsuty bezpiecznik. Testy najpierw mapują scenariusz,
  więc zatrzymać go może tylko wykluczenie (także dla `EXTRA_EXCLUDE_SCENARIOS`, które może tylko dodawać do listy
  wbudowanej).
- Nowe testy: cięcie pliku CSV przy 8 MB (plik jest cięty jak najpóźniej i oznaczany `[TRUNCATED]`), `ReportDate` nigdy
  z przyszłości, gdy alert ma znacznik o kilka minut do przodu, oraz odczyt własnych adresów serwera z `ip addr`
  (tylko globalne). Wszystkie cztery sprawdzone mutacją.

## 2026-10-01 - w README podane środowisko testowe (3.6.22)

- `README.pl.md` (Wymagania): wprost mówi, że narzędzie testowano tylko na Debianie 12 i Ubuntu 24.04 z CrowdSecem
  1.7 i 1.8 oraz nginx, że inne konfiguracje są nietestowane, a macOS, BSD, systemy bez systemd i CrowdSec w
  kontenerze nie są wspierane bez dodatkowych kroków. Tylko dokumentacja, zachowanie bez zmian.

## 2026-09-30 - formularz pytań w Discussions (3.6.21)

- `.github/DISCUSSION_TEMPLATE/q-a.yml`: kategoria Q&A w GitHub Discussions ma teraz formularz, tak jak Ideas:
  ostrzeżenie o prywatności i link do `SECURITY.md`, wskazówka o README i `docs/OPERATIONS.md`, to samo obowiązkowe
  potwierdzenie prywatności, obowiązkowe pytanie oraz opcjonalne pola na to, co już próbowano, wersje i fragment logu
  (ostatnie 60 linii `abuseipdb_cron.log`). W pytaniach też wklejane są logi, więc potwierdzenie prywatności należy tu
  również.

## 2026-09-30 - formularz pomysłów w Discussions (3.6.20)

- `.github/DISCUSSION_TEMPLATE/ideas.yml`: kategoria Ideas w GitHub Discussions ma teraz też formularz, z ostrzeżeniem o
  prywatności, tym samym obowiązkowym potwierdzeniem prywatności co zgłoszenie błędu oraz polami na cel, pomysł i
  (opcjonalnie) alternatywy i ryzyka. Pomysły idą do Discussions zamiast do osobnego formularza zgłoszeń: pomysł często
  dotyka bezpiecznika i wymaga najpierw decyzji, a zaakceptowany można zamienić na zgłoszenie.
- `.github/ISSUE_TEMPLATE/config.yml`: własny link "Security vulnerability" usunięty. Prowadził do formularza
  prywatnego zgłaszania podatności, który GitHub sam oferuje po włączeniu tej funkcji, więc byłby duplikatem.

## 2026-09-30 - zgłoszenie błędu jako formularz (3.6.19)

- `.github/ISSUE_TEMPLATE/bug_report.yml` zastępuje `bug_report.md`: zgłoszenie błędu jest teraz formularzem z
  osobnymi polami zamiast jednego pola tekstowego. Ostrzeżenie o prywatności i link do `SECURITY.md` są na górze i nie
  da się ich skasować, dalej jest obowiązkowe potwierdzenie prywatności (dwa pola wyboru), potem obowiązkowe pola: co się
  stało, czego oczekiwano, wersje wrappera i generatora oraz wersje CrowdSeca i Pythona, opcjonalne pole dystrybucji i
  pole na log z ostatnich 60 linii `abuseipdb_cron.log` (fragment, nie cały plik).
- `.github/ISSUE_TEMPLATE/config.yml`: puste zgłoszenia są wyłączone, więc każde zgłoszenie przechodzi przez formularz;
  nowy link kieruje pytania i pomysły do GitHub Discussions.

## 2026-09-30 - wyzwalacze CI, aktualne akcje, przypięty runner (3.6.18)

- `.github/workflows/tests.yml`: testy uruchamiają się przy pushu na `main` i na pull requestach, a nie przy każdym
  pushu na każdą gałąź, więc pull request nie uruchamia już dwóch identycznych przebiegów. Gałąź testuje się przez jej
  pull request (wystarczy szkic).
- `actions/checkout` i `actions/setup-python` przeszły z `@v4` / `@v5` na `@v7`: stare wersje działały na Node 20,
  który GitHub wycofuje (ostrzeżenie w przebiegu CI dla 3.6.16).
- Runner przypięty do `ubuntu-24.04` zamiast `ubuntu-latest`. GitHub przesuwa tę etykietę na Ubuntu 26 dnia
  2026-10-19; narzędzia używane w testach mają się zmieniać wtedy, kiedy zdecydujemy. To pierwsza zmiana, która przeszła
  przez gałąź i pull request (workflow opisany w 3.6.17).

## 2026-09-30 - workflow z gałęziami dla kodu (3.6.17)

- `docs/pl/DEVELOPMENT.md`: workflow ma teraz dwie ścieżki. Dokumentacja i redakcja idą wprost na `main`; kod, testy,
  hook, workflow CI i każda zmiana opisu bezpiecznika idą przez gałąź, wypychaną wyłącznie na `github`, z zielonym
  przebiegiem `tests` przed lokalnym scaleniem przez opiekuna (`--ff-only`) i pushem najpierw na `origin`, potem na
  `github`. Wersja rośnie raz na zmianę, która trafia na `main` (na gałęzi w jej ostatnim commicie), a nie na każdy
  commit.
- `docs/pl/DEVELOPMENT.md`: "Przyjmowanie pull requesta" przepisane pod forki (`pull/N/head`, lokalna gałąź `pr-N`,
  scalenie na komputerze opiekuna, pull request zamyka się sam). Lista kontrolna przed publikacją nie wymaga już
  wymaganego sprawdzenia `tests` w rulesecie (blokowałoby bezpośrednie pushe dokumentacji); wymaga rulesetu blokującego
  force-push i usuwanie gałęzi.
- `CONTRIBUTING.md` / `CONTRIBUTING.pl.md`: nowa sekcja "Jak wysłać zmianę" (fork, gałąź, pull request, utrzymanie
  gałęzi w aktualności; scala wyłącznie opiekun).
- `AGENTS.md`: agenci pracują na gałęzi i nigdy nie commitują na `main` ani nie scalają.

## 2026-09-30 - AGENTS.md i wkład tylko po angielsku (3.6.16)

- Nowy `AGENTS.md` (tylko po angielsku, bez polskiego odpowiednika): zasady dla agentów AI pracujących nad
  repozytorium, żeby asystent kontrybutora znał bezpieczniki, których nie wolno osłabiać, czego nigdy nie robić
  (prawdziwa wysyłka, prawdziwe klucze, nazwy hostów), konwencje i kilka nieoczywistych faktów o danych. Linkowany z
  README i `CONTRIBUTING.md`.
- `CONTRIBUTING.md` / `CONTRIBUTING.pl.md`: sekcja "Język" (zgłoszenia, pull requesty i przeglądy po angielsku) oraz
  "Praca z asystentem AI". Kontrybutorzy piszą dokumentację tylko po angielsku; polskie tłumaczenie i wpis w
  changelogu dodaje opiekun, więc nie muszą już aktualizować obu języków.
- `tools/pre-commit`: `EN_ONLY=1 git commit ...` pomija tylko regułę parowania EN/PL dla kontrybutorów piszących
  wyłącznie po angielsku; skan prywatności i wszystkie pozostałe kontrole nadal działają (sprawdzone ręcznie: bez
  zmiennej zmiana jednostronna jest odrzucana, ze zmienną commit przechodzi, a sztuczny klucz nadal jest odrzucany).
- `docs/pl/DEVELOPMENT.md`: `AGENTS.md` jako jedyny udokumentowany wyjątek od reguły parowania, przepływ z `EN_ONLY` i
  nowa sekcja "Przyjmowanie pull requesta" (ściągnij lokalnie, przetestuj, dodaj tłumaczenie, podnieś wersję, najpierw
  push do prywatnego repozytorium). `docs/pl/ARCHITECTURE.md` i oba README wymieniają nowy plik.

## 2026-09-29 - kontakt autora i kolejność w README (3.6.15)

- Adres kontaktowy w README, `SECURITY.md` i na liście dozwolonych ciągów hooka pre-commit to teraz dedykowany adres
  GitHub.
- README: krótkie ostrzeżenie "wczesny etap" pod tytułem; sekcja "Status" (z informacją, że projekt powstał z Claude
  Code i że najpierw `--dry-run` oraz przejrzenie CSV) przeniesiona przed "Wymagania"; "Licencja" i "Autor" scalone w
  jedną sekcję.
- E-mail autora commitów zmieniony na adres no-reply GitHuba.

## 2026-09-29 - gotowe dla innych użytkowników i kontrybutorów (3.6.14)

- README: nowa sekcja "Czy to narzędzie jest dla ciebie?" (prawdziwy IP klienta za CDN lub proxy, publiczny adres za
  NAT, journal systemd, własne fałszywe alarmy, inne porty WWW) oraz pełna instalacja: `jq`, reguła sudo bez hasła
  pozwalająca tylko na `cscli alerts list`, dostęp do journala dla auto-zaufania SSH, sprawdzenie bez hasła.
- Nowe `CONTRIBUTING.md` / `CONTRIBUTING.pl.md` i `SECURITY.md` / `SECURITY.pl.md` (prywatne zgłaszanie podatności),
  szablon zgłoszenia błędu z prośbą o anonimizację logów oraz workflow GitHub Actions uruchamiający cały zestaw testów
  (także wrappera) na Ubuntu z Pythonem 3.9 i najnowszym, plus `shellcheck`.
- `tools/pre-commit`: commit, który nie rusza wersji, przechodzi (kontrybutorzy jej nie podnoszą; robi to opiekun przy
  scalaniu); commit, który ją zmienia, nadal musi ją podnieść dokładnie o jeden krok. Nowe dokumenty są parowane EN/PL.
- `docs/COMPLIANCE.md`: reguła polityki "TCP tylko po pełnym three-way handshake, UDP nigdy" oraz dzienne limity bulk
  z dokumentacji API (Standard 5, Basic 100, Premium 500; odznaki Webmaster i Supporter podnoszą darmowy limit, 20
  widziane na koncie autora). Ponownie zweryfikowane na surowych stronach AbuseIPDB 2026-09-29.
- `docs/DEVELOPMENT.md`: zasady dla kontrybutorów, CI, czwarty znany równoważny mutant, a lista przed publikacją nie
  twierdzi już, że historia to jeden commit.
- Bez zmian działania generatora i wrappera (tylko numer wersji); CSV bez zmian.

## 2026-09-29 - problemy z journalem są zgłaszane, więcej metod logowania SSH, ALERT_LIMIT (3.6.13)

- `abuseipdb_report.py` 3.6.13: sprawdzane są kod wyjścia i stderr `journalctl`. Zmierzone na journalctl 252: kod 1 z
  pustym stderr oznacza tylko "brak pasujących wpisów", a brak uprawnień do journala (albo wersja bez `--grep`) zawsze
  wypisuje komunikat. Wcześniej taka awaria była cicha, gdy zapamiętana lista zaufanych nie była pusta, więc nowe
  logowania operatora przestawały być zaufane. Teraz to głośne `[warn]` ze wskazówką naprawy.
- Auto-zaufanie SSH rozpoznaje też `keyboard-interactive/<urządzenie>` inne niż `pam` (np. `bsdauth`), `hostbased` i
  `gssapi-*`. `Accepted none` celowo nie jest zaufane.
- `abuseipdb_send.sh` 1.1.6: `ALERT_LIMIT` (ustawiany w linii crontaba) trafia do generatora jako `--limit`. Alert
  "data cut off" kazał operatorowi podnieść `--limit`, czego przez wrapper nie dało się zrobić. Nieprawidłowa wartość
  kończy przebieg, zanim cokolwiek zostanie wygenerowane.
- CSV bez zmian (sprawdzone bajt w bajt na 497 prawdziwych alertach z ostatnich 30 dni).
- Nowe testy wyników journala, metod logowania i `ALERT_LIMIT`.

## 2026-09-29 - porty HTTP i dodatkowe wykluczone scenariusze w configu (3.6.12)

- `abuseipdb_report.py` 3.6.12: nowy opcjonalny klucz configu `HTTP_PORTS` (domyślnie `80/443`). Porty w "Target:
  HTTP/HTTPS (ports 80/443)." były stałą prawdziwą tylko na serwerze autora; na innym serwerze publiczne zgłoszenie
  podałoby zły port. Jeden port daje "port 443"; przyjmowane są tylko cyfry i `/`, a nieprawidłowa wartość zatrzymuje
  przebieg jak każdy inny błąd configu.
- Nowy opcjonalny klucz configu `EXTRA_EXCLUDE_SCENARIOS`: scenariusze, których operator nigdy nie chce zgłaszać (np.
  taki, który dawał fałszywe alarmy na jego ruchu), bez edycji kodu. Krótka nazwa pasuje do każdego autora, pełna
  `autor/nazwa` tylko do tego autora. Tylko dodaje do wbudowanych `EXCLUDE_SCENARIOS`.
- CSV bez zmian przy wartościach domyślnych (sprawdzone bajt w bajt na 497 prawdziwych alertach z ostatnich 30 dni).
- Nowe testy obu kluczy (parsowanie, walidacja, komentarz, krótkie i pełne nazwy, od początku do końca).

## 2026-09-29 - reguła CVE tylko dla zaufanego autora, bezpieczne cudzysłowy i backslashe, bez e-maili (3.6.11)

- `abuseipdb_report.py` 3.6.11: scenariusz nazwany od identyfikatora CVE dostaje domyślne 15,21 tylko wtedy, gdy jego
  autorem jest `crowdsecurity`. Wcześniej `ktos/postfix-cve-2024-1234` zostałby opublikowany jako atak na aplikację
  webową. Scenariusz CVE innego autora wymaga jawnego wpisu pełnej nazwy w `CATEGORY_MAP`, jak każdy obcy scenariusz.
- Cudzysłów w próbce żądania jest zapisywany jako `%22`, a komentarz nigdy nie kończy się backslashem. Strona
  bulk-report mówi, że backslashe i cudzysłowy wymagają eskejpowania (parser AbuseIPDB traktuje backslash jako znak
  ucieczki), a moduł `csv` Pythona zostawia backslashe bez zmian. Walidator odrzuca teraz backslash przed cudzysłowem
  lub na końcu komentarza. Pozostałe backslashe zostają: są dowodem (`\x5Cthink\x5Capp`). Zapobiegawczo: nginx i tak
  zapisuje cudzysłów jako `\x22`, a AbuseIPDB dotąd przyjął każdy wiersz; jak parsuje te przypadki, nie da się
  sprawdzić bez prawdziwej wysyłki.
- Próbka żądania wyglądająca na zawierającą adres e-mail jest pomijana w komentarzu (FAQ AbuseIPDB: bez danych
  osobowych w komentarzach), tak samo jak próbka z własną nazwą. Walidator nadal tylko ostrzega.
- CSV bez zmian (sprawdzone bajt w bajt na 497 prawdziwych alertach z ostatnich 30 dni, 7 wierszy z backslashami).
- Nowe testy reguły autora, cudzysłowu, końcowego backslasha, walidatora i pomijania e-maili.

## 2026-09-29 - plik konfiguracji działa fail-closed (3.6.10)

- `abuseipdb_report.py` 3.6.10: zniekształcona linia, nieznany klucz (literówka typu `EXLUDE=`), komentarz po wartości
  (`EXCLUDE=203.0.113.7 # dom`), wpis `OWN_NAME_MARKERS` ze spacją lub `#` w środku albo nieprawidłowy wpis `EXCLUDE`
  lub starego pliku wykluczeń zatrzymują teraz każdy tryb generatora z kodem 2. Wcześniej były pomijane z
  ostrzeżeniem: adres, który operator chciał chronić, stawał się zgłaszalny, a znacznik z doklejonym komentarzem nigdy
  nie pasował, choć wrapper uznawał listę za ustawioną. Znalezione w audycie przed publikacją; config produkcyjny nie
  był dotknięty.
- `abuseipdb_send.sh` 1.1.5: czytelny błąd dla przykładowego klucza API z szablonu, a alerty nie idą na `NTFY_TOPIC`
  spoza `[A-Za-z0-9_-]{1,64}` ani na `NTFY_URL` ze spacjami lub cudzysłowami (`"` zepsułby konfigurację curl, którą
  przechodzi URL).
- CSV bez zmian (sprawdzone bajt w bajt na 497 prawdziwych alertach z ostatnich 30 dni).
- Nowe testy dla każdego odrzucanego kształtu, dla zatrzymania `--validate` i generowania z kodem 2 oraz dla kontroli
  wrappera.

## 2026-09-28 - wartości podobne do poświadczeń są maskowane w próbkach żądań (3.6.9)

- `abuseipdb_report.py` 3.6.9: w części "Sample requests" komentarza WARTOŚĆ parametru zapytania, którego nazwa wygląda na
  poświadczenie (`token`, `key`, `api_key`, `secret`, `password`, `session`, `PHPSESSID`, `auth`, `sig`, `jwt`, `code`,
  `csrf` i podobne), jest zastępowana przez `***`. Wcześniej do publicznej bazy szła cała ścieżka, więc fałszywy alarm
  na żądaniu prawdziwego użytkownika mógł opublikować token z jego adresu URL (znalezione w przeglądzie przez podanie
  generatorowi `?token=...`; nie widziane w prawdziwych danych). Krótka nazwa jest dopasowywana jako całe słowo, więc
  `keyword=<script>` zachowuje ładunek. W miarę możliwości, nie gwarancja: sekret w samej ścieżce albo pod nietypową
  nazwą nie zostanie rozpoznany.
- Sprawdzone na 502 prawdziwych alertach z ostatnich 30 dni: wszystkie 182 wiersze identyczne bajt w bajt, nic nie
  zostało zamaskowane (próbki z tego okresu nie zawierają parametru podobnego do poświadczenia), więc dziś to środek
  zapobiegawczy, a nie naprawa zaobserwowanego wycieku.
- CSV bez zmian dla żądań bez takiego parametru (sprawdzone bajt w bajt).
- Nowe testy: maskowanie wielu kształtów nazw, nazwy tylko zawierające słowo kluczowe (`keyword`, `monkey`, `author`,
  `passenger`, `encode`), nietknięte ścieżki, komentarz od początku do końca (sekret znika, ładunek zostaje) oraz ścieżka
  niebędąca tekstem.

## 2026-09-28 - nieznane scenariusze nie są już zgłaszane jako "hacking" (3.6.8)

- `abuseipdb_report.py` 3.6.8: `category_for()` nie zwraca nic dla nieznanego scenariusza, a taki alert jest pomijany i
  wypisywany na stderr (`unknown scenario X - not reported`). Wcześniej każdy scenariusz spoza `CATEGORY_MAP` trafiał do
  publicznej bazy jako "hacking + atak na aplikację webową" (15,21), np. scenariusz postfix, MySQL albo własny, czyli
  mocniejsze twierdzenie, niż uzasadnia log. Zgłaszane są teraz: scenariusze autora `crowdsecurity` z mapy, scenariusze
  nazwane od prawdziwego identyfikatora CVE (nadal 15,21) oraz scenariusze, które operator doda do `CATEGORY_MAP` pod
  pełną nazwą (`autor/nazwa`). Ta sama krótka nazwa od innego autora (`ktos/ssh-bf`) była traktowana jak zaufana, a
  teraz nie jest. Nowy bezpiecznik 7 w docstringu i w COMPLIANCE.
- Sprawdzone na 502 prawdziwych alertach z ostatnich 30 dni (cscli v1.8.1): 182 wiersze przed i po, 181 identycznych
  bajt w bajt, żaden nie zniknął. Jedyny zmieniony wiersz ma o jeden scenariusz mniej
  (`LePresidente/http-generic-401-bf`, obcy scenariusz brute force, który był zgłaszany jako 15,21); kategorie się nie
  zmieniły, bo inny scenariusz tego samego adresu też daje 15,21. Ten sam przebieg pokazał, że ta wersja `cscli` ma pole
  `kind` i drukuje czasy z dokładnością do sekundy.
- CSV bez zmian dla wsadu zawierającego tylko znane scenariusze (sprawdzone bajt w bajt).
- Nowe testy: `category_for` (zaufany autor, obcy autor, brak autora, ręczny ban, nazwy CVE, jawny wpis pod pełną
  nazwą), pominięty alert z podpowiedzią, jeden adres ze scenariuszem znanym i nieznanym, `null`/brak scenariusza oraz
  to, że każdy scenariusz z mapy zachowuje swoją kategorię. Dwa testy protokołu używały wymyślonych nazw scenariuszy i
  teraz używają scenariuszy z mapy.

## 2026-09-28 - mniej cichych założeń o hoście (3.6.7)

- `abuseipdb_report.py` 3.6.7: auto-zaufanie SSH czyta teraz journal obu jednostek, `ssh` i `sshd` (`sshd` to nazwa
  jednostki na RHEL, Fedorze, Archu i SUSE; wcześniej główna ochrona przed zgłoszeniem własnego adresu była tam po cichu
  pusta i w logu lądowało tylko ostrzeżenie). Uruchomiony jako root wywołuje `cscli` bezpośrednio, bez `sudo`.
- Każdy komunikat o UCIĘTYCH danych (alerty przy `--limit`, ponad 9999 wierszy, limit 8 MB) zaczyna się teraz od
  `[TRUNCATED]`. Znacznik po takim przebiegu i tak się przesuwa, więc ucięte alerty przepadłyby z samą linijką w logu.
  `abuseipdb_send.sh` 1.1.4 szuka tego znacznika i wysyła alert ntfy `abuseipdb: data cut off` (także gdy nie ma czego
  wysyłać). Znacznik jest interfejsem między oboma skryptami.
- Jeśli WSZYSTKIE alerty w przebiegu odpadną, bo ich `kind` nie jest `crowdsec`, generator drukuje głośne ostrzeżenie:
  na wersji `cscli` bez pola `kind` narzędzie inaczej nie zgłaszałoby nic w nieskończoność, mówiąc tylko
  "No qualifying reports".
- `abuseipdb_send.sh` 1.1.4: ścieżka pliku CSV jest ujęta w cudzysłów w `curl -F` (bez tego `,` lub `;` w ścieżce
  instalacji psuło `curl` błędem `Failed to open/read local data`; zmierzone na curl 8.7.1).
- Komentarz przy wzorcu logowania SSH mówi teraz dokładnie, co jest, a co nie jest zaufane (`Partial publickey` jest
  ignorowane, liczy się tylko pełne logowanie). Kod bez zmian.
- CSV bez zmian. Nowe testy: obie nazwy jednostki, root a sudo, znacznik `[TRUNCATED]` (alerty przy `--limit`, limit
  wierszy, tylko na początku linii), ostrzeżenie o `kind`, a w wrapperze alert ntfy (także bez wierszy i w dry-run) oraz
  cytowana ścieżka w `-F`. Testy wrappera wymagają Linuksa: cały zestaw (162 testy, żaden pominięty) przeszedł na
  Debianie 12 z Pythonem 3.11.

## 2026-09-28 - czas parsuje się tak samo na Pythonie 3.9 do 3.14 (3.6.6)

- `abuseipdb_report.py` 3.6.6: wspólny `parse_iso_datetime()` (używany dla czasów CrowdSeca, logowań SSH z journalctl i
  pliku zaufanych IP) przepisuje tekst tak, żeby Python 3.9 i 3.10 go przyjęły: przesunięcie strefy bez dwukropka
  (`+0200`, dokładnie to, co drukuje journalctl) oraz ułamek sekundy o dowolnej liczbie cyfr (CrowdSec może podać 9).
  Wcześniej na Pythonie < 3.11 czas logowania SSH po cichu stawał się "teraz", więc zaufany adres wygasał później niż
  udokumentowane 60 dni (znalezione w przeglądzie; kierunek bezpieczny, ale obietnica była nieprawdziwa), a alert z
  9-cyfrowym ułamkiem w `created_at` zostałby odrzucony jako nieczytelny. Na 3.11+ nic się nie zmienia.
- `parse_ts()` zwraca `None` (alert jest pomijany i liczony) dla wartości, która nie jest tekstem, zamiast się wywalić.
- Walidator CSV nadal używa ścisłego `fromisoformat()` celowo: sprawdza format, który zapisujemy sami.
- CSV bez zmian (sprawdzone bajt w bajt na tym samym pliku alertów przed i po, na 3.14).
- README: Python 3.9 lub nowszy (testowany na 3.9 i 3.14). Cały zestaw jest zielony na obu; wcześniej dwa testy
  zaufania SSH padały na 3.9. Pythona 3.10 i 3.12/3.13 nie uruchamiałem.
- Nowe testy: przepisywanie tekstu (przesunięcie, `Z`, ułamki 1-9 cyfr, poprawny tekst nietknięty, śmieci nadal
  odrzucane) i `parse_ts` z nietypowymi wartościami.

## 2026-09-28 - awaria generatora nie udaje już "braku zgłoszeń" (3.6.5)

- `abuseipdb_report.py` 3.6.5: każdy nieoczekiwany wyjątek kończy przebieg kodem 2 (i śladem błędu na stderr).
  Wcześniej domyślny kod 1 Pythona był odczytywany przez `abuseipdb_send.sh` jako "brak kwalifikujących się
  zgłoszeń", więc awaria przesuwała znacznik i po cichu kasowała całe okno czasu, bez alertu. Znalezione w przeglądzie
  przez podanie generatorowi `null` oraz alertu z `"scope": null`. Kod 2 sprawia, że wrapper zostawia znacznik,
  wysyła alert ntfy i ponawia to samo okno w następnym przebiegu.
- Wyjście `cscli` lub `--input-json` zawierające `null` jest teraz pustą listą ("nie ma czego zgłaszać", kod 1, bez
  śladu błędu); każdy inny JSON niebędący listą, nieczytelny plik lub błędny JSON to czysty błąd (kod 2).
  `extract_ip` toleruje `null` w `source.scope` i `value`.
- CSV bez zmian (sprawdzone bajt w bajt na tym samym pliku alertów przed i po).
- Nowe testy: awaria daje kod 2, wsad `null`, wsad niebędący listą, błędny lub nieczytelny plik wejściowy, `null` w
  scope i w `value`. Strona wrappera (kod 2 zostawia znacznik i alarmuje) była już pokryta testem
  `test_generator_error_alerts_and_keeps_watermark`; brakowało kodu wyjścia prawdziwego generatora.

## 2026-09-28 - wrogie ścieżki nie blokują pliku, wartości przykładowe odrzucane (3.6.4)

- `abuseipdb_report.py` 3.6.4: próbka żądania, której ścieżka zawiera znacznik własnej nazwy, zgłaszany IP albo jeden z
  własnych adresów publicznych serwera, jest pomijana w komentarzu; zgłoszenie i jego pozostałe próbki zostają. Wcześniej
  walidator odrzucał cały plik z powodu jednej takiej ścieżki (znalezione na prawdziwych danych: skaner wklejający nazwę
  hosta celu w ścieżkę, 5 z 180 wierszy w 60 dni), co oznaczało brak zgłoszeń tego dnia i utratę danych po przerwie
  dłuższej niż 48 h. Walidator się nie zmienił i pozostaje ostatnią linią obrony. Pominięte próbki są liczone na stderr
  (`omitted N sample requests ...`), nigdy wypisywane. CSV jest bez zmian dla danych bez takich ścieżek.
- `abuseipdb_send.sh` 1.1.3: przebieg na żywo jest odmawiany, dopóki `OWN_NAME_MARKERS` ma wartości przykładowe
  (`your-domain.example`, `your-host.example`); dry-run tylko ostrzega. Alerty nigdy nie idą na przykładowy temat
  `your-private-ntfy-topic` (zamiast tego błąd w logu). `abuseipdb.conf.example` używa teraz tych wartości i mówi o tym.
- Nowe testy: pomijanie próbek (własna nazwa, IPv4/IPv6 zgłaszanego hosta, własny adres serwera), przebieg end-to-end z
  wrogimi ścieżkami i atrapą polecenia `ip` (to pokrywa też wykluczanie własnego adresu serwera ze zgłoszeń) oraz
  odmowa wartości przykładowych i tematu w wrapperze.

## 2026-09-28 - ntfy przez IPv4 (3.6.3)

- `abuseipdb_send.sh` 1.1.2: alerty do ntfy są wysyłane przez `curl -4`. `ntfy.sh` liczy dzienny limit wiadomości po
  adresie; przez IPv6 limit wspólnej puli może być już wyczerpany przez innych nadawców (HTTP 429, kod 42908), podczas
  gdy IPv4 nadal działa, co po cichu połykało alerty. Na hoście tylko z IPv6 usuń `-4`.
- `abuseipdb_report.py` 3.6.3: tylko podniesienie wersji, wygenerowany CSV bez zmian.

## 2026-09-28 - jeden plik konfiguracji, przygotowanie do publikacji (3.6.2)

- `abuseipdb_report.py` 3.6.2 i `abuseipdb_send.sh` 1.1.1: cała konfiguracja lokalna trafia do jednego pliku,
  `~/.secrets/abuseipdb.conf` (`ABUSEIPDB_API_KEY`, `NTFY_TOPIC`, `NTFY_URL`, `OWN_NAME_MARKERS`, `EXCLUDE`),
  objaśnionego linia po linii w `abuseipdb.conf.example`. Plik jest parsowany jako tekst, nigdy nie wykonywany; nowe
  `--config` i `ABUSEIPDB_CONFIG`.
- Znaczniki własnych nazw nie są już zaszyte w kodzie. Działają fail-closed: pusta lista powoduje ostrzeżenie generatora,
  a wrapper na żywo odmawia wysyłki i wysyła alert ntfy.
- Osobne pliki `abuseipdb_api_key`, `ntfy_topic` i `abuseipdb_exclude.txt` nadal działają jako przestarzały zapas;
  config ma pierwszeństwo, a wykluczenia z obu źródeł są łączone. Wrapper loguje ostrzeżenie, gdy czyta stary plik
  klucza. Zmigruj je i usuń.
- Wygenerowany CSV dla tego samego wejścia jest bez zmian.
- Dane osobowe i szczegóły serwera usunięte z kodu, testów i dokumentacji (przykładowe ścieżki, loginy, własne domeny,
  odwołania do skryptów administracyjnych). Testy używają `example.org` i zarezerwowanych zakresów adresów.
- `tools/pre-commit` dostał skan prywatności dodawanych linii (znaczniki własnych nazw z lokalnego configu, prawdziwe
  klucze, staged plik konfiguracji). Nowe testy parsera configu, pierwszeństwa i reguły fail-closed.
- Projekt jest wydany na licencji MIT (`LICENSE`); README ma sekcje Licencja i Autor.
- Publiczna historia repozytorium zaczyna się od jednego czystego commita.

## 2026-09-28 - reguła wersjonowania (3.6.1)

- Nowa reguła numeracji (patrz wyżej): `Z` rośnie o 1 przy każdej zacommitowanej i wypchniętej zmianie.
- Aktualna wersja `abuseipdb_report.py` jest widoczna na początku README, każdego dokumentu i obu changelogów.
- Hook pre-commit i test jednostkowy sprawdzają, że wersja w dokumentach zgadza się z `SCRIPT_VERSION` oraz że commit
  podnosi wersję dokładnie o jeden krok.

## 2026-09-28 - wydzielenie projektu, kod wyłącznie po angielsku (3.6.0)

- `abuseipdb_report.py` 3.6.0: docstring, komentarze, komunikaty i `--help` przetłumaczone na angielski; nowa opcja
  `--version`. Wygenerowany CSV jest bajt w bajt identyczny jak w 3.5 dla tego samego wejścia.
- `abuseipdb_send.sh` 1.1.0: komentarze, linie logu i alerty ntfy przetłumaczone na angielski. Logika bez zmian.
- Projekt przeniesiony do własnego repozytorium i katalogu.
- Testy przeniesione do repozytorium; test zewnętrznego skryptu monitorującego zostaje poza nim.
- Dodany hook pre-commit (`tools/pre-commit`) i dokumentacja dwujęzyczna (EN/PL).

## 2026-09-28 - wcześniejsza historia (zanim projekt miał własne repozytorium)

- `abuseipdb_report.py` 3.5 i `abuseipdb_send.sh` 1.0: rozłączne okna czasowe (`--after`,
  `--before`), znacznik ostatniego udanego zgłoszenia, blokada 20 h, `Accept: application/json`, kontrola kodu HTTP i
  odpowiedzi JSON, klucz API przez stdin, powtórki tylko dla błędów przejściowych, alerty ntfy.
- `abuseipdb_report.py` 3.4: licznik unikalnych zdarzeń zamiast sumy po scenariuszach, okno ataku
  z `start_at`/`stop_at`, `http-open-proxy` przeniesione z kategorii 9 do 14, ścisły regex logowania SSH, protokół z
  pola `service` zdarzeń, filtr adresów nieglobalnych (CGNAT), wykluczone własne adresy publiczne, trwała lista
  zaufanych IP z SSH, tryb `--validate` i automatyczna walidacja wyjścia.
- `abuseipdb_report.py` 3.3 i wcześniejsze: pierwszy działający generator wywoływany
  jednolinijkowym poleceniem crona.
