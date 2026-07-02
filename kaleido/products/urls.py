from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_home, name="home"),
    path("search/", views.product_search, name="search"),
    path("api/search/", views.live_search, name="live-search"),
    path("quote-cart/", views.quote_cart, name="quote_cart"),
    path("category/<slug:slug>/", views.category_detail, name="category"),
    path("<slug:slug>/", views.product_detail, name="detail"),
]