import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse

from listings.models import Listing


class Cart(models.Model):
    """A buyer's in-progress selection. One cart per buyer, reused forever."""

    buyer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items.all()), Decimal('0.00'))

    @property
    def item_count(self) -> int:
        return sum(item.quantity for item in self.items.all())

    def __str__(self) -> str:
        return f"Cart for {self.buyer}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Adding the same listing twice bumps the quantity instead of creating
        # a second row -- the database enforces it so a double-submit can't slip through.
        constraints = [
            models.UniqueConstraint(fields=['cart', 'listing'], name='unique_cart_listing')
        ]
        ordering = ['added_at']

    @property
    def subtotal(self) -> Decimal:
        return self.listing.price * self.quantity

    def __str__(self) -> str:
        return f'{self.quantity} x {self.listing.title}'


class Order(models.Model):
    """A confirmed purchase. Prices are copied in, never looked up again."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        SHIPPED = 'SHIPPED', 'Shipped'
        DELIVERED = 'DELIVERED', 'Delivered'
        CANCELLED = 'CANCELLED', 'Cancelled'

    reference = models.CharField(max_length=12, unique=True, editable=False)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    delivery_address = models.TextField()
    contact_phone = models.CharField(max_length=20)
    note = models.CharField(max_length=200, blank=True)
    # Snapshot of what the buyer actually agreed to pay. Recomputing this from
    # the listings later would give the wrong answer once a farmer edits a price.
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        """Can this order still move forward or be cancelled?"""
        return self.status not in {self.Status.DELIVERED, self.Status.CANCELLED}

    def get_absolute_url(self):
        return reverse('orders:detail', args=[self.pk])

    def __str__(self) -> str:
        return f'Order {self.reference}'


class OrderItem(models.Model):
    """One line of an order, with the listing's details frozen at purchase time."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # SET_NULL so deleting a listing never destroys order history.
    listing = models.ForeignKey(
        Listing, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Denormalised so the farmer's sales page is a single query, and so the row
    # still makes sense if the listing is gone.
    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sales',
    )
    title = models.CharField(max_length=120)
    unit = models.CharField(max_length=10)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f'{self.quantity} x {self.title}'
