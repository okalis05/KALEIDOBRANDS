from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views


app_name = "dashboard"

router = DefaultRouter()
router.register("contacts", views.ContactMessageViewSet, basename="contacts")
router.register("quotes", views.QuoteRequestViewSet, basename="quotes")


urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("api/", include(router.urls)),
]