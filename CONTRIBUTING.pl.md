[English](CONTRIBUTING.md) | **Polski**

# Współpraca

Dziękuję za pomoc. To narzędzie publikuje dane z kont AbuseIPDB swoich użytkowników, a fałszywe zgłoszenie może
skończyć się zawieszeniem konta. Każdą zmianę ocenia się najpierw jednym pytaniem: czy może sprawić, że narzędzie
zgłosi coś, co nie jest prawdziwym, lokalnie zaobserwowanym atakiem, albo ujawni coś o operatorze? Wygoda jest wtórna.

## Zgłaszanie błędu

Otwórz zgłoszenie (issue) z szablonu zgłoszenia błędu. Podaj wersję (`./abuseipdb_send.sh --version`,
`python3 abuseipdb_report.py --version`), dystrybucję, wersje CrowdSeca i Pythona oraz właściwe linie z
`abuseipdb_cron.log` albo z `--dry-run`.

Zanim cokolwiek wkleisz, usuń własne nazwy domen i hostów, ścieżkę katalogu domowego, temat ntfy i własne adresy IP.
Nigdy nie wklejaj klucza API ani pliku konfiguracji. Podatność zgłaszaj według [SECURITY.pl.md](SECURITY.pl.md), a nie
w publicznym zgłoszeniu.

## Proponowanie zmiany

Przy czymś większym niż literówka najpierw otwórz zgłoszenie i opisz problem. Zmiany bezpieczników wymienionych w
[docs/pl/COMPLIANCE.md](docs/pl/COMPLIANCE.md) są omawiane, zanim powstanie kod. Pull request, który osłabia któryś z
nich (filtr 60 dni, adresy nieglobalne, wykluczone lub słabe scenariusze, auto-zaufanie SSH, wykluczenia, własne
adresy, źródło danych tylko z lokalnych alertów, zasady komentarza, podwójna walidacja, znacznik, blokada 20 h,
obsługa klucza API), wymaga bardzo dobrego powodu i będzie z tym na uwadze przeglądany.

Nowy scenariusz CrowdSeca w `CATEGORY_MAP` wymaga najsłabszego zestawu kategorii, który log naprawdę uzasadnia, oraz
testu; patrz [docs/pl/DEVELOPMENT.md](docs/pl/DEVELOPMENT.md). Jeśli chcesz tylko przestać zgłaszać scenariusz na
własnym serwerze, użyj `EXTRA_EXCLUDE_SCENARIOS` w swoim configu.

## Jak wysłać zmianę

Nie potrzebujesz uprawnień zapisu ani zaproszenia: pracuj w forku.

1. Zrób fork repozytorium na GitHubie (przycisk "Fork"), potem sklonuj **swój fork**.
2. Utwórz gałąź na jeden temat: `git switch -c fix-krotki-opis`.
3. Wprowadź zmianę, uruchom testy, zrób commit z komunikatem po angielsku (patrz niżej).
4. Wypchnij gałąź do swojego forka: `git push -u origin fix-krotki-opis`.
5. Na GitHubie otwórz pull request z Twojej gałęzi do `main` tego repozytorium (GitHub pokaże przycisk po pushu).
6. Workflow `tests` uruchomi się na Twoim pull requeście; pierwszy przebieg nowego kontrybutora wymaga zatwierdzenia
   przez opiekuna. Poprawiaj to, co pada, dopychając kolejne commity do tej samej gałęzi.
7. Scala wyłącznie opiekun. Żeby utrzymać gałąź aktualną, dodaj raz to repozytorium jako drugi remote
   (`git remote add upstream https://github.com/arcymonek/reportabuseipdb.git`) i używaj `git pull --rebase upstream main`.

Opiekun stosuje zaakceptowane zmiany na swoim komputerze, dodaje polskie tłumaczenie i wersję, a GitHub oznacza potem
Twój pull request jako scalony lub zamknięty. Stałych kontrybutorów można później zaprosić do wypychania gałęzi
bezpośrednio do tego repozytorium; pull request i scalenie przez opiekuna pozostają bez zmian.

## Pull requesty

