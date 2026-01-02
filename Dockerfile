FROM python:3.11-slim
WORKDIR /code

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project (excludes files listed in .dockerignore)
COPY . .

# Copy entrypoint script and make it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Use entrypoint script
# Script checks RUN_MIGRATIONS env var to decide if migrations should run
# Dev: RUN_MIGRATIONS=true (auto-run migrations)
# Prod: RUN_MIGRATIONS=false (manual migrations only)
ENTRYPOINT ["/entrypoint.sh"]
