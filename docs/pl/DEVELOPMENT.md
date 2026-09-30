[English](../DEVELOPMENT.md) | **Polski**

Wersja: 3.6.16 (`abuseipdb_report.py`)

# Rozwój

## Układ repozytorium

```
abuseipdb_report.py     generator i walidator (Python, tylko biblioteka standardowa)
abuseipdb_send.sh       wrapper crona (bash)
tests/                  zestawy testów unittest
tools/pre-commit        hook repozytorium (włączenie: git config core.hooksPath tools)
AGENTS.md               zasady dla agentów AI (tylko po angielsku, bez polskiego odpowiednika)
docs/, docs/pl/         dokumentacja (angielska, polska)
README.md, README.pl.md, CHANGELOG.md, CHANGELOG.pl.md
```

## Workflow

To workflow opiekuna projektu. Kontrybutorzy: patrz [CONTRIBUTING.pl.md](../CONTRIBUTING.pl.md); nie podnosicie wersji
i niczego nie wdrażacie.

1. Edytuj i testuj lokalnie w klonie repozytorium.
2. Zaktualizuj dokumentację i changelog w obu językach (patrz zasady językowe niżej).
3. Podnieś wersję (patrz Wersjonowanie), zrób commit z komunikatem po angielsku, potem push.
4. Wdrożenie na serwerze: `git pull --ff-only` w katalogu instalacji, potem `./abuseipdb_send.sh --dry-run`.
5. Nigdy nie edytuj ręcznie plików w katalogu instalacji; kopia robocza musi pozostać czysta, żeby `--ff-only`
   zawsze działało.

Cron uruchamia skrypty na żywo, więc zepsuty push trafia na produkcję przy następnym pullu. Hook pre-commit i testy
mają to wychwycić wcześniej.

## Testy

```bash
python3 -m unittest discover -v tests                   # wszystko (testy wrappera są pomijane bez narzędzi Linuksa)
python3 -m unittest -v tests/test_abuseipdb_report.py   # tylko generator, działa także na macOS
# Uruchom testy także na NAJSTARSZYM wspieranym Pythonie (3.9), nie tylko na najnowszym: parsowanie czasu różni się przed 3.11.
```

- Testy wrappera wymagają Linuksa (`flock`, GNU `date`, `jq`). Uruchamiaj je na serwerze w klonie albo w kontenerze
  z Linuksem. Workflow GitHub Actions `.github/workflows/tests.yml` uruchamia cały zestaw na Ubuntu z najstarszym i
  najnowszym wspieranym Pythonem przy każdym pushu i pull requeście.
- `curl`, generator i `ntfy` to atrapy; żaden test nie dotyka AbuseIPDB ani sieci.
- Po zmianie bezpiecznika zrób test mutacyjny: tymczasowo zepsuj bezpiecznik (na przykład `MAX_AGE_DAYS = 600` albo
  pusty `EXCLUDE_SCENARIOS`) i sprawdź, że któryś test pada. Cztery mutanty są znanymi równoważnikami: końcowa asercja
  ASCII w `build_rows` (obrona warstwowa za `sanitize_comment`), kontrola prefiksu formuły w walidatorze,
  pokryta przez `sanitize_comment`, surowa forma zgłaszanego IP (tak jak zapisano w alercie) w `leaks_identity`,
  którą pokrywa już forma kanoniczna, oraz usuwanie końcowego backslasha po `truncate_bytes` w `build_rows` (próbki są
  dodawane tylko, dopóki komentarz się mieści, więc przycinanie dziś niczego nie obcina).
- Tłumaczenie lub refaktoryzacja musi zachować wygenerowany CSV bajt w bajt dla tego samego `--input-json`; porównaj
  stare i nowe wyjście na fikstury.

## Wersjonowanie

- Format `X.Y.Z`. Wersją projektu jest wersja `abuseipdb_report.py` (`SCRIPT_VERSION` i nagłówek docstringu). Każda
  zmiana zacommitowana i wypchnięta podnosi `Z` o 1 (3.6.1, 3.6.2, ...). Gdy `Z` dojdzie do 99, następna wersja podnosi
  `Y` o 1 i zeruje `Z` (po 3.6.99 następna to 3.7.0). Duża zmiana (`X`) to świadoma, ręczna decyzja.
- `abuseipdb_send.sh` ma własny `SCRIPT_VERSION` i podlega tej samej regule, gdy wrapper się zmienia (zaktualizuj też
  test sprawdzający jego napis wersji).
- W tym samym commicie zaktualizuj: wersję w skrypcie, linię `Version:` na początku `README.md` i każdego dokumentu w
  `docs/`, linię `Wersja:` w każdym polskim odpowiedniku oraz oba changelogi.
- Wymusza to hook pre-commit: dokumenty muszą pokazywać tę samą wersję co `SCRIPT_VERSION`, a commit, który zmienia
  wersję, musi ją podnieść dokładnie o jeden krok. Commit, który wersji nie rusza, przechodzi przez hook, więc
  kontrybutorzy nigdy nie muszą jej zmieniać: opisują zmianę w sekcji "Unreleased" w `CHANGELOG.md`, a opiekun
  podnosi wersję i uzupełnia `CHANGELOG.pl.md` przy scalaniu. Spójność sprawdza też `tests/test_versioning.py`.

