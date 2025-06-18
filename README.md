# Foodgram

Foodgram - это веб-приложение для создания и управления рецептами. Пользователи могут добавлять рецепты, сохранять их в избранное, добавлять в корзину ингредиенты и делиться рецептами с другими пользователями. Приложение поддерживает авторизацию, фильтрацию и пагинацию для удобного поиска и сортировки рецептов.

## Запуск проекта
Клонируйте репозиторий себе на компьютер
```bash
git clone https://github.com/BorodulinIvan/foodgram-st.git
cd foodgram-st
```
Запускаем докер, для этого перейдите в директорию `infra`
```bash
cd infra
```
Далее создайте файл `.env`
```
SECRET_KEY=
DEBUG=1
POSTGRES_DB=foodgram_db
POSTGRES_USER=foodgram_user
POSTGRES_PASSWORD=
POSTGRES_HOST=db
POSTGRES_PORT=5432
```
Запускаем непосредственно докер
```bash
docker compose up --build
```
Далее открываем еще один терминал и в нем выполняем команды
```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py collectstatic
docker compose exec backend python manage.py load_ingredients
```

### Доступ к страницам по ссылкам:
`Главная страница` – `http://localhost:8000/`

`Админка` – `http://localhost:8000/admin/`

`Документация` – `http://localhost:8000//api/docs/`

# Бородулин Иван
