from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    pdf_file = models.FileField(upload_to='book_pdfs/', blank=True, null=True)

    def __str__(self):
        return self.title

class UserLibrary(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    books = models.ManyToManyField(Book, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Library"

class Profile(models.Model):
    USER_ROLES = (
        ('librarian', 'Librarian'),
        ('patron', 'Patron'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=USER_ROLES, default='patron')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)

    theme = (('light', 'Light'), ('dark', 'Dark'))
    preference = models.CharField(max_length=5, choices=theme, default='light')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

class ApprovedLibrarianEmail(models.Model):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.email 
    

class Collection(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    books = models.ManyToManyField(Book, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cover_image = models.ImageField(upload_to='collection_covers/', blank=True, null=True)

    def __str__(self):
        return self.title

class Rental(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField()
    active = models.BooleanField(default=True)

class FakeInvoice(models.Model):
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE)
    amount = models.DecimalField(decimal_places=2, max_digits=6)
    issued_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=True)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=200, blank=True, help_text="URL or named route to link the notification to")
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.message}"