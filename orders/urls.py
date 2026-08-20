from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/', views.cart_detail, name='cart'),
    path('cart/add/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/item/<int:pk>/update/', views.update_cart_item, name='update_item'),
    path('cart/item/<int:pk>/remove/', views.remove_from_cart, name='remove_item'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.order_list, name='list'),
    path('orders/<int:pk>/', views.order_detail, name='detail'),
    path('orders/<int:pk>/status/', views.update_order_status, name='update_status'),
    path('sales/', views.sales, name='sales'),
]
