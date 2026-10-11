[English](../DEVELOPMENT.md) | **Polski**

# Rozwój

Dokument ma dwie części. Pierwsza, od "Układu repozytorium" do "Zasad językowych", dotyczy każdego, kto pracuje nad kodem
lub dokumentacją, także kontrybutorów. Druga, od "Workflow", opisuje pracę opiekuna: wdrażanie, wersje, wydania i
przyjmowanie cudzych pull requestów. Kontrybutorzy zaczynają od [CONTRIBUTING.md](CONTRIBUTING.md).

## Układ repozytorium

```
abuseipdb_report.py      generator i walidator (Python, tylko biblioteka standardowa)
abuseipdb_send.sh        wrapper crona (bash)
abuseipdb.conf.example   wzór konfiguracji, objaśnia każdą linię
tests/                   zestawy testów unittest (lista w sekcji "Testy")
tools/pre-commit         hook repozytorium dla plików
tools/commit-msg         hook repozytorium dla komunikatu commita
tools/lib-privacy.sh     reguły prywatności wspólne dla obu hooków (wczytywany, nie jest hookiem)
tools/deploy-check.sh    kontrola opiekuna: czy lokalny main, origin i github stoją na tym samym commicie?
tools/release_notes.sh   buduje notatki wydania z CHANGELOG.md (używa go release.yml)
.github/workflows/       CI: tests.yml (testy), release.yml (Release po wypchnięciu tagu)
.github/                 także szablony zgłoszeń, dyskusji i pull requesta
docs/, docs/pl/          dokumentacja (angielska, polska)
AGENTS.md                zasady dla agentów AI (tylko po angielsku, bez polskiego odpowiednika)
README.md, README.pl.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, LICENSE
```

## Przygotowanie środowiska

1. Python 3.9 lub nowszy; projekt używa tylko biblioteki standardowej, więc niczego się nie instaluje.
2. Raz na klon włącz hooki: `git config core.hooksPath tools`. Bez tego hooki nie działają i commit, który by odrzuciły,
   przejdzie bez słowa.
3. Opcjonalnie zainstaluj `shellcheck`. Bez niego hook sprawdza tylko składnię skryptów bash i pisze o tym uwagę;
   `shellcheck` i tak uruchamia CI.
4. Opiekun ma jeszcze lokalny config `~/.secrets/abuseipdb.conf` z `OWN_NAME_MARKERS`, bo od niego zależy skan prywatności
   (patrz "Konfiguracja i skan prywatności"). Kontrybutor bez configu może pracować: ta część skanu jest wtedy pomijana.
5. Sprawdź, że wszystko działa: `python3 -m unittest -v tests/test_abuseipdb_report.py`.

## Testy

```bash
python3 -m unittest discover -v tests                   # wszystko (testy wrappera są pomijane bez narzędzi Linuksa)
python3 -m unittest -v tests/test_abuseipdb_report.py   # tylko generator, działa także na macOS
```

Uruchom testy także na NAJSTARSZYM wspieranym Pythonie (3.9), nie tylko na najnowszym: parsowanie czasu różni się przed
3.11.

- Testy wrappera wymagają Linuksa (`flock`, GNU `date`, `jq`). Uruchamiaj je na serwerze w klonie albo w kontenerze
  z Linuksem.
- Workflow `.github/workflows/tests.yml` robi to samo na Ubuntu 24.04 (przypiętym celowo) z najstarszym i najnowszym
  wspieranym Pythonem, przy każdym pushu na `main` i każdym pull requeście. Najpierw sprawdza składnię (`bash -n`) i
  uruchamia `shellcheck -S error` na wrapperze i skryptach z `tools/`, potem cały zestaw testów.
