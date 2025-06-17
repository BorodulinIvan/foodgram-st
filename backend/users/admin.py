from django.contrib import admin
from .models import User, Follow


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "username", "first_name", "last_name", "is_staff"]
    search_fields = ["email", "username"]


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ["user", "author"]
    search_fields = ["user__email", "author__email"]
