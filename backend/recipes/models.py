from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


class Ingredient(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название ингредиента")
    measurement_unit = models.CharField(max_length=50, verbose_name="Единица измерения")

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"

    def __str__(self):
        return self.name


class Recipe(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipes",
        verbose_name="Автор рецепта",
    )
    title = models.CharField(max_length=256, verbose_name="Название рецепта")
    image = models.ImageField(
        upload_to="recipes/images/", verbose_name="Изображение рецепта"
    )
    description = models.TextField(verbose_name="Описание рецепта")
    ingredients = models.ManyToManyField(
        Ingredient,
        through="RecipeIngredient",
        related_name="recipes",
        verbose_name="Ингредиенты",
    )
    preparation_time = models.PositiveSmallIntegerField(
        verbose_name="Время приготовления (минуты)", validators=[MinValueValidator(1)]
    )
    date_created = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"

    def __str__(self):
        return self.title


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, verbose_name="Рецепт")
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент"
    )
    amount = models.PositiveIntegerField(verbose_name="Количество ингредиента")
    measurement_unit = models.CharField(max_length=50, default="г")

    class Meta:
        unique_together = ("recipe", "ingredient")
        verbose_name = "Ингредиент в рецепте"
        verbose_name_plural = "Ингредиенты в рецепте"

    def __str__(self):
        return f"{self.recipe}"


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="favorites",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name="Рецепт",
        related_name="in_favorites",
    )


class ShoppingCart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="shopping_carts",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name="Рецепт",
        related_name="in_shopping_carts",
    )
    ingredients_snapshot = models.JSONField(
        verbose_name="Снимок ингредиентов", null=True, blank=True
    )
    date_added = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")

    class Meta:
        unique_together = ("user", "recipe")
        verbose_name = "Список покупок"
        verbose_name_plural = "Списки покупок"

    def __str__(self):
        return f"{self.user} added {self.recipe.title} to shopping cart"

    def save(self, *args, **kwargs):
        """Сохраняем снимок ингредиентов при создании"""
        if not self.pk:
            self.ingredients_snapshot = [
                {
                    "name": ri.ingredient.name,
                    "unit": ri.ingredient.measurement_unit,
                    "amount": ri.amount,
                }
                for ri in self.recipe.recipeingredient_set.all()
            ]
        super().save(*args, **kwargs)