- Jeden temat na pull request. Kod ma być prosty i czytelny; komentarze wyjaśniają dlaczego, a nie tylko co.
- Kod, komentarze, komunikaty, testy i komunikaty commitów są wyłącznie po angielsku. Szablony zgłoszeń (`TPL_*`)
  muszą zostać po angielsku, bo są publikowane w AbuseIPDB.
- Dokumentacja istnieje po angielsku i po polsku (`README.md` i `README.pl.md`, `docs/X.md` i `docs/pl/X.md` itd.).
  Wystarczy, że napiszesz plik angielski; nie musisz znać polskiego. Polskie tłumaczenie dodaje opiekun projektu przed
  scaleniem, więc prosimy, żeby nie tłumaczyć maszynowo na własną rękę.
- Nie podnoś wersji. Opisz zmianę w sekcji "Unreleased" w `CHANGELOG.md`; opiekun podnosi wersję i uzupełnia
  `CHANGELOG.pl.md` przy scalaniu.
- Testy używają wyłącznie sztucznych danych: adresów zarezerwowanych (`203.0.113.0/24`, `198.51.100.0/24`,
  `2001:db8::/32`) albo znanych publicznych resolverów jako zastępczych atakujących, nazw `example.org` / `.example` /
  `.test`, sztucznych kluczy i tematów. Nigdy prawdziwego klucza API, nigdy prawdziwej wysyłki do AbuseIPDB, nigdy
  własnych nazw hostów ani adresów.
- Refaktoryzacja musi zachować wygenerowany CSV bajt w bajt dla tego samego `--input-json`. Po zmianie bezpiecznika
  zepsuj go celowo i sprawdź, że test pada (test mutacyjny, patrz [docs/pl/DEVELOPMENT.md](docs/pl/DEVELOPMENT.md)).

## Język

Zgłoszenia, pull requesty, komentarze w przeglądzie i komunikaty commitów są po angielsku, żeby każdy mógł je
śledzić. Opiekun jest Polakiem i może czytać Twój tekst w tłumaczeniu, a odpowiadać po angielsku; pisz prosto, a
wszystko będzie zrozumiałe.

## Praca z asystentem AI

Wkład tworzony z pomocą AI jest mile widziany; opiekun też tak pracuje. Wskaż swojemu asystentowi plik
[AGENTS.md](AGENTS.md): zawiera zasady (bezpieczniki, których nie wolno osłabiać, czego nigdy nie robić, konwencje i
kilka nieoczywistych faktów o danych) w formacie, który wielu agentów programistycznych czyta automatycznie. Jeśli
Twój tego nie robi, każ mu przeczytać ten plik na początku (Claude Code czyta `CLAUDE.md`, więc wpisz do niego linię
`@AGENTS.md`). Za to, co
wysyłasz, odpowiadasz Ty: uruchom testy i hook pre-commit samodzielnie, przeczytaj diff i napisz w pull requeście, co
sprawdzono, a czego nie. Nigdy nie pozwól asystentowi wysyłać czegokolwiek do AbuseIPDB ani wklejać prawdziwych
kluczy, nazw hostów lub adresów. Plik `AGENTS.md` jest tylko po angielsku i nie ma polskiego odpowiednika.

## Uruchamianie testów

```bash
python3 -m unittest discover -v tests     # testy generatora działają wszędzie; testy wrappera wymagają Linuksa
git config core.hooksPath tools           # opcjonalnie: hook pre-commit (składnia, pary EN/PL, wersje, skan prywatności)
```

Hook odmawia commita, który zmienia tylko angielską stronę pary dokumentów. Skoro piszesz tylko po angielsku,
commituj przez `EN_ONLY=1 git commit ...`: pomija to jedną regułę i zostawia wszystkie pozostałe kontrole (w tym skan
prywatności). Nie używaj `--no-verify`, który wyłącza wszystkie kontrole.

Workflow GitHub Actions uruchamia cały zestaw na Ubuntu dla każdego pull requesta; musi przejść przed scaleniem.

## Kodeks postępowania

Projekt stosuje [Contributor Covenant](CODE_OF_CONDUCT.pl.md). Biorąc udział w zgłoszeniach, dyskusjach i pull
requestach, akceptujesz go.

## Licencja

Wnosząc wkład, zgadzasz się, że jest on objęty [licencją MIT](LICENSE) tego projektu.
