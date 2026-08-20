from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import buyer_required, farmer_required
from listings.models import Listing

from .forms import CheckoutForm
from .models import Cart, CartItem, Order, OrderItem

SALES_PAGE_SIZE = 20


def _get_cart(user) -> Cart:
    """Every buyer has exactly one cart; make it on first use."""
    cart, _ = Cart.objects.get_or_create(buyer=user)
    return cart


def _wants_json(request) -> bool:
    """True when the request came from fetch() rather than a form submit."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@buyer_required
def cart_detail(request):
    cart = _get_cart(request.user)
    items = cart.items.select_related('listing', 'listing__farmer')
    return render(
        request,
        'orders/cart.html',
        {'cart': cart, 'items': items},
    )


@require_POST
@buyer_required
def add_to_cart(request, pk):
    listing = get_object_or_404(Listing, pk=pk)

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)

    if not listing.in_stock:
        message = f'"{listing.title}" is out of stock.'
        if _wants_json(request):
            return JsonResponse({'ok': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect(listing.get_absolute_url())

    cart = _get_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, listing=listing, defaults={'quantity': quantity}
    )
    if not created:
        item.quantity += quantity

    # Never let the cart hold more than the farmer actually has.
    capped = False
    if item.quantity > listing.quantity_available:
        item.quantity = listing.quantity_available
        capped = True
    item.save()

    message = (
        f'Only {listing.quantity_available} '
        f'{listing.unit_label(listing.quantity_available)} '
        f'available -- cart updated to that.'
        if capped
        else f'Added "{listing.title}" to your cart.'
    )

    if _wants_json(request):
        # The confirmation dialog reports what is actually in the cart, not
        # what was asked for -- those differ whenever `capped` is True.
        return JsonResponse(
            {
                'ok': True,
                'message': message,
                'capped': capped,
                'item': {
                    'title': listing.title,
                    'quantity': item.quantity,
                    'unit': listing.unit_label(item.quantity),
                    'line_total': f'{item.subtotal:.2f}',
                    'image': listing.image.url if listing.image else '',
                },
                'cart_item_count': cart.item_count,
                'cart_total': f'{cart.total:.2f}',
            }
        )

    messages.success(request, message)
    return redirect('orders:cart')


@require_POST
@buyer_required
def update_cart_item(request, pk):
    item = get_object_or_404(
        CartItem.objects.select_related('listing'), pk=pk, cart__buyer=request.user
    )

    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    if quantity < 1:
        item.delete()
    else:
        item.quantity = min(quantity, item.listing.quantity_available)
        item.save()

    cart = _get_cart(request.user)
    if _wants_json(request):
        return JsonResponse(
            {
                'ok': True,
                'quantity': 0 if quantity < 1 else item.quantity,
                'subtotal': '0.00' if quantity < 1 else f'{item.subtotal:.2f}',
                'cart_total': f'{cart.total:.2f}',
                'cart_item_count': cart.item_count,
            }
        )

    return redirect('orders:cart')


@require_POST
@buyer_required
def remove_from_cart(request, pk):
    item = get_object_or_404(CartItem, pk=pk, cart__buyer=request.user)
    title = item.listing.title
    item.delete()
    messages.success(request, f'Removed "{title}" from your cart.')
    return redirect('orders:cart')


@buyer_required
def checkout(request):
    cart = _get_cart(request.user)
    items = list(cart.items.select_related('listing', 'listing__farmer'))

    if not items:
        messages.info(request, 'Your cart is empty.')
        return redirect('listings:list')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = _place_order(request, cart, form)
            if order is not None:
                messages.success(
                    request, f'Order {order.reference} placed. Thank you!'
                )
                return redirect('orders:detail', pk=order.pk)
            # Stock ran out mid-checkout. _place_order already queued the
            # explanation, so send them back to fix the cart.
            return redirect('orders:cart')
    else:
        form = CheckoutForm(
            initial={
                'contact_phone': request.user.phone,
                'delivery_address': request.user.location,
            }
        )

    return render(
        request,
        'orders/checkout.html',
        {'form': form, 'cart': cart, 'items': items},
    )


def _place_order(request, cart, form):
    """Turn a cart into an order, or return None if stock ran out.

    Everything happens inside one transaction: either the order is written and
    stock is decremented together, or nothing changes at all. Rows are locked
    with select_for_update so two buyers racing for the last crate can't both win.
    """
    with transaction.atomic():
        listing_ids = [item.listing_id for item in cart.items.all()]
        locked = {
            listing.pk: listing
            for listing in Listing.objects.select_for_update().filter(pk__in=listing_ids)
        }

        items = list(cart.items.select_related('listing'))
        for item in items:
            listing = locked.get(item.listing_id)
            if listing is None or not listing.is_active:
                messages.error(
                    request, f'"{item.listing.title}" is no longer available.'
                )
                return None
            if item.quantity > listing.quantity_available:
                messages.error(
                    request,
                    f'Only {listing.quantity_available} left of '
                    f'"{listing.title}". Please adjust your cart.',
                )
                return None

        total = sum(item.listing.price * item.quantity for item in items)

        order = Order.objects.create(
            buyer=request.user,
            delivery_address=form.cleaned_data['delivery_address'],
            contact_phone=form.cleaned_data['contact_phone'],
            note=form.cleaned_data['note'],
            total_amount=total,
        )

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    listing=item.listing,
                    farmer=item.listing.farmer,
                    title=item.listing.title,
                    unit=item.listing.unit,
                    unit_price=item.listing.price,
                    quantity=item.quantity,
                )
                for item in items
            ]
        )

        # F() does the subtraction in SQL, so the value can't go stale between
        # reading it and writing it back.
        for item in items:
            Listing.objects.filter(pk=item.listing_id).update(
                quantity_available=F('quantity_available') - item.quantity
            )

        cart.items.all().delete()

    return order


@buyer_required
def order_list(request):
    orders = Order.objects.filter(buyer=request.user).prefetch_related('items')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('buyer').prefetch_related('items'), pk=pk
    )

    # A buyer sees their own orders; a farmer sees any order containing their
    # produce; staff see everything.
    is_seller = order.items.filter(farmer=request.user).exists()
    if not (order.buyer == request.user or is_seller or request.user.is_staff):
        messages.error(request, 'You do not have access to that order.')
        return redirect('listings:list')

    return render(
        request,
        'orders/order_detail.html',
        {'order': order, 'is_seller': is_seller},
    )


@farmer_required
def sales(request):
    """Order lines containing this farmer's produce, newest first."""
    items = (
        OrderItem.objects.filter(farmer=request.user)
        .select_related('order', 'order__buyer')
        .order_by('-order__created_at', '-pk')
    )
    # Without this the page returns every sale the farmer has ever made, so
    # both the HTML and the query grow without limit. Same page size as the
    # marketplace grid so the two feel consistent.
    page = Paginator(items, SALES_PAGE_SIZE).get_page(request.GET.get('page'))
    return render(request, 'orders/sales.html', {'page_obj': page})


@require_POST
@login_required
def update_order_status(request, pk):
    order = get_object_or_404(Order, pk=pk)

    is_seller = order.items.filter(farmer=request.user).exists()
    if not (is_seller or request.user.is_staff):
        messages.error(request, 'Only the seller can update this order.')
        return redirect('listings:list')

    new_status = request.POST.get('status')
    if new_status not in Order.Status.values:
        messages.error(request, 'Unknown status.')
        return redirect(order.get_absolute_url())

    order.status = new_status
    order.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Order {order.reference} marked {order.get_status_display()}.')
    return redirect(order.get_absolute_url())
