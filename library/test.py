from django.test import TestCase, Client
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail
from django.contrib.auth.models import User
from django.urls import reverse

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


class ViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.home_url = reverse("home")
        self.explore_library_url = reverse("explore_library")
        self.my_library_url = reverse("my_library")
        self.register_library_url = reverse("register")
        self.assign_roles_url = reverse("redirect")
        self.librarian_dashboard_url = reverse("librarian_dashboard")
        self.profile_url = reverse("profile")
        self.user = User.objects.create(username="gamma", password="abc")
        self.library = UserLibrary.objects.create(user=self.user)
        self.profile = Profile.objects.create(user=self.user, role="patron")
        self.book = Book.objects.create(title="beta", author="b_author")

    def test_home(self):
        response_code = self.client.get(self.home_url)
        self.assertEqual(response_code.status_code, 200)
        self.assertTemplateUsed(response_code, "library/home.html")
        self.assertContains(response_code, self.home_url)

    def test_explore(self):
        response_code = self.client.get(self.explore_library_url)
        self.assertEqual(response_code.status_code, 200)
        self.assertTemplateUsed(response_code, "library/explore_library.html")
        self.assertContains(response_code, self.explore_library_url)
        self.assertContains(response_code, self.book.title)
        self.assertContains(response_code, self.book.author)
