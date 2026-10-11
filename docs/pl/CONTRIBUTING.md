[English](../../CONTRIBUTING.md) | **Polski**

# Współpraca

Dziękuję za pomoc. To narzędzie publikuje dane z kont AbuseIPDB swoich użytkowników, a fałszywe zgłoszenie może
skończyć się zawieszeniem konta. Każdą zmianę ocenia się najpierw jednym pytaniem: czy może sprawić, że narzędzie
zgłosi coś, co nie jest prawdziwym, lokalnie zaobserwowanym atakiem, albo ujawni coś o operatorze? Wygoda jest wtórna.

| Chcesz | Dokąd |
|---|---|
| zgłosić błąd albo scenariusz pomijany jako nieznany | [Issues](https://github.com/arcymonek/reportabuseipdb/issues/new/choose), z formularzem zgłoszenia błędu |
| zaproponować zmianę albo zadać pytanie | [Discussions](https://github.com/arcymonek/reportabuseipdb/discussions) |
| zgłosić podatność | prywatnie, zobacz [SECURITY.md](SECURITY.md) |
| wysłać kod albo dokumentację | fork i pull request, zobacz "Jak wysłać zmianę" niżej |

## Zgłaszanie błędu

Otwórz zgłoszenie (issue) z formularza zgłoszenia błędu. Formularz pyta o wersję (`./abuseipdb_send.sh --version`,
`python3 abuseipdb_report.py --version`), wersje CrowdSeca i Pythona, opcjonalnie o dystrybucję, oraz o właściwe linie z
`abuseipdb_cron.log` albo z `--dry-run`.

Zanim cokolwiek wkleisz, usuń własne nazwy domen i hostów, ścieżkę katalogu domowego, temat ntfy i własne adresy IP.
Nigdy nie wklejaj klucza API ani pliku konfiguracji. Podatność zgłaszaj według [SECURITY.md](SECURITY.md), a nie
w publicznym zgłoszeniu.

## Proponowanie zmiany

Przy czymś większym niż literówka najpierw rozpocznij dyskusję (kategoria Ideas) i opisz problem. Zmiany bezpieczników
(lista jest w sekcji "Hard safeguards" w [AGENTS.md](../../AGENTS.md), po angielsku, uzasadnienia w
[docs/pl/COMPLIANCE.md](COMPLIANCE.md)) są omawiane, zanim powstanie kod. Pull request, który osłabia któryś z nich,
wymaga bardzo dobrego powodu i będzie z tym na uwadze przeglądany.

Nowy scenariusz CrowdSeca w `CATEGORY_MAP` wymaga najsłabszego zestawu kategorii, który log naprawdę uzasadnia, oraz
testu; patrz [docs/pl/DEVELOPMENT.md](DEVELOPMENT.md). Jeśli chcesz tylko przestać zgłaszać scenariusz na
własnym serwerze, użyj `EXTRA_EXCLUDE_SCENARIOS` w swoim configu. Jeśli chcesz, żeby scenariusz z nowej kolekcji
CrowdSeca był zgłaszany, otwórz issue z formularzem zgłoszenia błędu i podaj jego pełną nazwę (`autor/nazwa`) oraz
opis, co wykrywa, zamiast edytować kod na swoim serwerze.

## Przygotowanie i testy

Potrzebujesz Pythona 3.9 lub nowszego i niczego więcej: narzędzie używa wyłącznie biblioteki standardowej, więc proszę
nie dodawać zależności. CI uruchamia testy na Pythonie 3.9 i na najnowszym, więc unikaj składni od 3.10 wzwyż
(`match`, `X | Y` w adnotacjach typów).

```bash
python3 -m unittest discover -v tests     # testy generatora działają wszędzie; testy wrappera wymagają Linuksa
git config core.hooksPath tools           # opcjonalnie: dwa hooki opisane niżej
```

Testy wrappera wymagają Linuksa (`flock`, GNU `date`, `jq`) i gdzie indziej są pomijane. Workflow GitHub Actions
uruchamia cały zestaw na Ubuntu dla każdego pull requesta; musi przejść przed scaleniem.

Druga komenda włącza dwa hooki. `pre-commit` sprawdza składnię, pary EN/PL, wersje i prywatność, a gdy commit zmienia
`abuseipdb_report.py` albo jego plik testów, uruchamia też testy generatora (około 15 s). `commit-msg` stosuje ten sam
skan prywatności do komunikatu commita. Skan własnych nazw hostów czyta `OWN_NAME_MARKERS` z twojego własnego configu
(`~/.secrets/abuseipdb.conf` albo plik wskazany przez `ABUSEIPDB_CONFIG`); bez takiego pliku jest pomijany z komunikatem,
więc dane prywatne w diffie sprawdź sam.

Hook odmawia commita, który zmienia tylko angielską stronę pary dokumentów. Skoro piszesz tylko po angielsku,
commituj przez `EN_ONLY=1 git commit ...`: pomija to jedną regułę i zostawia wszystkie pozostałe kontrole (w tym skan
prywatności). Nie używaj `--no-verify`, który wyłącza wszystkie kontrole. Test, który pada, napraw zamiast pomijać.

## Jak wysłać zmianę

Nie potrzebujesz uprawnień zapisu ani zaproszenia: pracuj w forku.

1. Zrób fork repozytorium na GitHubie (przycisk "Fork"), potem sklonuj **swój fork**.
2. Utwórz gałąź na jeden temat, nazwaną według typu i tematu (`fix-`, `feat-`, `test-`, `ci-` albo `docs-`):
   `git switch -c fix-krotki-opis`.
3. Wprowadź zmianę, uruchom testy, zrób commit z komunikatem po angielsku (patrz "Pull requesty" niżej).
4. Wypchnij gałąź do swojego forka: `git push -u origin fix-krotki-opis`.
5. Na GitHubie otwórz pull request z twojej gałęzi do `main` tego repozytorium (GitHub pokaże przycisk po pushu).
6. Workflow `tests` uruchomi się na twoim pull requeście; pierwszy przebieg nowego kontrybutora wymaga zatwierdzenia
   przez opiekuna. Poprawiaj to, co pada, dopychając kolejne commity do tej samej gałęzi.
7. Scala wyłącznie opiekun. Nie musisz utrzymywać gałęzi aktualnej: jeśli `main` się przesunie, opiekun sam się tym
   zajmie. Jeśli zostaniesz o to poproszony albo GitHub zgłosi konflikt, dodaj raz to repozytorium jako drugi remote
   (`git remote add upstream https://github.com/arcymonek/reportabuseipdb.git`) i użyj `git pull --rebase upstream main`.
   Rebase przepisuje twoją gałąź, więc wypchnij ją do swojego forka przez `git push --force-with-lease`.

Opiekun stosuje zaakceptowane zmiany na swoim komputerze, dodaje polskie tłumaczenie oraz, gdy zmienia się program,
wersję (patrz "Przyjmowanie pull requesta" w [docs/pl/DEVELOPMENT.md](DEVELOPMENT.md#przyjmowanie-pull-requesta)).
GitHub oznacza potem twój pull request jako scalony lub zamknięty. Stałych kontrybutorów można później zaprosić do
wypychania gałęzi bezpośrednio do tego repozytorium; scala nadal opiekun.

## Pull requesty

- Jeden temat na pull request. Kod ma być prosty i czytelny; komentarze wyjaśniają dlaczego, a nie tylko co. Szablon
  pull requesta ma listę kontrolną: wypełnij ją rzetelnie i napisz, czego nie sprawdzono.
- Kod, komentarze, komunikaty, testy, komunikaty commitów, zgłoszenia, pull requesty i komentarze w przeglądzie są
  wyłącznie po angielsku. Opiekun jest Polakiem i może czytać twój tekst w tłumaczeniu, a odpowiadać po angielsku; pisz
  prosto, a wszystko będzie zrozumiałe. Szablony zgłoszeń (`TPL_*`) muszą zostać po angielsku, bo są publikowane w
  AbuseIPDB.
- Dokumentacja istnieje po angielsku i po polsku (`README.md` i `README.pl.md`, każdy inny `X.md` i `docs/pl/X.md` itd.).
  Wystarczy, że napiszesz plik angielski; nie musisz znać polskiego. Polskie tłumaczenie dodaje opiekun projektu przed
  scaleniem, więc proszę, nie tłumacz maszynowo na własną rękę.
- Nie podnoś wersji. Opisz zmianę w sekcji "Unreleased" w `CHANGELOG.md`; opiekun decyduje, czy wersja rośnie
  (rośnie, gdy zmienia się program), i uzupełnia `docs/pl/CHANGELOG.md` przy scalaniu.
- Testy używają wyłącznie sztucznych danych: adresów zarezerwowanych (`203.0.113.0/24`, `198.51.100.0/24`,
  `2001:db8::/32`), nazw `example.org` / `.example` / `.test`, sztucznych kluczy i tematów. Adresy zarezerwowane nie są
  "globalne", więc filtr samego narzędzia je odrzuca; gdy test potrzebuje adresu, który przechodzi filtr, użyj znanego
  publicznego resolvera jako zastępczego atakującego. Nigdy prawdziwego klucza API, nigdy prawdziwej wysyłki do
  AbuseIPDB, nigdy własnych nazw hostów ani adresów.
- Refaktoryzacja musi zachować wygenerowany CSV bajt w bajt dla tego samego `--input-json`. Po zmianie bezpiecznika
  zepsuj go celowo i sprawdź, że test pada (test mutacyjny, patrz [docs/pl/DEVELOPMENT.md](DEVELOPMENT.md)).

## Praca z asystentem AI

Wkład tworzony z pomocą AI jest mile widziany; opiekun też tak pracuje.

- Wskaż swojemu asystentowi plik [AGENTS.md](../../AGENTS.md): zawiera zasady (bezpieczniki, których nie wolno
  osłabiać, czego nigdy nie robić, konwencje i kilka nieoczywistych faktów o danych) w formacie, który wielu agentów
  programistycznych czyta automatycznie. Jeśli twój tego nie robi, każ mu przeczytać ten plik na początku (Claude Code
  czyta `CLAUDE.md`, więc wpisz do niego linię `@AGENTS.md`).
- Za to, co wysyłasz, odpowiadasz ty: uruchom testy i hook samodzielnie, przeczytaj diff i napisz w pull requeście, co
  sprawdzono, a czego nie.
- Nigdy nie pozwól asystentowi wysyłać czegokolwiek do AbuseIPDB ani wklejać prawdziwych kluczy, nazw hostów lub
  adresów.

## Kodeks postępowania

Projekt stosuje [Contributor Covenant](CODE_OF_CONDUCT.md). Biorąc udział w zgłoszeniach, dyskusjach i pull
requestach, akceptujesz go.

## Licencja

Wnosząc wkład, zgadzasz się, że jest on objęty [licencją MIT](../../LICENSE) tego projektu.
