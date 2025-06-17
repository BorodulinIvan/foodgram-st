from rest_framework import viewsets, status, views, serializers
from django.contrib.auth import authenticate, login, logout
from api.serializers import Base64ImageField
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.filters import SearchFilter
from django.db.models import Sum
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import render, redirect, get_object_or_404
from users.models import User, Follow
from recipes.models import Recipe, Ingredient, RecipeIngredient, Favorite, ShoppingCart
from api.serializers import (
    UserCreateSerializer,
    UserSerializer,
    IngredientSerializer,
    UserPublicSerializer,
    RecipeCreateSerializer,
    SetPasswordSerializer,
    RecipeDetailsSerializer,
    RecipeSummarySerializer,
    FavoriteRecipeSerializer,
    UserListSerializer,
    ShoppingCartResponseSerializer,
    FollowSerializer,
    AvatarResponseSerializer,
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from api.filters import RecipeFilter, IngredientFilter
from api.pagination import CustomPageNumberPagination
from api.permissions import IsOwnerOrReadOnly
from django.views.generic.edit import CreateView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.contrib.auth.views import PasswordChangeView as AuthPasswordChangeView
from django.urls import reverse_lazy


class SignUpView(CreateView):
    template_name = "signup.html"
    model = User
    fields = ["email", "username", "first_name", "last_name", "password"]
    success_url = reverse_lazy("login")

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            return redirect(self.success_url)
        return self.form_invalid(form)


class LoginView(views.APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return Response({"message": "Login successful"}, status=status.HTTP_200_OK)
        return Response(
            {"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST
        )


class LogoutView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(
            {
                "message": "Logout successful",
                "detail": "Your session has been terminated",
            },
            status=status.HTTP_200_OK,
        )


class UserProfileView(DetailView):
    model = User
    template_name = "profile.html"
    context_object_name = "user"

    pk_url_kwarg = "user_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = self.get_object()
        user = self.request.user

        context["recipes"] = Recipe.objects.filter(author=profile_user)
        context["can_follow"] = user.is_authenticated and user.id != profile_user.id
        context["is_following"] = (
            user.is_authenticated
            and Follow.objects.filter(user=user, author=profile_user).exists()
        )
        return context


class RecipeDetailView(DetailView):
    model = Recipe
    template_name = "recipe_detail.html"
    context_object_name = "recipe"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart_count"] = ShoppingCart.objects.filter(
            user=self.request.user
        ).count()
        return context


class SubscriptionsView(ListView):
    model = Follow
    template_name = "subscriptions.html"
    context_object_name = "subscriptions"
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Follow.objects.filter(user=self.request.user)


class FavoritesView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        """Получить список избранных рецептов с пагинацией"""
        user = request.user
        favorites = Recipe.objects.filter(in_favorites__user=user)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(favorites, request)

        serializer = RecipeSummarySerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Добавить рецепт в избранное"""
        recipe_id = request.data.get("id")
        if not recipe_id:
            return Response(
                {"error": "Не указан ID рецепта"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recipe = Recipe.objects.get(id=recipe_id)
        except Recipe.DoesNotExist:
            return Response(
                {"error": "Рецепт не найден"}, status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        if recipe.in_favorites.filter(user=user).exists():
            return Response(
                {"error": "Рецепт уже в избранном"}, status=status.HTTP_400_BAD_REQUEST
            )

        Favorite.objects.create(user=user, recipe=recipe)
        serializer = RecipeSummarySerializer(recipe, context={"request": request})
        serializer_data = serializer.data
        serializer_data["cart_count"] = ShoppingCart.objects.filter(user=user).count()
        return Response(serializer_data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        """Удалить рецепт из избранного"""
        recipe_id = request.data.get("id")
        if not recipe_id:
            return Response(
                {"error": "Не указан ID рецепта"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recipe = Recipe.objects.get(id=recipe_id)
        except Recipe.DoesNotExist:
            return Response(
                {"error": "Рецепт не найден"}, status=status.HTTP_404_NOT_FOUND
            )

        user = request.user
        favorite = Favorite.objects.filter(user=user, recipe=recipe)
        if favorite.exists():
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        return Response(
            {"error": "Рецепт не найден в избранном"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ShoppingCartView(LoginRequiredMixin, View):
    """Представление для работы с корзиной покупок"""

    template_name = "shopping_cart.html"

    def get(self, request):
        """Обработка GET-запроса (просмотр корзины)"""
        cart_items = ShoppingCart.objects.filter(user=request.user).select_related(
            "recipe"
        )
        return render(
            request,
            self.template_name,
            {"cart_items": cart_items, "cart_count": cart_items.count()},
        )

    def post(self, request):
        """Обработка POST-запроса (добавление/удаление из корзины)"""
        user = request.user

        if "add" in request.POST:
            return self._add_to_cart(request, user)
        elif "remove" in request.POST:
            return self._remove_from_cart(request, user)

        return self.get(request)

    def _add_to_cart(self, request, user):
        """Добавление рецепта в корзину"""
        recipe_id = request.POST.get("recipe_id")
        if not recipe_id:
            return self.get(request)

        try:
            recipe = Recipe.objects.get(id=recipe_id)
            ShoppingCart.objects.get_or_create(user=user, recipe=recipe)
        except Recipe.DoesNotExist:
            pass

        return redirect("shopping_cart")

    def _remove_from_cart(self, request, user):
        """Удаление рецепта из корзины"""
        recipe_id = request.POST.get("recipe_id")
        if not recipe_id:
            return self.get(request)

        ShoppingCart.objects.filter(user=user, recipe_id=recipe_id).delete()

        return redirect("shopping_cart")


class CreateRecipeView(CreateView):
    model = Recipe
    template_name = "create_recipe.html"
    fields = ["title", "image", "description", "ingredients", "preparation_time"]
    success_url = reverse_lazy("recipe_list")
    permission_classes = [IsAuthenticated]

    def form_valid(self, form):
        form.instance.author = self.request.user
        cart_count = ShoppingCart.objects.filter(user=self.request.user).count()
        return self.render_to_response(self.get_context_data(cart_count=cart_count))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart_count"] = kwargs.get(
            "cart_count", ShoppingCart.objects.filter(user=self.request.user).count()
        )
        return context


class EditRecipeView(UpdateView):
    model = Recipe
    template_name = "edit_recipe.html"
    fields = ["title", "image", "description", "ingredients", "preparation_time"]
    success_url = reverse_lazy("recipe_list")
    permission_classes = [IsAuthenticated]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cart_count"] = ShoppingCart.objects.filter(
            user=self.request.user
        ).count()
        return context

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.author != self.request.user and not self.request.user.is_staff:
            raise PermissionError("You can only edit your own recipes.")
        return obj


class PasswordChangeView(AuthPasswordChangeView):
    template_name = "password_change.html"
    success_url = reverse_lazy("profile", kwargs={"user_id": 1})
    permission_classes = [IsAuthenticated]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    pagination_class = CustomPageNumberPagination

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        if self.action == "list":
            if not self.request.user.is_authenticated:
                return UserPublicSerializer
            return UserListSerializer
        return UserSerializer

    def list(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            self.queryset = self.queryset.only(
                "id", "username", "first_name", "last_name", "email", "avatar"
            )

        if "limit" in request.query_params:
            request.query_params._mutable = True
            request.query_params["page_size"] = request.query_params["limit"]
            request.query_params._mutable = False

        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = UserSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = get_object_or_404(User, pk=pk)
        serializer = UserSerializer(user, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post", "patch", "put", "delete"],
        permission_classes=[IsAuthenticated],
        url_path="me/avatar",
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def upload_avatar(self, request):
        user = request.user

        if request.method in ["POST", "PATCH", "PUT"]:
            if "avatar" not in request.data:
                return Response(
                    {"error": "Avatar image is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                user.avatar = Base64ImageField().to_internal_value(
                    request.data["avatar"]
                )
                user.save()

                avatar_url = request.build_absolute_uri(user.avatar.url)
                serializer = AvatarResponseSerializer(data={"avatar": avatar_url})
                serializer.is_valid(raise_exception=True)

                return Response(serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response(
                    {"error": "Invalid image format"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        elif request.method == "DELETE":
            if not user.avatar:
                return Response(
                    {"error": "No avatar to delete"}, status=status.HTTP_400_BAD_REQUEST
                )

            user.avatar.delete()
            user.avatar = None
            user.save()

            return Response({"avatar": None}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def set_password(self, request):
        """Смена пароля текущего пользователя"""
        user = request.user

        if not isinstance(request.data, dict):
            return Response(
                {"error": "Данные должны быть в формате JSON"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        required_fields = [
            "current_password",
            "new_password",
        ]
        if any(field not in request.data for field in required_fields):
            return Response(
                {"error": "Необходимо заполнить все поля"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(request.data["current_password"]):
            return Response(
                {"current_password": ["Неверный текущий пароль"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SetPasswordSerializer(
            data=request.data, context={"request": request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "delete"],
        url_path="subscribe",
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, pk=None):
        author = get_object_or_404(User, pk=pk)

        if request.method == "POST":
            if request.user.following.filter(author=author).exists():
                return Response(status=status.HTTP_400_BAD_REQUEST)
            serializer = FollowSerializer(
                data={"user": request.user.id, "author": author.id},
                context={"request": request, "author": author},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        follow = request.user.following.filter(author=author)
        if not follow:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        follow.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="subscriptions")
    def subscriptions(self, request):
        queryset = request.user.following.select_related("author")
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = FollowSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)

        serializer = FollowSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = IngredientFilter
    search_fields = ["^name"]
    pagination_class = None

    def fetch_data_set(self):
        initial_set = Ingredient.objects.all()
        search_value = self.request.query_params.get("name", None)
        if search_value:
            initial_set = initial_set.filter(name__istartswith=search_value)
        return initial_set

    def get_queryset(self):
        return self.fetch_data_set()


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by("-date_created")
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = RecipeFilter
    search_fields = ["title"]
    pagination_class = CustomPageNumberPagination
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    serializer_class = RecipeDetailsSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update(
            {"request": self.request, "format": self.format_kwarg, "view": self}
        )
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        is_favorited = self.request.query_params.get("is_favorited")
        if is_favorited == "1" and not self.request.user.is_authenticated:
            return queryset.none()
        return queryset

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return RecipeCreateSerializer
        return RecipeDetailsSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        recipe = serializer.instance
        detailed_serializer = RecipeDetailsSerializer(
            recipe, context={"request": request}
        )

        headers = self.get_success_headers(detailed_serializer.data)
        return Response(
            detailed_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except serializers.ValidationError as e:
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    @action(
        detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        try:
            recipe = self.get_object()
        except Recipe.DoesNotExist:
            return Response(
                {"error": "Рецепт не найден"}, status=status.HTTP_404_NOT_FOUND
            )
        user = request.user
        if request.method == "POST":
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {"error": "Рецепт уже в избранном"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            favorite = Favorite.objects.create(user=user, recipe=recipe)
            serializer = FavoriteRecipeSerializer(
                favorite, context={"request": request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        favorite = Favorite.objects.filter(user=user, recipe=recipe)
        if favorite.exists():
            favorite.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Рецепт не в избранном"}, status=status.HTTP_400_BAD_REQUEST
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="shopping_cart",
        permission_classes=[IsAuthenticated],
    )
    def add_to_shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        if ShoppingCart.objects.filter(user=user, recipe=recipe).exists():
            return Response(
                {"error": "Рецепт уже в списке покупок"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ShoppingCart.objects.create(user=user, recipe=recipe)

        response_data = {
            "id": recipe.id,
            "name": recipe.title,
            "image": (
                request.build_absolute_uri(recipe.image.url) if recipe.image else None
            ),
            "cooking_time": recipe.preparation_time,
        }

        serializer = ShoppingCartResponseSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @add_to_shopping_cart.mapping.delete
    def remove_from_shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        user = request.user

        try:
            cart_item = ShoppingCart.objects.get(user=user, recipe=recipe)
            cart_item.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ShoppingCart.DoesNotExist:
            return Response(
                {"error": "Рецепта нет в списке покупок"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def download_shopping_cart(self, request):
        user = request.user

        recipe_ids = ShoppingCart.objects.filter(user=user).values_list(
            "recipe_id", flat=True
        )

        if not recipe_ids:
            return Response(
                {"detail": "Ваша корзина покупок пуста"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingredients = (
            RecipeIngredient.objects.filter(recipe_id__in=recipe_ids)
            .values("ingredient__name", "ingredient__measurement_unit")
            .annotate(total_amount=Sum("amount"))
            .order_by("ingredient__name")
        )

        response = HttpResponse(content_type="text/plain")

        content = "Список покупок:\n\n"
        for i, item in enumerate(ingredients, 1):
            name = item["ingredient__name"]
            amount = item["total_amount"]
            unit = item["ingredient__measurement_unit"]

            content += f"{i}. {name} - {amount} {unit}\n"

        response.write(content)
        return response

    @action(
        detail=True, methods=["get"], url_path="get-link", permission_classes=[AllowAny]
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        base_url = request.build_absolute_uri("/")[:-1]
        return Response(
            {"short-link": f"{base_url}/recipes/{recipe.id}"}, status=status.HTTP_200_OK
        )