- `curl`, generator i `ntfy` to atrapy; żaden test nie dotyka AbuseIPDB ani sieci.
- Zestawy w `tests/`:
  - `test_abuseipdb_report.py`: generator i walidator (działa wszędzie);
  - `test_abuseipdb_send.py`: wrapper z atrapami (wymaga Linuksa);
  - `test_hooks.py`: oba hooki w tymczasowym repozytorium;
  - `test_deploy_check.py` i `test_release_notes.py`: skrypty `tools/deploy-check.sh` i `tools/release_notes.sh`;
  - `test_versioning.py`: jedna wersja, wpis w changelogach, brak linii "Version:" w dokumentach;
  - `test_agents_file.py`: `AGENTS.md` jest po angielsku, jego ścieżki istnieją, nazywa bezpieczniki i nie rozjeżdża się
    z `CONTRIBUTING.md` ani `docs/COMPLIANCE.md`.
- **Test mutacyjny.** Po zmianie bezpiecznika (albo kodu obok niego) tymczasowo go zepsuj, na przykład ustaw
  `MAX_AGE_DAYS = 600` albo opróżnij `EXCLUDE_SCENARIOS`, i sprawdź, że któryś test pada; potem przywróć kod. Jeśli żaden
  test nie pada, bezpiecznik nie jest pilnowany i brakuje testu. Cztery mutanty są znane jako *równoważne*, czyli po takim
  zepsuciu program zachowuje się tak samo, więc żaden test nie może ich wykryć i brak czerwonego testu jest tu poprawnym
  wynikiem:
  - końcowa kontrola ASCII w `build_rows` (obrona warstwowa za `sanitize_comment`);
  - kontrola prefiksu formuły wewnątrz walidatora, pokryta przez `sanitize_comment`;
  - surowa postać zgłaszanego IP (tak jak zapisano w alercie) w `leaks_identity`, którą pokrywa już postać kanoniczna;
  - usuwanie końcowego backslasha po `truncate_bytes` w `build_rows`: próbki są dodawane tylko, dopóki komentarz się
    mieści, więc przycinanie dziś niczego nie obcina.
- Tłumaczenie lub refaktoryzacja musi zachować wygenerowany CSV bajt w bajt dla tego samego `--input-json`; porównaj
  stare i nowe wyjście na tym samym zestawie testowym (fixture).

## Hooki

Hooki leżą w `tools/` i działają po `git config core.hooksPath tools` (patrz "Przygotowanie środowiska"). `tools/pre-commit`
sprawdza pliki w indeksie, czyli to, co za chwilę trafi do commita (indeks to zestaw plików, które dodałeś przez
`git add`):

1. **Składnia:** `bash -n` i `shellcheck -S error` dla plików `*.sh`; kompilacja Pythona dla `*.py`.
2. **Pary EN/PL:** commit, który zawiera tylko jedną stronę pary dokumentów, jest odrzucany, tak samo jak para z różną
   liczbą nagłówków (patrz "Zasady językowe"). Hook liczy każdą linię zaczynającą się od `#`, także komentarz w bloku
   kodu, więc blok kodu z taką linią musi mieć odpowiednik w drugim języku.
3. **Wersje:** krok wersji i równość wersji w obu skryptach (patrz "Wersjonowanie").
4. **Skan prywatności** dodawanych linii (patrz "Konfiguracja i skan prywatności").
5. **Testy generatora** (około 15 s), gdy commit zmienia `abuseipdb_report.py` albo `tests/test_abuseipdb_report.py`;
   commit czegokolwiek innego pozostaje szybki. Hook testuje kopię indeksu, a nie Twój katalog roboczy, i pomija testy,
   gdy wcześniejsza kontrola już odrzuciła commit. Cały zestaw trwa kilka minut, a testy wrappera wymagają Linuksa, więc
   kompletną kontrolą pozostaje CI.

`tools/commit-msg` skanuje komunikat commita, który też jest publiczny; jego zakres opisuje sekcja "Konfiguracja i skan
prywatności".

Dwie zmienne wyłączają pojedyncze kontrole, a wszystkie pozostałe działają dalej:

