#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Checking environment...${NC}"

# Check if migrations should run
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo -e "${YELLOW}🔄 Running database migrations...${NC}"
    
    # Run migrations
    if alembic upgrade head; then
        echo -e "${GREEN}✅ Migrations completed successfully${NC}"
    else
        echo -e "${RED}❌ Migration failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⏭️  Skipping migrations (RUN_MIGRATIONS=false)${NC}"
    echo -e "${YELLOW}💡 Tip: Run manually with 'alembic upgrade head'${NC}"
fi

echo -e "${YELLOW}🚀 Starting FastAPI application...${NC}"
echo -e "${YELLOW}📍 Listening on http://0.0.0.0:8000${NC}"

# Start the API with coverage if RUN_COVERAGE is set
if [ "$RUN_COVERAGE" = "true" ]; then
    echo -e "${YELLOW}📊 Running with coverage enabled...${NC}"
    exec coverage run --source=main,models,services,utils -m uvicorn main:app --host 0.0.0.0 --port 8000
else
    exec uvicorn main:app --host 0.0.0.0 --port 8000
fi
