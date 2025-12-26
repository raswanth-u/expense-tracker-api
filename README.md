# Expense Tracker API

[![CI Pipeline](https://github.com/raswanth-u/expense-tracker-api/actions/workflows/ci.yml/badge.svg)](https://github.com/raswanth-u/expense-tracker-api/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/raswanth-u/expense-tracker-api/branch/main/graph/badge.svg)](https://codecov.io/gh/raswanth-u/expense-tracker-api)

FastAPI-based expense tracking API with PostgreSQL backend.

## Features

- ✅ CRUD operations for expenses
- ✅ Category-based summaries
- ✅ Payment method tracking
- ✅ Date range filtering
- ✅ API key authentication
- ✅ 96% test coverage
- ✅ CI/CD with GitHub Actions

## Quick Start

```bash
# Clone repository
git clone https://github.com/raswanth-u/expense-tracker-api.git
cd expense-tracker-api

# Copy environment file
cp .env.example .env

# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"

# Start services
docker compose up -d