- `EN_ONLY=1 git commit ...` pomija tylko regułę par EN/PL. To tryb kontrybutora: kontrybutor pisze tylko po angielsku,
  polską stronę dodaje opiekun. Opiekun może go też użyć do poprawki jednej strony pary (na przykład literówki w
  tłumaczeniu); hook nie porówna wtedy liczby nagłówków, więc sprawdź ją ręcznie.
- `NO_TESTS=1 git commit ...` pomija tylko testy generatora, na przykład przy commicie roboczym opiekuna. Test, który
  pada, naprawia się albo zgłasza; nigdy nie pomija się go, żeby przepchnąć commit.

`git commit --no-verify` wyłącza wszystkie kontrole naraz: nie używaj go. `tests/test_hooks.py` uruchamia oba hooki w
tymczasowym repozytorium.

## Dodawanie scenariusza lub kategorii

1. Dodaj scenariusz do `CATEGORY_MAP` z najsłabszym zestawem kategorii, który log naprawdę uzasadnia. Dla scenariusza
   autora `crowdsecurity` użyj krótkiej nazwy (`ssh-bf`), a dla scenariusza innego autora pełnej nazwy (`autor/nazwa`);
   bez wpisu nieznany scenariusz nie jest w ogóle zgłaszany.
2. Zdecyduj, czy należy do `EXCLUDE_SCENARIOS` lub `WEAK_ONLY_SCENARIOS`. (Operator, który chce tylko przestać
   zgłaszać scenariusz na własnym serwerze, używa `EXTRA_EXCLUDE_SCENARIOS` w configu zamiast zmieniać kod.)
3. Dodaj test, uruchom zestaw i zaktualizuj changelog.

## Konfiguracja i skan prywatności

- Jedyna lokalna konfiguracja to `~/.secrets/abuseipdb.conf` (wzór: `abuseipdb.conf.example`, który objaśnia każdą
  linię). Prawdziwe wartości nigdy nie trafiają do repozytorium; `abuseipdb.conf` jest w `.gitignore`.
- Testy nigdy nie dotykają prawdziwego configu: przekazują `--config` (generator) albo ustawiają `ABUSEIPDB_CONFIG` i
  pusty `HOME` (wrapper) oraz używają wyłącznie sztucznych kluczy, tematów i zarezerwowanych nazw `example.org` /
  `203.0.113.0/24`.
- `tools/pre-commit` skanuje linie dodawane przez commit:
  - jeśli lokalny config ma `OWN_NAME_MARKERS`, każda dodana linia zawierająca któryś z nich jest odrzucana (to trzyma
    Twoje domeny i nazwę hosta poza repozytorium); bez configu ten skan jest pomijany z uwagą;
  - odrzuca staged `abuseipdb.conf` oraz dodaną linię wyglądającą na prawdziwy klucz API (80 znaków szesnastkowych);
  - odrzuca linie `ABUSEIPDB_API_KEY=` i `NTFY_TOPIC=`, których wartość nie zaczyna się od `Y` lub `y`, czyli nie jest
    wzorcem w rodzaju `YOUR_...` / `your-...` z `abuseipdb.conf.example`.
- Dozwolone są tylko dane kontaktowe autora: adres e-mail, strona, imię i nazwisko oraz adres projektu na
  GitHubie. Domena jest dozwolona tylko samodzielnie: nazwa hosta pod nią (`host.<domena>`) lub inna skrzynka w niej nadal
  jest odrzucana.
- `tools/commit-msg` stosuje do KOMUNIKATU commita tylko dwie z tych reguł: wzorzec klucza API (działa zawsze, także bez
  configu) i `OWN_NAME_MARKERS` (bez configu pomijane po cichu). Nie sprawdza staged `abuseipdb.conf` ani linii
  `KEY=` / `TOPIC=`. Pomija własne linie komentarza `#` gita.

## Zasady językowe

