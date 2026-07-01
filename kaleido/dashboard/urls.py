from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views


app_name = "dashboard"

router = DefaultRouter()
router.register("contacts", views.ContactMessageViewSet, basename="contacts")
router.register("quotes", views.QuoteRequestViewSet, basename="quotes")


urlpatterns = [
    path("", views.dashboard_home, name="home"),
    path("api/charts/", views.dashboard_charts_api, name="charts_api"),
    path("api/", include(router.urls)),
    path("api/stats/", views.dashboard_stats_api, name="stats_api"),
    path("analytics/", views.analytics_page, name="analytics"),
    path("crm/", views.crm_page , name="crm")
    
]