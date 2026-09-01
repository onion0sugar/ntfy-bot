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
SUPERVISOR_TOPIC=supervisor
```

W aplikacji ntfy zasubskrybuj dokładnie ten sam topic, który wpisano w `NTFY_TOPIC`.
Supervisor powinien zasubskrybować topic wpisany w `SUPERVISOR_TOPIC`.

### 4. Przygotuj pliki projektu

Dostosuj zapytania `query22.sql` i `query22_users.sql` do swojej bazy. Pierwsze
jest głównym źródłem dokumentów typu 7 i 22, a drugie wskazuje użytkownika
odpowiedzialnego za spakowane pozycje.

Skopiuj plik użytkowników i wpisz jeden login w każdej linii:

```bash
cp users.txt.example users.txt
```

Każdy użytkownik ma jeden topic równy jego loginowi MSSQL. Nowe zamówienie jest
wysyłane z priorytetem `default`, a gotowe zamówienie z priorytetem `max`.
Nowe zamówienia są wysyłane tylko do użytkowników z `users.txt`, którzy
zmodyfikowali dziś co najmniej jeden dokument (`work_today_users.sql`); supervisor
otrzymuje powiadomienie niezależnie od tego.
Wyjątkiem są powiadomienia „Gotowe do wydania”: użytkownik z `users.txt`, który
ma takie zamówienie, otrzyma je również bez wpisu w `work_today_users.sql`.
Jeśli w tym samym pollingu wykryto gotowe zamówienie, powiadomienie o nowym
zamówieniu nie jest wysyłane. Lista z `users.txt` jest wczytywana tylko przy starcie.

### 5. Sprawdź konfigurację

```bash
python main.py --test-db
python main.py --test-ntfy
python main.py --test-new
python main.py --test-ready
```

Jeśli testy zakończą się poprawnie, uruchom bota:

```bash
python main.py
```

Zatrzymanie programu: `Ctrl+C`.

Po każdej zmianie w `.env`, `users.txt` lub plikach `.sql` uruchom program ponownie.

## Uruchomienie serwera ntfy w Dockerze

Na serwerze uruchom serwer ntfy:

```bash
docker compose up -d
```

Sprawdzenie działania:

```bash
docker compose ps
docker compose logs -f ntfy
```

Telefon korzysta z adresu ustawionego w `NTFY_BASE_URL` w `docker-compose.yml`.
Dane serwera ntfy są przechowywane w katalogu `ntfy-data`.

Bot działa poza Dockerem jako usługa systemd z pliku `ntfy-bot.service`.
