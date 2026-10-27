from django.urls import path
from . import views

app_name = "brands"

urlpatterns = [
    path("", views.home, name="home"),
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-of-service/", views.terms_of_service, name="terms_of_service"),
]