- Kod, komentarze, komunikaty logów i błędów, `--help`, alerty, testy i komunikaty commitów są wyłącznie po
  angielsku.
- Szablony zgłoszeń (`TPL_*`) muszą pozostać angielskie; są publikowane w AbuseIPDB.
- README, każdy dokument w `docs/` i changelog istnieją po angielsku (domyślnie) i po polsku. Angielski jest
  źródłem, polski tłumaczeniem. Zmiana w jednym języku nie jest skończona, dopóki drugi nie zostanie
  zaktualizowany.
- Pary plików: `README.md` i `README.pl.md` (jedyny polski plik w katalogu głównym), każdy inny dokument `X.md` (w
  katalogu głównym lub w `docs/`) i `docs/pl/X.md`.
  Każdy plik zaczyna się linią przełącznika języka. Hook pre-commit odmawia commita, który zawiera tylko jedną stronę
  pary albo w którym liczba nagłówków się różni.
- `AGENTS.md` jest jedynym wyjątkiem: tylko po angielsku, bez polskiego odpowiednika, bo czytają go
  agenci, a czytelnik nie wybiera języka. Aktualizuj go razem z tymi zasadami, gdy się zmieniają.
- Kontrybutorzy piszą tylko po angielsku (patrz [CONTRIBUTING.md](CONTRIBUTING.md)). Commitują z
  `EN_ONLY=1`, co sprawia, że hook pomija wyłącznie regułę parowania. Polską stronę dodaje opiekun (patrz "Przyjmowanie
  pull requesta").

## Workflow

Od tego miejsca dokument opisuje pracę opiekuna. Kontrybutorzy: patrz [CONTRIBUTING.md](CONTRIBUTING.md) (fork, gałąź,
pull request); nie podnosisz wersji, niczego nie wdrażasz ani nie scalasz.

Są dwie ścieżki. Reguła praktyczna: jeśli po zmianie program zachowywałby się inaczej albo opis bezpiecznika mówiłby
co innego, użyj gałęzi.

| Wprost na `main` | Przez gałąź, zielone CI przed scaleniem |
|---|---|
| literówki i redakcja w `*.md`, które nie zmieniają opisu zachowania | `abuseipdb_report.py`, `abuseipdb_send.sh`, `abuseipdb.conf.example` |
| polskie tłumaczenia zgodne z angielskim źródłem | `tests/`, `tools/` (hooki i skrypty), `.github/workflows/` |
| wpisy w changelogu | zmiana ZNACZENIA bezpiecznika w opisie (`docs/pl/COMPLIANCE.md`, listy bezpieczników w `README.pl.md`, `AGENTS.md`) |
| poprawka opisu bezpiecznika, która tylko dopasowuje go do kodu działającego tak od dawna (po audycie opisu względem kodu) | zmiany tego workflow |

CI sprawdza kod, a nie treść dokumentów. Gałąź przy opisie bezpiecznika służy więc przeglądowi: zmiana znaczenia (na
przykład inne okno czasowe) musi przejść przez świadome przeczytanie. Dopasowanie opisu do kodu, który już tak działa,
znaczenia nie zmienia i może iść wprost na `main`.

### Ścieżka A, dokumentacja wprost na `main`

1. Edytuj, utrzymuj zgodność plików angielskich i polskich i uzupełnij oba changelogi, jeśli zmiana tam należy (patrz
   [Wersjonowanie](#wersjonowanie)). Zmiana dokumentacji nie podnosi wersji.
2. Zrób commit z komunikatem po angielsku; hook pre-commit uruchamia się sam przy `git commit`.
3. `git push origin main`, wdrożenie i sprawdzenie na serwerze (patrz "Wdrożenie" niżej), dopiero potem
   `git push github main`. Kolejność jest taka sama jak w ścieżce B i obowiązuje także po samej zmianie dokumentacji:
   serwer ma zawsze stać na `main`.

### Ścieżka B, kod przez gałąź

1. `git switch -c fix-krotki-opis`. Nazwa = typ, myślnik i temat (`fix-`, `feat-`, `test-`, `ci-`, `docs-`), małe litery,
   jeden temat na gałąź.
2. Edytuj i testuj lokalnie (`python3 -m unittest discover -v tests`). Rób commity po drodze, z komunikatami po angielsku.
   Te robocze commity nie ruszają wersji.
3. Ostatni commit gałęzi uzupełnia dokumentację i oba changelogi. Jeśli zmiana dotyka programu, podnosi też wersję, raz
   (patrz [Wersjonowanie](#wersjonowanie)); zmiana samych narzędzi dodaje zamiast tego linię w sekcji "Development".
4. `git push github fix-krotki-opis`. Gałęzie idą wyłącznie na `github`, gdzie działa CI; prywatny `origin` dostaje
   tylko `main`. Otwórz pull request z gałęzi do `main` (może być szkicem): workflow `tests` uruchamia się dla każdego
   pull requesta.
5. Poczekaj na zielony przebieg obu wersji Pythona. Jeśli jest czerwony, popraw na gałęzi i wypchnij ponownie.
6. Scal na swoim komputerze, nigdy przyciskiem GitHuba: `git switch main`, potem `git merge --ff-only fix-krotki-opis`.
   Jeśli Git odmówi, bo `main` się przesunął, zrób `git rebase main` na gałęzi i przetestuj ponownie. Rebase zmienia
   numery (SHA) commitów, więc gałąź już wypchniętą na `github` wypchnij jeszcze raz przez
   `git push --force-with-lease github fix-krotki-opis`. To dotyczy wyłącznie tej gałęzi roboczej, nigdy `main`;
   `--force-with-lease` odmawia, jeśli na `github` jest coś, czego nie masz. CI sprawdzało dotąd stare commity, więc
   poczekaj na nowy zielony przebieg i dopiero wtedy powtórz scalenie.
7. `git push origin main`, wdróż i sprawdź na serwerze (patrz "Wdrożenie" niżej), potem `git push github main`. GitHub sam
   oznaczy pull request jako scalony, bo jego commity są już w `main`.
8. Posprzątaj: `git branch -d fix-krotki-opis` i `git push github --delete fix-krotki-opis`.

### Wdrożenie

Dotyczy obu ścieżek, zawsze, także po samej zmianie dokumentacji. Na serwerze uruchom `git pull --ff-only` w katalogu
instalacji, potem `./abuseipdb_send.sh --dry-run`. Nigdy nie edytuj ręcznie plików w katalogu instalacji; kopia robocza
musi pozostać czysta, żeby `--ff-only` zawsze działało. Jeśli `git pull --ff-only` mimo to odmawia (na przykład po
scaleniu historii w jeden commit), zatrzymaj się: najpierw diagnoza tylko do odczytu (status, `origin/main..HEAD`, wersja),
bez ręcznych napraw.

Potem, we własnym klonie, uruchom `tools/deploy-check.sh`. Pobiera `origin` i `github` i mówi, czy lokalny `main` oraz oba
zdalne repozytoria stoją na tym samym commicie. Między pushem na `origin` a pushem na `github` pokaże `github` jako
`NOT PUSHED YET`, co jest oczekiwane; `AHEAD`, `DIVERGED` albo `WARNING` o kolejności oznaczają: zatrzymaj się i
sprawdź. Skrypt tylko czyta, nigdy nie wypisuje adresu zdalnego repozytorium i nie dotyka serwera: tam
`git log -1 --format=%h` w katalogu instalacji musi pokazać commit wypisany przez skrypt.

Cron uruchamia skrypty na żywo, więc zepsuty push trafia na produkcję przy następnym pullu. Hook pre-commit, testy i
zielone CI przed scaleniem mają to wychwycić wcześniej.

## Przypięte akcje CI

Workflow używają dwóch akcji: `actions/checkout` (w `tests.yml` i `release.yml`) oraz `actions/setup-python` (w
`tests.yml`). Każda jest przypięta do pełnego, 40-znakowego skrótu commita z tagiem w komentarzu na końcu linii
(`@<sha>  # v7`). Tag to ruchoma etykieta, skrót nie, więc skompromitowane repozytorium akcji nie zmieni tego, co się
uruchamia. Podobnie runner jest przypięty do `ubuntu-24.04`, a nie do `ubuntu-latest`: etykieta `latest` zmienia
system według harmonogramu GitHuba (jq, shellcheck i bash zmieniłyby się bez naszej decyzji). W `tests.yml`
`checkout` nie zostawia tokenu w `.git/config` (`persist-credentials: false`), a job ma 10-minutowy limit czasu.

Dependabota nie ma (jego pull requesty kolidowałyby ze scalaniem lokalnie przez `--ff-only`), więc sprawdzaj nowe wersje
ręcznie mniej więcej raz na kwartał i gdy GitHub ostrzega o wycofanej:

1. Znajdź commit, na który wskazuje nowy tag: `gh api repos/actions/checkout/git/ref/tags/<tag> --jq .object` (jeśli
   typ to `tag`, a nie `commit`, przejdź jeszcze raz przez `.object.sha` w `git/tags/<sha>`).
2. Podmień skrót i komentarz w KAŻDYM workflow, który używa tej akcji (`grep -n "actions/" .github/workflows/*.yml`),
   zmianę zrób na gałęzi (ścieżka B) i przed scaleniem poczekaj na CI w pull requeście. `release.yml` uruchamia się dopiero
   po wypchnięciu tagu, więc CI pull requesta go nie sprawdza: wpisz w nim dokładnie ten sam skrót, który przeszedł w
   `tests.yml`.

## Wersjonowanie

Projekt ma **jedną wersję** `X.Y.Z`: `SCRIPT_VERSION` w `abuseipdb_report.py`, powtórzoną w `abuseipdb_send.sh` (hook i
`tests/test_versioning.py` pilnują, żeby obie były równe). Odpowiada osobie uruchamiającej narzędzie na jedno pytanie:
"czy program się zmienił?". Dlatego rośnie, gdy zmienia się **program**, i tylko wtedy:

| Krok | Kiedy | Przykład |
|---|---|---|
| `Z` o 1 | poprawka albo każda zmiana zachowania `abuseipdb_report.py` lub `abuseipdb_send.sh` (nowa kontrola, zmieniony komunikat, alert, kod wyjścia lub walidacja) albo znaczenia linii w `abuseipdb.conf.example`; `Z` nie ma górnej granicy (po 3.6.99 jest 3.6.100) | 3.6.34 na 3.6.35 |
| `Y` o 1, `Z` na 0 | nowa funkcja lub nowy klucz konfiguracji | 3.6.35 na 3.7.0 |
| `X` o 1, `Y` i `Z` na 0 | świadoma, ręczna decyzja przy zmianie łamiącej istniejące instalacje | 3.7.0 na 4.0.0 |

- **Nie podnoszą wersji:** zmiany w `tools/` (hooki), `tests/`, `.github/` (CI, formularze), `docs/`, README,
  `CONTRIBUTING.md`, `AGENTS.md` i innych szablonach, podobnie jak zmiana dotykająca wyłącznie komentarzy w skryptach.
  Te, które są ważne dla opiekuna i kontrybutorów (nowa lub poprawiona reguła hooka, zmiana CI, nowy dokument), dostają
  jedną linię z datą w sekcji "Development" w obu changelogach; literówka nie potrzebuje wpisu.
- **Gdzie wersja jest zapisana, i nigdzie indziej:** `SCRIPT_VERSION` w dwóch skryptach oraz nagłówki
  `## X.Y.Z - data` w `CHANGELOG.md` i `docs/pl/CHANGELOG.md`. Dokumenty nie mają linii "Wersja:" (była głównym źródłem
  zapomnianych edycji), a komentarze nagłówkowe skryptów nie powtarzają numeru. `tests/test_versioning.py` zawodzi, gdy
  linia "Version:" lub "Wersja:" wróci.
- **Przy podnoszeniu wersji** zrób to w ostatnim commicie gałęzi i dokładnie raz: dwa podniesienia na jednej gałęzi dałyby
  po scaleniu wzrost o dwa kroki, a hook porównuje tylko każdy commit z poprzednim. Zaktualizuj `SCRIPT_VERSION` w obu
  skryptach oraz dodaj wpis `## X.Y.Z - data` w obu changelogach (`tests/test_versioning.py` szuka tego nagłówka).
  Opiekun podaje proponowany numer i powód przed commitem.
- **Co pilnuje hook:** commit, który zmienia wersję, musi zrobić dokładnie jeden dozwolony krok (`Z+1`, `Y+1` przy `Z=0`
  albo `X+1` przy `Y=Z=0`), a wrapper musi mieć tę samą wersję co generator. Commit, który wersji nie rusza, przechodzi,
  więc kontrybutorzy nigdy nie muszą jej zmieniać: opisują zmianę w sekcji "Unreleased" w `CHANGELOG.md`, a opiekun
  decyduje, czy podnosi wersję, uzupełnia `docs/pl/CHANGELOG.md` i przenosi notatkę przy scalaniu.

### Tagi i Releases

Numer wersji i wydanie to dwie różne rzeczy. Każda zmiana programu podnosi numer, więc `main` przechodzi przez wiele
wersji; **wydaniem** (release) zostają tylko te, które wybierze opiekun.

- Wydanie to tag git `vX.Y.Z` na commicie, który jest już scalony, wdrożony i sprawdzony na serwerze, oraz utworzony z
  niego GitHub Release. Oznacza wersję, na którą warto wskazać operatorom. Decyzja należy do opiekuna; nic nie jest
  tagowane automatycznie.
- Utwórz tag adnotowany (`git tag -a vX.Y.Z -m "Release X.Y.Z"`) i wypchnij go po nazwie do każdego remote'a osobno:
  `git push origin vX.Y.Z`, potem `git push github vX.Y.Z`. Nigdy `git push --tags`: opublikowałoby wszystkie lokalne tagi.
- Wypchnięcie tagu na GitHub uruchamia `.github/workflows/release.yml`. Sprawdza, czy tag równa się `SCRIPT_VERSION` i czy
  changelog ma wpis dla tej wersji (inaczej zatrzymuje się i niczego nie tworzy), buduje notatki przez
  `tools/release_notes.sh` i tworzy Release. Notatki zawierają każdy wpis changeloga nowszy niż poprzedni tag, bo między
  dwoma wydaniami numer rośnie wiele razy, a operator aktualizujący potrzebuje wszystkich tych notatek.
- **Tagu i wydania nie da się cofnąć.** Release jest niezmienny (GitHub oznacza go jako *immutable*), a ruleset
  `protect-version-tags` blokuje usuwanie i przesuwanie tagów wersji. Dlatego przed wypchnięciem tagu sprawdź na sucho to,
  co sprawdzi workflow: `tools/release_notes.sh <wersja> <poprzednia wersja>` ma wypisać oczekiwane wpisy, tag musi równać
  się `SCRIPT_VERSION` w obu skryptach, a oba changelogi muszą mieć wpis `## X.Y.Z - data`. Gdy workflow zatrzyma się po
  wypchnięciu tagu, tag już zostaje.
- Błędne wydanie naprawia się **kolejną wersją i kolejnym tagiem**, a nie usuwaniem. Usunięcie opublikowanego tagu lub
  Release to decyzja opiekuna: wymaga wyłączenia rulesetu, a GitHub może i tak nie pozwolić na ponowne użycie tej samej
  nazwy tagu.

## Przyjmowanie pull requesta

Rutyna opiekuna dla wkładu z zewnątrz. Kontrybutorzy pracują w forku i otwierają pull request; nikt inny nie ma zapisu.
Repozytorium na komputerze opiekuna jest źródłem prawdy, więc pull requesta nigdy nie scala się przyciskiem GitHuba
(prywatne repozytorium zostałoby w tyle).

1. Ściągnij go do lokalnej gałęzi przeglądowej i przeczytaj diff: `git fetch github pull/N/head:pr-N`, potem
   `git switch pr-N`. Mógł go napisać asystent kontrybutora: argumentem są testy i opis, więc sprawdź także je.
2. Uruchom cały zestaw testów i hook pre-commit (`EN_ONLY=1`, jeśli pull request zmienia tylko angielską stronę pary
   dokumentów). Jeśli dotknięty jest bezpiecznik, zrób test mutacyjny samodzielnie. Zatwierdź przebieg CI pull requesta
   na GitHubie (pierwszy przebieg zewnętrznego kontrybutora wymaga Twojego kliknięcia).
3. Dodaj polskie tłumaczenie każdego zmienionego angielskiego dokumentu w osobnym commicie na `pr-N` (źródłem
   pozostaje angielski; kontrybutor nie musi tłumaczyć). Przeczytaj tłumaczenie raz: to kontrola opiekuna, że zmiana
   została zrozumiana.
4. Podnieś wersję, jeśli zmiana dotyka programu (patrz [Wersjonowanie](#wersjonowanie)), i uzupełnij oba changelogi,
   przenosząc notatkę kontrybutora z "Unreleased" do nowego wpisu (albo linii w sekcji "Development" dla samych
   narzędzi) i wymieniając go tam.
5. Scal na swoim komputerze: `git switch main`, `git merge --ff-only pr-N` (albo najpierw `git rebase main` na `pr-N`,
   jeśli `main` się przesunął). Wypchnij najpierw do prywatnego remote'a, wdróż i sprawdź na serwerze, dopiero potem do
   publicznego. GitHub oznaczy pull request jako scalony lub zamknięty. Usuń `pr-N`.

Kontrybutora, którego pull requesty scaliłeś i któremu ufasz, można później zaprosić jako współpracownika, żeby mógł
wypychać gałęzie do tego repozytorium. Nic innego się nie zmienia: gałąź nadal scala wyłącznie opiekun.

## Stałe kontrole

Repozytorium jest publiczne, a historia opublikowana jest nieodwracalna. Te kontrole obowiązują stale:

- Licencja to MIT (`LICENSE`); utrzymuj spójność linii praw autorskich i sekcji "Licencja" w README.
- Zachowaj uwagę "nieoficjalny, niezwiązany" w obu README.
- Historia publiczna zaczyna się od commita wydania 3.6.2 (wcześniejsza historia została scalona w jeden commit). Przed
  każdą operacją, która przepisuje historię lub publikuje ją na nowo, przeskanuj drzewo i historię pod kątem sekretów,
  adresów i nazw hostów.
- Na GitHubie mają pozostać aktywne: prywatne zgłaszanie podatności (patrz `docs/pl/SECURITY.md`) oraz rulesety
  `protect-main` (blokuje force-push i usuwanie gałęzi, wymaga liniowej historii) i `protect-version-tags` (tagi wersji). Nie wymagaj sprawdzenia
  `tests` w rulesecie `protect-main`: wynik istnieje dopiero po pushu, więc wymóg blokowałby także bezpośrednie pushe
  dokumentacji opiekuna. Opiekun ogląda zielony przebieg gałęzi przed jej scaleniem.
- Sprawdź, że żaden dokument nie zawiera prawdziwej nazwy hosta, domeny, adresu ani tematu ntfy (skan prywatności robi
  to przy każdym commicie, jeśli Twój config zawiera Twoje nazwy).
