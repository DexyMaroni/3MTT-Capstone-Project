from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import farmer_required
from orders.models import Order, OrderItem

from .forms import ListingForm
from .models import Category, Listing

PAGE_SIZE = 9


def listing_list(request):
    """The marketplace grid: every available listing, searchable and filterable."""
    search_term = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    sort = request.GET.get('sort', 'newest')

    listings = Listing.objects.available().with_related().search(search_term)

    if category_slug:
        listings = listings.filter(category__slug=category_slug)

    sort_options = {
        'newest': '-created_at',
        'price_low': 'price',
        'price_high': '-price',
        'title': 'title',
    }
    listings = listings.order_by(sort_options.get(sort, '-created_at'))

    page = Paginator(listings, PAGE_SIZE).get_page(request.GET.get('page'))

    # Keeps the current filters attached to pagination links.
    querystring = request.GET.copy()
    querystring.pop('page', None)

    return render(
        request,
        'listings/listing_list.html',
        {
            'page_obj': page,
            # Count only what a shopper can actually buy, so the sidebar
            # numbers match the grid.
            'categories': Category.objects.annotate(
                listing_count=Count(
                    'listings',
                    filter=Q(listings__is_active=True, listings__quantity_available__gt=0),
                )
            ),
            'search_term': search_term,
            'active_category': category_slug,
            'sort': sort,
            'querystring': querystring.urlencode(),
        },
    )


def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing.objects.with_related(), pk=pk
    )

    # A hidden listing should still be reachable by its owner (to preview) and
    # by staff, but not by the public.
    if not listing.is_active and listing.farmer != request.user and not request.user.is_staff:
        messages.error(request, 'That listing is no longer available.')
        return redirect('listings:list')

    related = (
        Listing.objects.available()
        .with_related()
        .filter(category=listing.category)
        .exclude(pk=listing.pk)[:3]
    )

    return render(
        request,
        'listings/listing_detail.html',
        {'listing': listing, 'related': related},
    )


@farmer_required
def dashboard(request):
    """A farmer's home: their listings plus headline sales numbers."""
    listings = (
        Listing.objects.filter(farmer=request.user)
        .select_related('category')
        .order_by('-created_at')
    )

    # Cancelled orders shouldn't count as income.
    sales = OrderItem.objects.filter(farmer=request.user).exclude(
        order__status=Order.Status.CANCELLED
    )
    # One aggregate query rather than looping in Python: the database
    # multiplies each line out and sums the result.
    totals = sales.aggregate(
        units=Sum('quantity'),
        revenue=Sum(
            F('unit_price') * F('quantity'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
    )

    return render(
        request,
        'listings/dashboard.html',
        {
            'listings': listings,
            'active_count': listings.filter(is_active=True).count(),
            'out_of_stock_count': listings.filter(quantity_available=0).count(),
            'units_sold': totals['units'] or 0,
            'revenue': totals['revenue'] or Decimal('0.00'),
        },
    )


@farmer_required
def listing_create(request):
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.farmer = request.user
            listing.save()
            messages.success(request, f'"{listing.title}" is now listed.')
            return redirect('listings:dashboard')
    else:
        form = ListingForm()

    return render(
        request,
        'listings/listing_form.html',
        {'form': form, 'heading': 'Add a listing', 'submit_label': 'Publish listing'},
    )


@farmer_required
def listing_update(request, pk):
    # Scoping the lookup to request.user is what stops one farmer editing
    # another's listing -- a permission check you can't forget to write.
    listing = get_object_or_404(Listing, pk=pk, farmer=request.user)

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{listing.title}" updated.')
            return redirect('listings:dashboard')
    else:
        form = ListingForm(instance=listing)

    return render(
        request,
        'listings/listing_form.html',
        {
            'form': form,
            'listing': listing,
            'heading': f'Edit {listing.title}',
            'submit_label': 'Save changes',
        },
    )


@farmer_required
def listing_delete(request, pk):
    listing = get_object_or_404(Listing, pk=pk, farmer=request.user)

    if request.method == 'POST':
        title = listing.title
        listing.delete()
        messages.success(request, f'"{title}" deleted.')
        return redirect('listings:dashboard')

    return render(request, 'listings/listing_confirm_delete.html', {'listing': listing})
