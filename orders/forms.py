from django import forms

from .models import Order


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['delivery_address', 'contact_phone', 'note']
        widgets = {
            'delivery_address': forms.Textarea(
                attrs={'rows': 3, 'placeholder': 'Street, town, state'}
            ),
            'note': forms.TextInput(
                attrs={'placeholder': 'Optional: delivery instructions'}
            ),
        }
        labels = {
            'note': 'Note for the farmer',
        }
