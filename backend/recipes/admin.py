from django.contrib import admin
from django import forms
from .models import Recipe, Ingredient, RecipeIngredient, Favorite, ShoppingCart


class RecipeForm(forms.ModelForm):
    class Meta:
        model = Recipe
        fields = "__all__"

    def clean_preparation_time(self):
        preparation_time = self.cleaned_data["preparation_time"]
        if preparation_time < 1:
            raise forms.ValidationError(
                f"Время приготовления должно быть не менее {1} минуты."
            )
        if preparation_time > 16000:
            raise forms.ValidationError(
                f"Время приготовления не должно превышать {16000} минут."
            )
        return preparation_time


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    fields = ("ingredient", "amount", "measurement_unit")
    readonly_fields = ("measurement_unit",)

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "get_favorite_count")
    search_fields = ("title", "author__username", "author__email")
    list_filter = ("author",)
    fields = (
        "title",
        "author",
        "image",
        "description",
        "preparation_time",
        "date_created",
    )
    readonly_fields = ("date_created",)
    inlines = [RecipeIngredientInline]

    def get_favorite_count(self, obj):
        return obj.favorites.count()


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("name", "measurement_unit")
    search_fields = ("name",)


@admin.register(RecipeIngredient)
class RecipeIngredientAdmin(admin.ModelAdmin):
    list_display = ("recipe", "ingredient", "amount", "measurement_unit")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe")
    search_fields = ("user__username", "recipe__title")


@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    list_display = ("user", "recipe")
    search_fields = ("user__username", "recipe__title")
