from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.profile_settings, name="profile_settings"),
    path("assets/", views.asset_library, name="asset_library"),

    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/<int:order_id>/reorder/", views.reorder_order, name="reorder_order"),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="customers/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(
            next_page="brands:home",
        ),
        name="logout",
    ),
    path("orders/<int:order_id>/artwork/upload/", views.upload_artwork, name="upload_artwork"),
    path("artwork/<int:proof_id>/approve/", views.approve_artwork, name="approve_artwork"),
    path("artwork/<int:proof_id>/changes/", views.request_artwork_changes, name="request_artwork_changes"),
    path("orders-analytics/", views.order_analytics, name="order_analytics"),
    path("crm/", views.crm_dashboard, name="crm_dashboard"),
    path("crm/leads/<int:lead_id>/", views.crm_lead_detail, name="crm_lead_detail"),
    path("crm/activities/<int:activity_id>/complete/", views.complete_crm_activity, name="complete_crm_activity"),
    path("crm/analytics/", views.crm_analytics, name="crm_analytics"),
    path("executive-dashboard/", views.executive_dashboard, name="executive_dashboard"),
    path("api/executive/summary/", views.executive_summary_api, name="executive_summary_api"),
    path("api/executive/order-status/", views.executive_order_status_api, name="executive_order_status_api"),
    path("api/executive/crm-pipeline/", views.executive_crm_pipeline_api, name="executive_crm_pipeline_api"),
    path("api/executive/supplier-sync/", views.executive_supplier_sync_api, name="executive_supplier_sync_api"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<slug:product_slug>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:item_id>/", views.update_cart_item, name="update_cart_item"),
    path("cart/remove/<int:item_id>/", views.remove_cart_item, name="remove_cart_item"),
    path("checkout/", views.checkout, name="checkout"),
    path("addresses/", views.address_list, name="address_list"),
    path("checkout/success/<int:order_id>/", views.checkout_success, name="checkout_success"),

    path("payments/start/<int:order_id>/", views.start_payment, name="start_payment"),
    path("payments/success/<int:order_id>/", views.payment_success, name="payment_success"),
    path("payments/cancel/<int:order_id>/", views.payment_cancel, name="payment_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]