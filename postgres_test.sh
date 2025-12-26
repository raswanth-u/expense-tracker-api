# Start PostgreSQL in Docker
docker run -d \
  --name test-postgres \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_pass \
  -e POSTGRES_DB=test_db \
  -p 5432:5432 \
  postgres:16-alpine

# Wait for PostgreSQL to be ready
sleep 5

# Run tests against PostgreSQL
DATABASE_URL=postgresql://test_user:test_pass@localhost:5432/test_db \
API_KEY=test_api_key \
pytest tests/ -v --cov=. --cov-report=xml --cov-report=term

# Cleanup
docker stop test-postgres
docker rm test-postgres