FROM python:3.11-slim
WORKDIR /code

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project (excludes files listed in .dockerignore)
COPY . .

# Run migrations before starting the app
ENTRYPOINT ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
