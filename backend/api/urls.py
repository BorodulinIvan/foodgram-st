from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views import UserViewSet
from api.views import (
    SignUpView,
    LoginView,
    RecipeViewSet,
    IngredientViewSet,
    LogoutView,
    UserProfileView,
    RecipeDetailView,
    SubscriptionsView,
    FavoritesView,
    ShoppingCartView,
    CreateRecipeView,
    EditRecipeView,
    PasswordChangeView,
)


router = DefaultRouter()
router.register(r"users", UserViewSet, basename="users")
router.register(r"ingredients", IngredientViewSet, basename="ingredients")
router.register(r"recipes", RecipeViewSet, basename="recipes")

urlpatterns = [
    path("auth/", include("djoser.urls")),
    path("auth/", include("djoser.urls.authtoken")),
    path("", include(router.urls)),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("user/<int:user_id>/", UserProfileView.as_view(), name="profile"),
    path("recipe/<int:id>/", RecipeDetailView.as_view(), name="recipe_detail"),
    path("subscriptions/", SubscriptionsView.as_view(), name="subscriptions"),
    path("favorites/", FavoritesView.as_view(), name="favorites"),
    path("shopping_cart/", ShoppingCartView.as_view(), name="shopping_cart"),
    path("create_recipe/", CreateRecipeView.as_view(), name="create_recipe"),
    path("edit_recipe/<int:id>/", EditRecipeView.as_view(), name="edit_recipe"),
    path("password_change/", PasswordChangeView.as_view(), name="password_change"),
]
