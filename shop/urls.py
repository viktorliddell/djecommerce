from django.urls import path
from .views import *

app_name = 'shop'

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('cart/', CartView.as_view(), name='cart'),
    path('product/<slug:slug>/', ProductView.as_view(), name='product'),
    path('add-to-cart/<slug:slug>/', add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<slug:slug>/',
         remove_from_cart, name='remove_from_cart'),
    path('remove-item-from-cart/<slug:slug>/',
         remove_single_item_from_cart, name='remove_single_item_from_cart'),
    path('add-item-to-cart/<slug:slug>/',
         add_single_item_to_cart, name='add_single_item_to_cart'),
    path('remove-item-from-product/<slug:slug>/',
         remove_single_item_from_product, name='remove_single_item_from_product'),
    path('add-item-from-product/<slug:slug>/',
         add_single_item_from_product, name='add_single_item_from_product'),
]
