# Family Expense Tracker API

A comprehensive FastAPI-based expense tracking system for families with budget management, credit card tracking, and advanced analytics.

## Features

- 👥 **Multi-User Support** - Track expenses for all family members
- 💰 **Budget Management** - Set monthly budgets with alerts
- 💳 **Credit Card Tracking** - Monitor billing cycles and utilization
- 📊 **Advanced Reports** - Trends, analytics, and exports
- 🔒 **Secure** - API key authentication
- 🚀 **CI/CD** - Automated testing and deployment

## Quick Start

```bash
# Clone repository
git clone https://github.com/raswanth-u/expense-tracker-api.git
cd expense-tracker-api

# Copy environment file
cp .env.example .env
# Edit .env with your secure passwords

# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Org/CN=localhost"
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

# Start services
docker compose up -d
```

## API Documentation

Once running, visit:
- **Swagger UI:** `https://localhost/api/docs`
- **ReDoc:** `https://localhost/api/redoc`

## Testing

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Architecture

- **API:** FastAPI with SQLModel ORM
- **Database:** PostgreSQL 15
- **Reverse Proxy:** Nginx with SSL
- **Testing:** Pytest (75 tests, 94% coverage)
- **CI/CD:** GitHub Actions

## Endpoints

### Users
- `POST /users/` - Create user
- `GET /users/` - List users
- `GET /users/{id}` - Get user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Deactivate user
- `GET /users/{id}/stats` - User statistics

### Budgets
- `POST /budgets/` - Create budget
- `GET /budgets/` - List budgets
- `GET /budgets/status/summary` - Budget tracking
- `GET /budgets/status/alerts` - Budget alerts
- And more...

### Expenses
- `POST /expenses/` - Create expense
- `GET /expenses/` - List expenses (with filters)
- `GET /expenses/summary` - Category summary
- `GET /expenses/payment_summary` - Payment method summary
- And more...

### Credit Cards
- `POST /credit-cards/` - Register card
- `GET /credit-cards/{id}/statement` - Billing statement
- `GET /credit-cards/{id}/utilization` - Utilization trend
- `GET /credit-cards/summary` - All cards summary
- And more...

### Reports
- `GET /reports/monthly` - Comprehensive monthly report
- `GET /reports/family-summary` - Family spending summary
- `GET /reports/category-analysis` - Category deep dive
- `GET /reports/spending-trends` - Multi-month trends
- `GET /reports/export` - Export data (JSON/CSV)

## Development

```bash
# Run locally
uvicorn main:app --reload --port 8001

# Run linting
ruff check .

# Run type checking
mypy main.py models.py --ignore-missing-imports
```

## Deployment

Automated via GitHub Actions:
- Push to `main` → Tests run → Deploy to production
- Deploys to private Tailscale network via SSH

## License

MIT

## Author

Built in 5 hours as a comprehensive family expense tracking solution.
```

---