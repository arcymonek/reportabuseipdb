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

## Pull requesty

- Jeden temat na pull request. Kod ma być prosty i czytelny; komentarze wyjaśniają dlaczego, a nie tylko co.
- Kod, komentarze, komunikaty, testy i komunikaty commitów są wyłącznie po angielsku. Szablony zgłoszeń (`TPL_*`)
  muszą zostać po angielsku, bo są publikowane w AbuseIPDB.
- Dokumentacja istnieje po angielsku i po polsku (`README.md` i `README.pl.md`, `docs/X.md` i `docs/pl/X.md` itd.).
  Aktualizuj obie wersje. Jeśli nie piszesz po polsku, zaktualizuj plik angielski i napisz to w pull requeście;
  tłumaczenie doda opiekun projektu.
- Nie podnoś wersji. Opisz zmianę w sekcji "Unreleased" w `CHANGELOG.md` (i "Niewydane" w `CHANGELOG.pl.md`, jeśli
  możesz); opiekun podnosi wersję przy scalaniu.
- Testy używają wyłącznie sztucznych danych: adresów zarezerwowanych (`203.0.113.0/24`, `198.51.100.0/24`,
  `2001:db8::/32`) albo znanych publicznych resolverów jako zastępczych atakujących, nazw `example.org` / `.example` /
  `.test`, sztucznych kluczy i tematów. Nigdy prawdziwego klucza API, nigdy prawdziwej wysyłki do AbuseIPDB, nigdy
  własnych nazw hostów ani adresów.
- Refaktoryzacja musi zachować wygenerowany CSV bajt w bajt dla tego samego `--input-json`. Po zmianie bezpiecznika
  zepsuj go celowo i sprawdź, że test pada (test mutacyjny, patrz [docs/pl/DEVELOPMENT.md](docs/pl/DEVELOPMENT.md)).

## Uruchamianie testów

```bash
python3 -m unittest discover -v tests     # testy generatora działają wszędzie; testy wrappera wymagają Linuksa
git config core.hooksPath tools           # opcjonalnie: hook pre-commit (składnia, pary EN/PL, wersje, skan prywatności)
```

Workflow GitHub Actions uruchamia cały zestaw na Ubuntu dla każdego pull requesta; musi przejść przed scaleniem.

## Licencja

Wnosząc wkład, zgadzasz się, że jest on objęty [licencją MIT](LICENSE) tego projektu.
