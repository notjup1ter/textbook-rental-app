from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, Collection, Book, BookRating

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["profile_picture"]


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['title', 'description', 'cover_image']


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'isbn', 'description', 'cover_image', 'pdf_file', 'rental_price', 'rental_duration_days', 'condition']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class RentalPaymentForm(forms.Form):
    card_number = forms.CharField(max_length=16, min_length=16)
    expiry_month = forms.CharField(max_length=2, min_length=2)
    expiry_year = forms.CharField(max_length=2, min_length=2)
    cvv = forms.CharField(max_length=3, min_length=3)

    def clean_card_number(self):
        card_number = self.cleaned_data['card_number']
        if not card_number.isdigit():
            raise forms.ValidationError("Card number must contain only digits")
        return card_number

    def clean_cvv(self):
        cvv = self.cleaned_data['cvv']
        if not cvv.isdigit():
            raise forms.ValidationError("CVV must contain only digits")
        return cvv

class BookRatingForm(forms.ModelForm):
    class Meta:
        model = BookRating
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }