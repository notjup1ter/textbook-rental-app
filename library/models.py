from django.db import models
from django.contrib.auth.models import User

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