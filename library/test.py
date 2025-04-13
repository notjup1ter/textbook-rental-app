from datetime import timedelta
from urllib import response

import freezegun
from django.utils import timezone
from freezegun import freeze_time
from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.test import TestCase, Client, override_settings
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail, Collection, Rental
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile
import shutil
import os

# Create a temporary directory for media files during tests
TEMP_MEDIA_ROOT = tempfile.mkdtemp()

@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
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

class CollectionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="allaa", password="beea")
        self.book = Book.objects.create(title="cjfdcc", author="ddfjdkslad")
        self.collection = Collection.objects.create(title="My best collection", description="good books", user=self.user)

    def test_collection_str(self):
        self.assertEqual(str(self.collection), "My best collection")

    def test_collection_user(self):
        self.assertEqual(self.collection.user, self.user)

class RentalTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(username="hahah", password="loll")
        self.book = Book.objects.create(title="abba", author="kkun")

    def test_rental_str(self):
        re = Rental.objects.create(book=self.book, user=self.user, end_date=timezone.now(), status="expired")
        self.assertEqual(str(re), f"{re.user.username} - {re.book.title} ({re.status})")

    @freeze_time("2025-01-01 12:00:00")
    def test_days_remaining(self):
        re = Rental.objects.create(book=self.book, user=self.user, end_date=timezone.now() + timedelta(hours=2))
        self.assertEqual(re.status, "pending")
        self.assertEqual(re.days_remaining(), 120)
        self.assertFalse(re.is_active())

    @freeze_time("2025-01-01 12:00:00")
    def test_is_active(self):
        re = Rental.objects.create(book=self.book, user=self.user, end_date=timezone.now() + timedelta(minutes=30), status="active")
        self.assertTrue(re.is_active())
        with freeze_time("2025-01-01 13:00:00"):
            self.assertEqual(re.days_remaining(), 0)
            self.assertFalse(re.is_active())


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

        self.user = User.objects.create_user(username="gamma", password="abc")

        self.library = UserLibrary.objects.create(user=self.user)
        self.profile = Profile.objects.create(user=self.user, role="patron")
        self.book = Book.objects.create(title="beta", author="b_author")

    def test_home(self):
        response_code = self.client.get(self.home_url)
        self.assertEqual(response_code.status_code, 200)
        self.assertTemplateUsed(response_code, "library/home.html")
        self.assertContains(response_code, self.home_url)

    def test_explore_library(self):
        response_code = self.client.get(self.explore_library_url)
        self.assertEqual(response_code.status_code, 200)
        self.assertTemplateUsed(response_code, "library/explore_library.html")
        self.assertContains(response_code, self.explore_library_url)
        self.assertContains(response_code, self.book.title)
        self.assertContains(response_code, self.book.author)

    def test_my_library_redirect(self):
        response_code = self.client.get(self.my_library_url)
        self.assertEqual(response_code.status_code, 302)

    def test_my_library_with_login(self):
        self.client.login(username="gamma", password="abc")
        response_code = self.client.get(self.my_library_url)
        self.assertEqual(response_code.status_code, 200)
        self.assertTemplateUsed(response_code, "library/my_library.html")
        self.library.books.add(self.book)
        self.library.save()
        self.assertIn(self.book, self.library.books.all())
        response = self.client.post(self.my_library_url, {'book_id': self.book.id})
        self.assertRedirects(response, self.my_library_url)
        self.library.refresh_from_db()
        self.assertNotIn(self.book, self.library.books.all())

    def test_assign_roles_non_librarian(self):
        self.client.login(username="gamma", password="abc")
        response_code = self.client.get(self.assign_roles_url)
        self.assertEqual(response_code.status_code, 302)
        self.assertRedirects(response_code, self.my_library_url)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.role, "patron")

    def test_assign_roles_librarian(self):
        librarian_user = User.objects.create_user(username='hello', password='world', email='bjayden36@gmail.com')
        Profile.objects.create(user=librarian_user, role='patron')
        self.client.login(username="hello", password="world")
        response_code = self.client.get(self.assign_roles_url)
        self.assertRedirects(response_code, self.librarian_dashboard_url)
        profile = Profile.objects.get(user=librarian_user)
        self.assertEqual(profile.role, "librarian")

    def test_profile_view(self):
        self.client.login(username="gamma", password="abc")
        response_code = self.client.get(self.profile_url)
        self.assertTemplateUsed(response_code, "library/profilepage.html")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def test_file_upload(self):
        # Create a test file
        test_file = SimpleUploadedFile(
            "test.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        
        # Use the test file in your tests
        response = self.client.post('/some/url/', {
            'pdf_file': test_file,
        })