[English](SECURITY.md) | **Polski**

# Polityka bezpieczeństwa

## Co jest tu podatnością

Wszystko, co mogłoby sprawić, że narzędzie:

- zgłosi adres, który nie atakował serwera (np. własny adres operatora, CDN albo adres wzięty z innego źródła niż
  lokalne alerty CrowdSeca);
- opublikuje w komentarzu zgłoszenia coś o operatorze (nazwę domeny lub hosta, własny adres, poświadczenie albo dane
  osobowe z żądania);
- ujawni klucz API albo temat ntfy (logi, lista procesów, repozytorium, alerty);
- wykona kod lub polecenia z pliku konfiguracji, z alertów CrowdSeca albo z odpowiedzi API.

## Jak zgłosić

Nie otwieraj publicznego zgłoszenia. Użyj prywatnego zgłaszania podatności na GitHubie (zakładka "Security", "Report a
vulnerability") albo napisz na <github@arkadiuszpolak.pl>. Opisz problem, wersję, której dotyczy, i jeśli możesz, jak
go odtworzyć na sztucznych danych. Nie dołączaj prawdziwych kluczy API, tematów ani danych innych osób.

To hobbystyczny projekt prowadzony przez jedną osobę: odpowiedź w ciągu mniej więcej tygodnia. Potwierdzony problem
zostaje naprawiony w nowej wersji i odnotowany w changelogu z podziękowaniem, chyba że wolisz zachować anonimowość.

## Wspierane wersje

Poprawki dostaje tylko najnowsza wersja na gałęzi `main`.
