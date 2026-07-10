from django.db.models import Q
from products.models import Product, RecommendationEvent


class RecommendationEngine:

    @staticmethod
    def similar_products(product, limit=8):
        """
        Find products similar to the current product.
        """

        queryset = Product.objects.filter(
            is_active=True
        ).exclude(
            id=product.id
        )

        if product.category:
            queryset = queryset.filter(category=product.category)

        return queryset[:limit]

    @staticmethod
    def same_supplier(product, limit=8):

        queryset = Product.objects.filter(
            supplier_record=product.supplier_record,
            is_active=True,
        ).exclude(id=product.id)

        return queryset[:limit]

    @staticmethod
    def keyword_matches(product, limit=8):

        queryset = Product.objects.filter(
            Q(name__icontains=product.name.split()[0]) |
            Q(description__icontains=product.name.split()[0]),
            is_active=True,
        ).exclude(id=product.id)

        return queryset[:limit]

    @staticmethod
    def recommendations(product):

        similar = RecommendationEngine.similar_products(product)

        if similar.exists():
            return similar

        supplier = RecommendationEngine.same_supplier(product)

        if supplier.exists():
            return supplier

        return RecommendationEngine.keyword_matches(product)
    

    @staticmethod
    def customer_recommendations(user, limit=8):
        """
        Recommend products based on a customer's previous quote items.
        """
        if not user.is_authenticated or not user.email:
            return Product.objects.filter(is_active=True, is_featured=True)[:limit]

        from products.models import QuoteItem

        quote_items = QuoteItem.objects.filter(
            quote__email__iexact=user.email
        )

        keywords = []

        for item in quote_items:
            if item.product_name:
                keywords.extend(item.product_name.split()[:2])
            if item.category:
                keywords.append(item.category)

        queryset = Product.objects.filter(is_active=True)

        if keywords:
            query = Q()

            for keyword in keywords:
                query |= Q(name__icontains=keyword)
                query |= Q(description__icontains=keyword)
                query |= Q(category__name__icontains=keyword)

            queryset = queryset.filter(query).distinct()

        else:
            queryset = queryset.filter(is_featured=True)

        return queryset[:limit]
    
    @staticmethod
    def log_recommendations(products, context, user=None):
        for product in products:
            RecommendationEvent.objects.create(
                user=user if user and user.is_authenticated else None,
                product_name=product.name,
                product_slug=product.slug,
                context=context,
            )