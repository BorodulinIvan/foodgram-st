#!/bin/bash
# Ожидание доступности базы данных
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h db -U ${POSTGRES_USER} -d ${POSTGRES_DB}; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is ready - executing migrations"

# Выполнение миграций
python manage.py makemigrations
python manage.py migrate --noinput

# Запуск gunicorn (передается через CMD)
exec "$@"