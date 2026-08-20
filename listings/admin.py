from django.contrib import admin

from .models import Category, Listing


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ['title', 'farmer', 'category', 'price', 'unit', 'quantity_available', 'is_active']
    list_filter = ['is_active', 'category', 'unit']
    search_fields = ['title', 'description', 'farmer__username']
    list_editable = ['price', 'quantity_available', 'is_active']
    autocomplete_fields = ['farmer']
    date_hierarchy = 'created_at'
