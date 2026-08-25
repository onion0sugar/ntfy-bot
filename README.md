# MSSQL → ntfy

Bot sprawdza bazę MSSQL i wysyła powiadomienia do aplikacji ntfy.

## Uruchomienie

### 1. Zainstaluj wymagania

Potrzebujesz:

- Python 3.12 lub nowszy,
- Microsoft ODBC Driver 18 for SQL Server,
- dostępu do bazy MSSQL,
- aplikacji ntfy na telefonie.

### 2. Przygotuj środowisko

W katalogu projektu wykonaj:

```bash
python -m venv .venv
```

Aktywuj środowisko:

```bash
# Linux / macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Zainstaluj biblioteki:

```bash
pip install -r requirements.txt
```

### 3. Uzupełnij konfigurację

Skopiuj plik konfiguracyjny:

```bash
# Linux / macOS
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Otwórz `.env` i wpisz prawidłowe dane:

```env
MSSQL_SERVER=adres-serwera
MSSQL_PORT=1433
MSSQL_DATABASE=nazwa-bazy
MSSQL_USERNAME=login
MSSQL_PASSWORD=haslo

NTFY_SERVER=https://ntfy.sh
NTFY_TOPIC=moja-nazwa-topic
```

W aplikacji ntfy zasubskrybuj dokładnie ten sam topic, który wpisano w `NTFY_TOPIC`.

### 4. Przygotuj pliki projektu

Skopiuj przykładowe mapowanie użytkowników:

```bash
# Linux / macOS
cp user_mapping.example.json user_mapping.json

# Windows PowerShell
Copy-Item user_mapping.example.json user_mapping.json
```

W `user_mapping.json` wpisz loginy z MSSQL oraz topiki ntfy dla każdego użytkownika.

Dostosuj zapytania do swojej bazy:

- `query.sql` – nowe zamówienia,
- `query_busy.sql` – zajęci użytkownicy,
- `query22.sql` – zamówienia gotowe do wydania.

### 5. Sprawdź konfigurację

```bash
python main.py --test-db
python main.py --test-ntfy
```

Jeśli oba testy zakończą się poprawnie, uruchom bota:

```bash
python main.py
```

Zatrzymanie programu: `Ctrl+C`.

Po każdej zmianie w `.env`, `user_mapping.json` lub plikach `.sql` uruchom program ponownie.
