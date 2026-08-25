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

Dostosuj zapytania do swojej bazy:

- `query.sql` – nowe zamówienia,
- `query_busy.sql` – zajęci użytkownicy,
- `query22.sql` – zamówienia gotowe do wydania.

Skopiuj plik użytkowników i wpisz jeden login w każdej linii:

```bash
cp users.txt.example users.txt
```

Topiki są tworzone automatycznie: `login-new` dla nowego zamówienia oraz `login-rdy`
dla zamówienia gotowego do wydania. Lista z `users.txt` jest wczytywana tylko przy starcie.

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

Po każdej zmianie w `.env`, `users.txt` lub plikach `.sql` uruchom program ponownie.
