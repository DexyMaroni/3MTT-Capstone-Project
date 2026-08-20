from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    """A produce grouping, e.g. Vegetables, Grains, Tubers."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{reverse('listings:list')}?category={self.slug}"

    def __str__(self) -> str:
        return self.name


class ListingQuerySet(models.QuerySet):
    """Reusable filters, so views don't repeat query logic."""

    def available(self):
        return self.filter(is_active=True, quantity_available__gt=0)

    def with_related(self):
        # Avoids the N+1 queries a listing grid would otherwise make when it
        # renders each item's farmer and category.
        return self.select_related('farmer', 'category')

    def search(self, term):
        if not term:
            return self
        return self.filter(
            models.Q(title__icontains=term)
            | models.Q(description__icontains=term)
            | models.Q(farmer__location__icontains=term)
        )


class Listing(models.Model):
    """A quantity of produce a farmer is offering for sale."""

    class Unit(models.TextChoices):
        KG = 'kg', 'Kilogram'
        BAG = 'bag', 'Bag'
        BASKET = 'basket', 'Basket'
        CRATE = 'crate', 'Crate'
        BUNCH = 'bunch', 'Bunch'
        PIECE = 'piece', 'Piece'
        LITRE = 'litre', 'Litre'

    farmer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='listings',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='listings',
    )
    title = models.CharField(max_length=120)
    description = models.TextField(
        blank=True,
        help_text='Variety, harvest date, storage notes -- anything a buyer would ask.',
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        help_text='Price per unit, in Naira.',
    )
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.KG)
    quantity_available = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='listings/%Y/%m/', blank=True)
    image_alt = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='Photo description',
        help_text=(
            'What the photo shows, for people using a screen reader. '
            'Describe the picture, not the produce -- "a full basket of red '
            'tomatoes on a wooden table", not just the title.'
        ),
    )
    image_credit = models.CharField(
        max_length=255,
        blank=True,
        help_text=(
            'Photographer and licence, shown under the picture. Required for '
            'Creative Commons images; leave blank for a photo the farmer took.'
        ),
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Uncheck to hide this listing without deleting it.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ListingQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            # The marketplace grid filters on these two columns on every page load.
            models.Index(fields=['is_active', '-created_at']),
        ]

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.quantity_available > 0

    def unit_label(self, quantity=None) -> str:
        """The unit name, pluralised to match `quantity`.

        get_unit_display() only ever returns the singular label from
        Unit.choices, which produced "Only 50 litre available". Naive +"s"
        is not enough either, because "Bunch" has to become "Bunches".
        """
        label = self.get_unit_display().lower()
        if quantity is None:
            quantity = self.quantity_available
        if quantity == 1:
            return label
        # English adds -es after a sibilant; of our units only "bunch" hits
        # this, but the rule is cheaper to keep than a per-unit table.
        suffix = 'es' if label.endswith(('ch', 'sh', 's', 'x', 'z')) else 's'
        return label + suffix

    def get_absolute_url(self):
        return reverse('listings:detail', args=[self.pk])

    def __str__(self) -> str:
        return f'{self.title} ({self.get_unit_display()})'
