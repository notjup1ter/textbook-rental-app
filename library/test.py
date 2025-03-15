from django.test import TestCase
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail
from django.contrib.auth.models import User

class BookTest(TestCase):
    def setUp(self):
        self.book = Book.objects.create(title="Alpha Book", author="alpha")

    def test_create_book(self):
        self.assertEqual(self.book.title, "Alpha Book")
        self.assertEqual(self.book.author, "alpha")

    def test_book_str(self):
        self.assertEqual(str(self.book), "Alpha Book")

class UserLibraryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="beta", password="123")
        self.book = Book.objects.create(title="beta", author="b_author")
        self.user_library = UserLibrary.objects.create(user=self.user)

    def test_create_user_library(self):
        self.assertEqual(self.user_library.user.username, "beta")

    def test_user_library_str(self):
        self.assertEqual(str(self.user_library), "beta's Library")

    # def test_add_book_to_library(self):
    #     self.user_library.books.add(self.book)
    #     self.assertIn(self.book, self.user_library.books.all())
    #
    # def test_remove_book_from_library(self):
    #     self.user_library.books.add(self.book)
    #     self.user_library.books.remove(self.book)
    #     self.assertNotIn(self.book, self.user_library.books.all())


class ProfileTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="gamma", password="abc")
        self.profile = Profile.objects.create(user=self.user)

    def test_create_user_profile(self):
        self.assertEqual(self.profile.user.username, "gamma")
        self.assertEqual(self.profile.role, "patron")

    def test_profile_str(self):
        self.assertEqual(str(self.profile), "gamma - patron")


class ApprovedLibrarianEmailTest(TestCase):
    def setUp(self):
        self.email = ApprovedLibrarianEmail.objects.create(email="hello.com")

    def test_create_approved_librarian_email(self):
        self.assertEqual(self.email.email, "hello.com")

    def test_profile_str(self):
        self.assertEqual(str(self.email), "hello.com")