## Zasady językowe

- Kod, komentarze, komunikaty logów i błędów, `--help`, alerty, testy i komunikaty commitów są wyłącznie po
  angielsku.
- Szablony zgłoszeń (`TPL_*`) muszą pozostać angielskie; są publikowane w AbuseIPDB.
- README, każdy dokument w `docs/` i changelog istnieją po angielsku (domyślnie) i po polsku. Angielski jest
  źródłem, polski tłumaczeniem. Zmiana w jednym języku nie jest skończona, dopóki drugi nie zostanie
  zaktualizowany.
- Pary plików: `README.md` i `README.pl.md`, `CHANGELOG.md` i `CHANGELOG.pl.md`, `docs/X.md` i `docs/pl/X.md`.
  Każdy plik zaczyna się linią przełącznika języka. Hook pre-commit odmawia commita, który zawiera tylko jedną stronę
  pary albo w którym liczba nagłówków się różni.
- `AGENTS.md` jest jedynym wyjątkiem: tylko po angielsku, bez polskiego odpowiednika i bez linii wersji, bo czytają go
  agenci, a czytelnik nie wybiera języka. Aktualizuj go razem z tymi zasadami, gdy się zmieniają.
- Kontrybutorzy piszą tylko po angielsku (patrz [CONTRIBUTING.pl.md](../../CONTRIBUTING.pl.md)). Commitują z
  `EN_ONLY=1`, co sprawia, że hook pomija wyłącznie regułę parowania. Polską stronę dodaje opiekun (patrz następna
  sekcja).

## Przyjmowanie pull requesta

Rutyna opiekuna dla wkładu z zewnątrz. Repozytorium na komputerze opiekuna jest źródłem prawdy, więc pull requesta
nigdy nie scala się przyciskiem GitHuba (prywatne repozytorium zostałoby w tyle).

1. Ściągnij go lokalnie (`git fetch <remote> pull/N/head` albo gałąź kontrybutora) i przeczytaj diff. Mógł go napisać
   asystent kontrybutora: argumentem są testy i opis, więc sprawdź także je.
2. Uruchom cały zestaw testów i hook pre-commit. Jeśli dotknięty jest bezpiecznik, zrób test mutacyjny samodzielnie.
3. Dodaj polskie tłumaczenie każdego zmienionego angielskiego dokumentu w osobnym commicie na wierzchu wkładu
   (źródłem pozostaje angielski; kontrybutor nie musi tłumaczyć). Przeczytaj tłumaczenie raz: to kontrola opiekuna, że
   zmiana została zrozumiana.
4. Podnieś wersję (patrz Wersjonowanie) i uzupełnij oba changelogi, przenosząc notatkę kontrybutora z "Unreleased" do
   nowego wpisu i wymieniając go tam.
5. Wypchnij najpierw do prywatnego remote'a, wdróż i sprawdź na serwerze, dopiero potem do publicznego.

## Dodawanie scenariusza lub kategorii

1. Dodaj scenariusz do `CATEGORY_MAP` z najsłabszym zestawem kategorii, który log naprawdę uzasadnia. Dla scenariusza
   `crowdsecurity` użyj krótkiej nazwy (`ssh-bf`), dla scenariusza dowolnego innego autora PEŁNEJ nazwy (`autor/nazwa`);
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
- `tools/pre-commit` skanuje też linie dodawane przez commit. Jeśli lokalny config ma `OWN_NAME_MARKERS`, każda dodana
  linia zawierająca któryś z nich jest odrzucana (to trzyma twoje domeny i nazwę hosta poza repozytorium). Odrzuca też
  staged `abuseipdb.conf`, linię wyglądającą na prawdziwy klucz API (80 znaków szesnastkowych) oraz prawdziwe wartości w
  liniach `ABUSEIPDB_API_KEY=` / `NTFY_TOPIC=`. Dozwolone są tylko dane kontaktowe autora: adres e-mail, strona, imię i
  nazwisko oraz adres projektu na GitHubie. Bez configu skan własnych nazw jest pomijany z komunikatem.

## Lista kontrolna przed publicznym repozytorium

- Licencja to MIT (`LICENSE`); utrzymuj spójność linii praw autorskich i sekcji "Licencja" w README.
- Przeskanuj drzewo i historię pod kątem sekretów, adresów i nazw hostów. Historia publiczna zaczyna się od commita
  wydania 3.6.2 (wcześniejsza historia została zsquashowana) i była ponownie przeskanowana 2026-09-29; skanuj ją przed
  każdą nową publikacją.
- Ustawienia GitHuba: włącz prywatne zgłaszanie podatności (patrz `SECURITY.pl.md`) i wymagaj przejścia workflow
  `tests` przed scaleniem do `main`.
- Zachowaj uwagę "nieoficjalny, niezwiązany" w obu README.
- Sprawdź, że żaden dokument nie zawiera prawdziwej nazwy hosta, domeny, adresu ani tematu ntfy (skan prywatności robi
  to przy każdym commicie, jeśli twój config zawiera twoje nazwy).
