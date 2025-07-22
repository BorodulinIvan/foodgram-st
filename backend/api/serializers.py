from rest_framework import serializers
from django.core.files.base import ContentFile
import base64
import uuid
from django.core.validators import MinValueValidator
from users.models import User, Follow
from recipes.models import (Recipe, Ingredient, RecipeIngredient, Favorite,
                            ShoppingCart)
from django.core.validators import MinValueValidator, MaxValueValidator


MIN_VALUE_FOR_VALIDATOR = 1
MAX_VALUE_FOR_VALIDATOR = 32000


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith("data:image"):
            format, imgstr = data.split(";base64,")
            ext = format.split("/")[-1]
            img_data = base64.b64decode(imgstr)
            file_name = f"{uuid.uuid4()}.{ext}"
            return ContentFile(img_data, name=file_name)
        return super().to_internal_value(data)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "username", "first_name", "last_name",
                  "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def get_avatar(self, obj):
        request = self.context.get("request")
        if obj.avatar and hasattr(obj.avatar, "url"):
            return request.build_absolute_uri(obj.avatar.url)
        return None


class RecipeShortSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="title")
    cooking_time = serializers.IntegerField(source="preparation_time")

    class Meta:
        fields = ("id", "name", "image", "cooking_time")
        read_only_fields = fields
        model = Recipe


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
            "recipes",
            "recipes_count",
        ]
        read_only_fields = ["is_subscribed", "avatar", "recipes",
                            "recipes_count"]

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return (
                request.user.is_authenticated
                and request.user.following.filter(author=obj).exists()
            )
        return False

    def get_recipes(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            recipes_limit = request.query_params.get("recipes_limit")
            recipes = obj.recipes.all()

            if recipes_limit and recipes_limit.isdigit():
                recipes = recipes[: int(recipes_limit)]

            return RecipeShortSerializer(
                recipes, many=True, context={"request": request}
            ).data
        return []

    def get_recipes_count(self, obj):
        if (
            self.context.get("request")
            and self.context["request"].user.is_authenticated
        ):
            return obj.recipes.count()
        return 0

    def get_fields(self):
        fields = super().get_fields()
        view = self.context.get("view")
        if view and view.action in ["retrieve", "me"]:
            fields.pop("recipes", None)
            fields.pop("recipes_count", None)
        return fields


class UserListSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email",
                  "avatar"]
        read_only_fields = fields


class AvatarResponseSerializer(serializers.Serializer):
    avatar = serializers.CharField()

    class Meta:
        fields = ["avatar"]


class UserPublicSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email",
                  "avatar"]
        read_only_fields = fields


class IngredientAmountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    amount = serializers.IntegerField(validators=[
        MinValueValidator(MIN_VALUE_FOR_VALIDATOR),
        MaxValueValidator(MAX_VALUE_FOR_VALIDATOR),])

    def validate_id(self, value):
        if not Ingredient.objects.filter(id=value).exists():
            raise serializers.ValidationError(
                "Ингредиент с таким ID не существует.")
        return value


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name", "measurement_unit"]


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source="ingredient.id")
    name = serializers.ReadOnlyField(source="ingredient.name")
    measurement_unit = serializers.ReadOnlyField(
        source="ingredient.measurement_unit")
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ["id", "name", "measurement_unit", "amount"]


class RecipeCreateSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    name = serializers.CharField(source="title", max_length=256)
    text = serializers.CharField(source="description")
    cooking_time = serializers.IntegerField(
        source="preparation_time", validators=[
            MinValueValidator(MIN_VALUE_FOR_VALIDATOR),
            MaxValueValidator(MAX_VALUE_FOR_VALIDATOR),]
    )
    ingredients = IngredientAmountSerializer(many=True, write_only=True)
    ingredients_data = RecipeIngredientSerializer(
        source="recipeingredient_set", many=True, read_only=True
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "name",
            "image",
            "text",
            "ingredients",
            "cooking_time",
            "ingredients_data",
        ]

    def validate(self, data):
        if self.instance and "ingredients" not in self.initial_data:
            raise serializers.ValidationError(
                {"ingredients": "Это поле обязательно при обновлении рецепта."}
            )
        return data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError("Нужен хотя бы один ингредиент.")

        seen_ids = set()
        for item in value:

            ingredient_id = item["id"]
            if ingredient_id in seen_ids:
                raise serializers.ValidationError(
                    "Ингредиенты не должны повторяться."
                )
            seen_ids.add(ingredient_id)
        return value

    def create_update_recipes(self, recipe, ingredients_data):
        ingredient_ids = [item['id'] for item in ingredients_data]
        ingredients = Ingredient.objects.in_bulk(ingredient_ids,
                                                 field_name='id')

        recipe_ingredients = []
        for item in ingredients_data:
            ingredient = ingredients.get(item['id'])
            recipe_ingredients.append(
                RecipeIngredient(
                    recipe=recipe,
                    ingredient=ingredient,
                    amount=item['amount'],
                    measurement_unit=ingredient.measurement_unit
                )
            )

        RecipeIngredient.objects.bulk_create(recipe_ingredients)
        return recipe

    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients", [])
        author = self.context["request"].user
        recipe = Recipe(author=author, **validated_data)
        recipe.full_clean()
        recipe.save()

        return self.create_update_recipes(recipe, ingredients_data)

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.full_clean()
        instance.save()

        instance.recipeingredient_set.all().delete()
        return self.create_update_recipes(instance, ingredients_data)

    def to_representation(self, instance):
        return RecipeDetailsSerializer(instance, context=self.context).data


class UserShortSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'is_subscribed',
            'avatar'
        ]

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.followers.filter(user=request.user).exists()

    def get_avatar(self, obj):
        request = self.context.get('request')
        if obj.avatar and hasattr(obj.avatar, 'url'):
            return request.build_absolute_uri(obj.avatar.url)
        return None


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'name', 'measurement_unit', 'amount']


class RecipeDetailsSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)
    ingredients = IngredientInRecipeSerializer(
        source='recipeingredient_set', 
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    name = serializers.CharField(source="title")
    text = serializers.CharField(source="description")
    cooking_time = serializers.IntegerField(source="preparation_time")
    image = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "author",
            "ingredients",
            "is_favorited",
            "is_in_shopping_cart",
            "name",
            "image",
            "text",
            "cooking_time",
        ]

    def get_is_favorited(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.in_favorites.filter(user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        user = self.context["request"].user
        if not user.is_authenticated:
            return False
        return obj.in_shopping_carts.filter(user=user).exists()

    def get_image(self, obj):
        request = self.context.get("request")
        if obj.image and hasattr(obj.image, "url"):
            return request.build_absolute_uri(obj.image.url)
        return None

    def _get_is_subscribed(self, author):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user.following.filter(author=author).exists()

    def _get_avatar_url(self, user):
        request = self.context.get("request")
        if user.avatar and hasattr(user.avatar, "url"):
            return request.build_absolute_uri(user.avatar.url)
        return None


class RecipeSummarySerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    name = serializers.CharField(source="title")
    cooking_time = serializers.IntegerField(source="preparation_time")
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = ["id", "name", "image", "cooking_time"]


class FavoriteRecipeSerializer(serializers.ModelSerializer):
    recipe = RecipeSummarySerializer()

    class Meta:
        model = Favorite
        fields = ["recipe"]


class ShoppingCartResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.CharField()
    cooking_time = serializers.IntegerField()

    class Meta:
        fields = ["id", "name", "image", "cooking_time"]
        read_only_fields = fields


class FollowSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="author.id", read_only=True)
    first_name = serializers.CharField(source="author.first_name",
                                       read_only=True)
    last_name = serializers.CharField(source="author.last_name",
                                      read_only=True)
    email = serializers.EmailField(source="author.email", read_only=True)
    username = serializers.CharField(source="author.username", read_only=True)
    avatar = serializers.ImageField(source="author.avatar", read_only=True)
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = Follow
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar",
            "is_subscribed",
            "recipes",
            "recipes_count",
        )

    def validate(self, data):
        user = self.context["request"].user
        author = self.context["author"]

        if user == author:
            raise serializers.ValidationError(
                "Нельзя подписаться на самого себя.")
        if user.following.filter(author=author).exists():
            raise serializers.ValidationError(
                "Вы уже подписаны на этого пользователя.")

        return data

    def create(self, validated_data):
        user = self.context["request"].user
        author = self.context["author"]

        return Follow.objects.create(user=user, author=author)

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj) -> list:
        request = self.context.get("request")
        recipes = obj.author.recipes.all()

        if not request:
            return RecipeShortSerializer(recipes, many=True,
                                         context=self.context).data

        if limit := request.query_params.get("recipes_limit"):
            try:
                recipes = recipes[: int(limit)]
            except (TypeError, ValueError):
                pass

        serializer = RecipeShortSerializer(recipes, many=True,
                                           context=self.context)
        return serializer.data

    def get_recipes_count(self, obj):
        return obj.author.recipes.count()


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль неверен")
        return value


class UserProfileNoAuthSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
        ]
        read_only_fields = fields

    def get_is_subscribed(self, obj):
        return False
