from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_home, name="home"),

     path("supplier-inventory/",views.supplier_inventory_dashboard, name="supplier_inventory_dashboard",),
    path("search/", views.product_search, name="search"),
    path("api/search/", views.live_search, name="live-search"),

    path("supplier-sync/", views.supplier_sync_dashboard, name="supplier_sync_dashboard"),
    path("supplier-sync/upload/", views.supplier_csv_upload, name="supplier_csv_upload"),
    path("supplier-analytics/", views.supplier_analytics, name="supplier_analytics"),

    path("api/supplier-stats/", views.supplier_stats_api, name="supplier_stats_api"),
    path("api/supplier-categories/", views.supplier_categories_api, name="supplier_categories_api"),
    path("api/supplier-pricing/", views.supplier_pricing_api, name="supplier_pricing_api"),

    path("supplier/<slug:slug>/", views.supplier_detail, name="supplier_detail"),
    path("supplier/<slug:slug>/search/", views.supplier_search, name="supplier_search"),

    path("quotes/", views.quote_history, name="quote_history"),
    path("quotes/<int:quote_id>/", views.quote_detail, name="quote_detail"),        
    path("quote-cart/", views.quote_cart, name="quote_cart"),
    path("quote-success/", views.quote_success, name="quote_success"),
    path("category/<slug:slug>/", views.category_detail, name="category"),
    path("quote-builder/",views.quote_builder,name="quote_builder"),
    path("recommendation-analytics/", views.recommendation_analytics, name="recommendation_analytics"),
    path("purchase-orders/",views.purchase_order_list, name="purchase_order_list"),
    path("purchase-orders/<int:po_id>/", views.purchase_order_detail, name="purchase_order_detail"),
    path("purchase-orders/<int:po_id>/pdf/",views.generate_purchase_order_pdf_view, name="generate_purchase_order_pdf"),
    path("purchase-orders/<int:po_id>/send/",views.send_purchase_order, name="send_purchase_order",),
    path("purchase-orders/<int:po_id>/update/", views.update_purchase_order_status, name="update_purchase_order_status"),
    path("supplier-operations/", views.supplier_operations_dashboard, name="supplier_operations_dashboard"),
    path("<slug:slug>/", views.product_detail, name="detail"),
    
]