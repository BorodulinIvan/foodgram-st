import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from recipes.models import Ingredient


class Command(BaseCommand):
    help = "Загрузка ингредиентов в базу данных"

    def handle(self, *args, **options):
        file_path = Path(settings.BASE_DIR) / "data" / "ingredients.json"
        with open(file_path, "r", encoding="utf-8") as file:
            ingredients_list = json.load(file)
            count = Ingredient.objects.count()
            ingredients = [Ingredient(**item) for item in ingredients_list]

            Ingredient.objects.bulk_create(ingredients, ignore_conflicts=True)
            created_count = Ingredient.objects.count() - count

            self.stdout.write(
                self.style.SUCCESS(
                    f"Загружено {created_count} ингредиентов в базу данных"
                )
            )
