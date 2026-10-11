[English](../../SECURITY.md) | **Polski**

# Polityka bezpieczeństwa

## Jak zgłosić podatność

Nie otwieraj publicznego issue ani dyskusji. Użyj jednej z dwóch dróg:

- **GitHub (zalecane):** zakładka "Security", przycisk "Report a vulnerability". Takie zgłoszenie jest prywatne.
- **E-mail:** <github@arkadiuszpolak.pl>. Poczta nie jest szyfrowana, więc nie wysyłaj nią niczego tajnego.

Możesz pisać po polsku lub po angielsku. Podaj:

- co się dzieje i jakie może mieć skutki;
- wersję, której dotyczy problem (`./abuseipdb_send.sh --version`);
- jeśli możesz, jak to odtworzyć na sztucznych danych (`python3 abuseipdb_report.py --input-json plik.json --dry-run`,
  gdzie `plik.json` ma kształt wyniku `cscli alerts list -o json`).

Nie dołączaj prawdziwych kluczy API, tematów ntfy, własnych nazw domen i hostów, własnych adresów IP ani danych innych
osób. Nie sprawdzaj problemu na żywej wysyłce do AbuseIPDB: każda próba publikuje zgłoszenia pod czyimś kontem.

## Czego się spodziewać

To hobbystyczny projekt prowadzony przez jedną osobę: odpowiedzi spodziewaj się w ciągu około tygodnia. Potwierdzony
problem zostaje naprawiony w nowej wersji i odnotowany w changelogu z podziękowaniem, chyba że wolisz zachować
anonimowość. Proszę, nie publikuj szczegółów, zanim poprawka się ukaże.

## Co jest podatnością

Wszystko, co mogłoby sprawić, że narzędzie:

- zgłosi adres, który nie atakował serwera: własny adres operatora lub serwera, adres podsunięty z zewnątrz (na
  przykład treścią żądania, która psuje strukturę pliku CSV) albo adres wzięty z innego źródła niż lokalne alerty
  CrowdSeca;
- ujawni coś o operatorze w komentarzu zgłoszenia lub w alercie ntfy: nazwę domeny lub hosta, własny adres IP,
  ścieżkę instalacji, nazwę użytkownika;
- opublikuje w komentarzu dane uwierzytelniające lub dane osobowe z cudzego żądania w przypadku, który opisana ochrona
  powinna wychwycić (sekcja "Poprawność danych w zgłoszeniu" w [COMPLIANCE.md](COMPLIANCE.md));
- ujawni klucz API albo temat ntfy (logi, lista procesów, repozytorium, alerty);
- wykona kod lub polecenia z pliku konfiguracji, z alertów CrowdSeca albo z odpowiedzi API.

## Co nie jest podatnością

- Działania kogoś, kto już ma dostęp do konta użytkownika usługi albo do roota na serwerze: taka osoba i tak czyta
  klucz API.
- Znane ograniczenia ochrony danych w komentarzu, opisane w tej samej sekcji [COMPLIANCE.md](COMPLIANCE.md) (na
  przykład token w samej ścieżce żądania nie jest maskowany).
- Skutki konfiguracji niezgodnej z listą "Zanim uruchomisz na żywo" w [README.pl.md](../../README.pl.md) (na
  przykład CrowdSec za CDN widzi adresy CDN, więc je zgłosi).
- Fałszywy alarm scenariusza CrowdSeca, czyli zwykły ruch uznany za atak: to zwykły błąd, zgłoś go jako issue
  (formularz błędu).
- Błędy w CrowdSecu, AbuseIPDB, ntfy lub curl: zgłoś je ich autorom.

## Wspierane wersje

Poprawki trafiają na gałąź `main` i dostaje je tylko jej najnowsza wersja. Oznaczone wydanie (Release) może być starsze
niż `main`, bo wydania powstają rzadko. Aktualizacja: `git pull --ff-only`, patrz sekcja "Aktualizacja i wycofanie
zmian" w [OPERATIONS.md](OPERATIONS.md).
