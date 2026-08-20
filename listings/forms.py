from django import forms

from .models import Listing


class ListingForm(forms.ModelForm):
    """Create/edit form for a farmer's produce listing.

    `farmer` is deliberately absent -- the view sets it from request.user, so a
    crafted POST can't assign a listing to someone else.
    """

    class Meta:
        model = Listing
        fields = [
            'title',
            'category',
            'description',
            'price',
            'unit',
            'quantity_available',
            'image',
            'image_alt',
            'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Fresh Sweet Potatoes'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'image_alt': forms.TextInput(
                attrs={'placeholder': 'e.g. a full basket of red tomatoes on a table'}
            ),
        }

    def clean_price(self):
        price = self.cleaned_data['price']
        if price <= 0:
            raise forms.ValidationError('Price must be greater than zero.')
        return price
