# Dokumentacja odtworzenia MSSQL → ntfy

## Cel

Program cyklicznie wykonuje skonfigurowane zapytanie `SELECT` w Microsoft SQL
Server. Gdy zapytanie zwróci wiersz, wysyła tekstowe powiadomienie do ntfy.
Serwer Linux publikuje przez HTTPS, a urządzenia Android odbierają wiadomości
w aplikacji ntfy po zasubskrybowaniu tego samego topicu.

Przepływ:

```text
MSSQL (read-only) → query.sql → wiersz? → POST do ntfy → Android
```

## Założenia

- Program korzysta z `state.db` wyłącznie do zapamiętania zmian dokumentów typu 22; nie zapisuje historii nowych zamówień.
- `query.sql` ma zwracać maksymalnie jeden wiersz, najlepiej przez `TOP 1`.
- Jedna kolumna oznacza numer zamówienia; przy dwóch kolumnach pierwsza jest opcjonalnym numerycznym ID do logów, druga numerem.
- Brak wiersza resetuje bieżący cykl. Kolejny wiersz jest anonsowany od razu.
- Baza jest tylko do odczytu: ODBC Driver 18, `autocommit`, `ApplicationIntent=ReadOnly`.
- `.env` i `query.sql` są ładowane przy starcie; zmiana wymaga restartu.
- Powiadomienie ntfy jest tekstowe. Poprzedni strumień audio Opus/Zello nie jest już używany.
- Każdy login ma dwa topiki: `new_order_topic` i `ready_order_topic`.
- Typ 7 `in_progress` oraz typ 22 `CourierId=13` `in_progress` oznaczają zajętego użytkownika.
- Typ 22 `CourierId=13` `in_progress` nie generuje żadnego powiadomienia.
- Typ 22 `CourierId=13` `new` oznacza gotowe do wydania i trafia wyłącznie na topik przypisanego użytkownika.
- Użytkownik z gotowym zamówieniem nie dostaje nowych zamówień.

## Konfiguracja

Wymagane:

- `MSSQL_SERVER`, `MSSQL_DATABASE`, `MSSQL_USERNAME`, `MSSQL_PASSWORD`;
- `user_mapping.json` – mapowanie każdego loginu MSSQL na dwa topiki ntfy.
- `USER_MAPPING_FILE` – domyślnie `user_mapping.json`, mapowanie loginów na dwa topiki;

Opcjonalne:

- `MSSQL_PORT` – domyślnie `1433`; dla `host\\instancja` portu nie dopisuje się;
- `MSSQL_ENCRYPT` i `MSSQL_TRUST_SERVER_CERTIFICATE` – domyślnie `yes`;
- `NTFY_SERVER` – domyślnie `https://ntfy.sh`, może wskazywać własny serwer;
- `NTFY_TOKEN` – token Bearer dla prywatnego topicu lub ACL;
- `NTFY_TITLE`, `NTFY_PRIORITY`, `NTFY_TAGS` – nagłówki wiadomości;
- `POLL_INTERVAL` – polling bazy, minimum 1 s, domyślnie 10 s;
- `COURIER_ID` – identyfikator kuriera, domyślnie `13`;
- `MAX_NOTIFICATIONS_PER_BATCH` – równoległa partia wysyłek, domyślnie 3;
- `ANNOUNCE_INTERVAL` – powtórzenie aktywnego anonsu, domyślnie 30 s; `0` oznacza jeden anons przy każdym pollingu;
- `SEND_TEXT` – domyślnie `true`.

Do Androida trzeba przekazać adres serwera (jeśli self-hosted) i dokładnie tę
samą nazwę topicu. Dla własnego serwera należy zapewnić dostęp HTTPS z telefonu
oraz skonfigurować uprawnienia subskrypcji i publikacji.

## Logika pętli

1. Zweryfikuj, że `query.sql` istnieje, nie jest pusty i po komentarzach zaczyna się od `SELECT`.
2. Utwórz klienta ntfy.
3. Utrzymuj połączenie MSSQL; po awarii zamknij je i ponów po 5 s.
4. Co `POLL_INTERVAL` wykonaj zapytanie i pobierz jeden wiersz.
5. Jeśli `ANNOUNCE_INTERVAL=0`, opublikuj wiadomość przy każdym pollingu z wierszem.
6. Jeśli interwał jest większy od zera, pierwszy anons wyślij natychmiast, a następne co `ANNOUNCE_INTERVAL`, niezależnie od pollingu.
7. Polling bez wiersza zatrzymuje powtórzenia.
8. Po `SIGTERM`/`SIGINT` zamknij bazę i zakończ proces.

Treść wiadomości ma postać `🔔 Nowe zamówienie: {numer}`. Publikacja do ntfy
jest uznana za udaną dopiero po odpowiedzi HTTP 2xx. Timeout HTTP wynosi 15 s.
Błąd publikacji trafia do głównej obsługi błędów i powoduje ponowną próbę po 5 s.

## ntfy

Publikacja wykonuje `POST` na:

```text
{NTFY_SERVER}/{NTFY_TOPIC}
```

Body to UTF-8 `text/plain`. Nagłówki to `Title`, `Priority`, opcjonalnie `Tags`
i `Authorization: Bearer {NTFY_TOKEN}`. Adapter używa standardowej biblioteki
HTTP i wykonuje blokujące żądanie w wątku, aby nie blokować asynchronicznej pętli.

## Uruchomienie i testy

- `python main.py` – serwis;
- `python main.py --test-db` – `SELECT 1` i walidacja `query.sql`;
- `python main.py --test-ntfy` – publikacja testowej wiadomości (`--test-text` jest aliasem).

Testy powinny mockować HTTP ntfy i MSSQL. Najważniejsze testowane zachowania to
reset po braku wiersza, niezależny zegar anonsów, tryb interwału zero oraz retry
po chwilowej niedostępności bazy.

## Bezpieczeństwo i self-hosting

Topic powinien być trudny do odgadnięcia, a dla prywatnych danych należy używać
autoryzacji ntfy i HTTPS. Token trzymać wyłącznie w `.env` z prawami `600`.
Nie umieszczać sekretów w repozytorium. Historyczny `REASONIX.md` zawiera stare
dane dostępowe – należy je traktować jako ujawnione i zmienić.
