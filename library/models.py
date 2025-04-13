from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta

class Book(models.Model):
    CONDITION_CHOICES = (
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor')
    )
    
    
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)
    pdf_file = models.FileField(upload_to='book_pdfs/', blank=True, null=True)
    rental_price = models.DecimalField(max_digits=6, decimal_places=2, default=9.99)
    rental_duration_days = models.IntegerField(default=30)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='good')

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
    RENTAL_STATUS = (
        ('pending', 'Pending Payment'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=RENTAL_STATUS, default='pending')
    payment_id = models.CharField(max_length=100, blank=True, null=True)

    def days_remaining(self):
        if not self.end_date:
            return 0
        now = timezone.now()
        if isinstance(self.end_date, str):
            end_date = timezone.datetime.fromisoformat(self.end_date)
        else:
            end_date = self.end_date
        remaining = (end_date - now).total_seconds() / 60  # Convert to minutes
        return max(0, int(remaining))

    def is_active(self):
        return self.status == 'active' and self.days_remaining() > 0

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.status})"

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