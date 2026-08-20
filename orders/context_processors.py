from django.db.models import Sum

from .models import CartItem


def cart_summary(request):
    """Expose the cart badge count to every template.

    Registered in TEMPLATES['OPTIONS']['context_processors'] so the navbar
    doesn't need every view to pass this in by hand.
    """
    count = 0
    if request.user.is_authenticated and request.user.is_buyer:
        count = (
            CartItem.objects.filter(cart__buyer=request.user).aggregate(
                total=Sum('quantity')
            )['total']
            or 0
        )
    return {'cart_item_count': count}
