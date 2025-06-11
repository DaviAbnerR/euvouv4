# EuVou

This project is a simple Flask web application for creating and selling event tickets and raffle numbers. Users can register, log in, organize raffles and parties, and purchase entries online.

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate
```

### 2. Install requirements

Install the dependencies listed in `requirements.txt` (Flask, Flask-SQLAlchemy,
python-dotenv and Werkzeug):

```bash
pip install -r requirements.txt
```

### 3. Initialize the database

The database is created automatically on the first run. If you need to initialize it manually, run:

```bash
python - <<'PY'
from app import app, db
with app.app_context():
    db.create_all()
PY
```

### 4. Run the application

Start the Flask app using:

```bash
python app.py
```

Navigate to `http://localhost:5000` in your browser.

## Environment variables

Copy `.env.example` to `.env` and fill in the required values.
- `SECRET_KEY` – secret string used by Flask for sessions. The application reads this variable and falls back to `change-me` if it is not set.
- `MP_ACCESS_TOKEN` – access token for Mercado Pago API used to process payments.
- `GA_MEASUREMENT_ID` – optional Google Analytics ID. When set, pages will load the GA tracking script.
- `MP_CURRENCY_ID` – currency code used for Mercado Pago items (default `BRL`).
- `PUBLIC_URL` – base URL used to generate callback links for Mercado Pago. Example: `http://200.138.43.32:5000`.


## Running tests

After installing the requirements, execute the test suite with:

```bash
pytest
```

The tests use an in-memory SQLite database and do not affect your local data.

## Sorting a raffle

You can perform the raffle draw manually by sending a POST request to
`/api/rifa/<id>/sortear`. The same action is available through the
**Sortear** button shown on the organizer panel and inserted by
`static/main.js`.

The button only appears when the following conditions are met:

- the raffle status is `em_andamento`;
- the draw date has been reached; and
- there are sold tickets.

When invoked, either method finalizes the raffle and returns the winning
entry.

### Automated checking

The command `flask verificar_rifas` checks for raffles whose `data_fim` has
passed and status is `em_andamento`. It uses the same logic as the API to pick
a winning ticket and finalizes the raffle. You can run this command manually or
schedule it with cron.

## Analytics

The application collects basic web analytics. A small script runs on every page,
recording pageviews, referrers and ad clicks. Events are stored in the
`AnalyticsEvent` table and can be queried for visits and time on page metrics.
If `GA_MEASUREMENT_ID` is configured, a Google Analytics tag is also inserted on
each page.

3. **Consentimento de Cookies (LGPD/GDPR)** – o visitante é informado sobre a
coleta de dados e precisa aceitar o banner de consentimento antes que cookies de
analytics sejam gravados. Esse aviso atende às exigências legais no Brasil,
Europa e EUA.
4. **Bloqueio de Bots/Fraude** – o sistema detecta e bloqueia acessos automatizados (bots), evitando a inflação de métricas e prejuízo para anunciantes.
