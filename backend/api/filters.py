from django_filters.rest_framework import FilterSet, BooleanFilter, CharFilter
from recipes.models import Recipe, Ingredient
from django_filters import rest_framework as filters


class RecipeFilter(FilterSet):
    is_favorited = BooleanFilter(method="filter_is_favorited")
    is_in_shopping_cart = BooleanFilter(method="filter_is_in_shopping_cart")
    author = filters.NumberFilter(field_name="author__id")

    class Meta:
        model = Recipe
        fields = ["is_favorited", "is_in_shopping_cart", "author"]

    def filter_is_favorited(self, queryset, name, value):
        if value and self.request.user.is_authenticated:
            return queryset.filter(in_favorites__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Фильтрация рецептов в корзине покупок"""
        if value and self.request.user.is_authenticated:
            return queryset.filter(in_shopping_carts__user=self.request.user)

        return queryset


class IngredientFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = Ingredient
        fields = ["name"]
