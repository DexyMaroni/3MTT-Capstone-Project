from django.urls import path

from . import views

app_name = 'listings'

urlpatterns = [
    path('', views.listing_list, name='list'),
    # Static segments come before the <int:pk> pattern so "new" is never
    # mistaken for a listing id.
    path('listing/new/', views.listing_create, name='create'),
    path('listing/<int:pk>/', views.listing_detail, name='detail'),
    path('listing/<int:pk>/edit/', views.listing_update, name='update'),
    path('listing/<int:pk>/delete/', views.listing_delete, name='delete'),
    path('dashboard/', views.dashboard, name='dashboard'),
]
