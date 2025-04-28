from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group, User
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail, Collection, Rental, Notification, BookRating
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from .forms import CustomUserCreationForm, ProfileForm, CollectionForm, BookForm, RentalPaymentForm, BookRatingForm
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from functools import wraps
from django.db import IntegrityError
from django.core.exceptions import ValidationError

#predefined price ranges
PRICE_RANGES = [
    ('under_10', 'Under $10'),
    ('10_to_50', '$10 - $50'),
    ('51_to_100', '$51 - $100'),
    ('over_100', 'Over $100'),
]

def prevent_admin_access(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_superuser or request.user.is_staff):
            return render(request, 'library/admin_blocked.html')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@prevent_admin_access
def home(request):
    if request.user.is_authenticated:
        try:
            Profile.objects.get_or_create(user=request.user, defaults={'role': 'patron'})
        except Exception:
            pass
    return render(request, 'library/home.html')

@prevent_admin_access
def explore_library(request):
    # First, get IDs of books in private collections
    private_collection_books = Book.objects.filter(
        collection__is_private=True
    ).values_list('id', flat=True)
    
    # Exclude these books from the main queryset
    books = Book.objects.exclude(id__in=private_collection_books)
    
    query = request.GET.get('q')
    selected_conditions = request.GET.getlist('conditions')
    selected_price_ranges = request.GET.getlist('price_ranges')
    
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        )
    if selected_conditions:
        books = books.filter(condition__in=selected_conditions)
    
    # Filter by price range
    if selected_price_ranges:
        price_Q = Q()
        for price_range in selected_price_ranges:
            if price_range == 'under_10':
                price_Q |= Q(rental_price__lt=10.00)
            elif price_range == '10_to_50':
                price_Q |= Q(rental_price__gte=10, rental_price__lte=50)
            elif price_range == '51_to_100':
                price_Q |= Q(rental_price__gt=50, rental_price__lte=100)
            elif price_range == 'over_100':
                price_Q |= Q(rental_price__gt=100)
        books = books.filter(price_Q)
    
    user_library_books = []
    user_collections = []
    
    if request.user.is_authenticated:
        user_library, created = UserLibrary.objects.get_or_create(user=request.user)
        user_library_books = user_library.books.all()
        user_collections = Collection.objects.filter(user=request.user)
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        book = Book.objects.get(id=book_id)
        if request.user.is_authenticated:
            user_library.books.add(book)
            return redirect('explore_library')
        else:
            return redirect('login')
    
    return render(request, 'library/explore_library.html', {
        'books': books,
        'user_library_books': user_library_books,
        'user_collections': user_collections,
        'query': query,
        'conditions': Book.CONDITION_CHOICES,
        'selected_conditions': selected_conditions,
        'price_ranges': PRICE_RANGES,
        'selected_price_ranges': selected_price_ranges,
    })

@login_required
@prevent_admin_access
def my_library(request):
    user_library, created = UserLibrary.objects.get_or_create(user=request.user)
    current_time = timezone.now()
    
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        if book_id:
            try:
                book = get_object_or_404(Book, id=book_id)
                # Cancel any active rentals for this book
                Rental.objects.filter(
                    user=request.user,
                    book=book,
                    status='active'
                ).update(status='cancelled')
                # Remove book from library
                user_library.books.remove(book)
                # Create notification
                Notification.objects.create(
                    user=request.user,
                    message=f"'{book.title}' has been removed from your library",
                    link=reverse('explore_library')
                )
                messages.success(request, f"'{book.title}' has been removed from your library.")
            except Exception as e:
                messages.error(request, f"Error removing book: {str(e)}")
            return redirect('my_library')
    
    # Check for rentals about to expire (less than 5 minutes remaining)
    nearly_expired_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__gt=current_time,
        end_date__lte=current_time + timedelta(minutes=5)
    )
    
    for rental in nearly_expired_rentals:
        if not Notification.objects.filter(
            user=request.user,
            message__contains=f"Your rental of {rental.book.title} will expire soon",
            created_at__gte=current_time - timedelta(minutes=5)
        ).exists():
            Notification.objects.create(
                user=request.user,
                message=f"Your rental of {rental.book.title} will expire soon!",
                link=reverse('my_library')
            )
            messages.warning(request, f"Your rental of {rental.book.title} will expire soon!")
    
    # Check for expired rentals
    expired_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__lt=current_time
    )
    
    for rental in expired_rentals:
        rental.status = 'expired'
        rental.save()
        user_library.books.remove(rental.book)
        
        Notification.objects.create(
            user=request.user,
            message=f"Your rental of {rental.book.title} has expired",
            link=reverse('explore_library')
        )
        messages.error(request, f"Your rental of {rental.book.title} has expired")
    
    # Get active rentals
    active_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__gte=current_time
    )
    
    # Create a dictionary of book_id: minutes_remaining
    rental_times = {}
    for rental in active_rentals:
        try:
            rental_times[rental.book.id] = rental.days_remaining()
        except (ValueError, TypeError):
            rental_times[rental.book.id] = 0
    
    return render(request, 'library/my_library.html', {
        'books': user_library.books.all(),
        'rental_times': rental_times
    })

def custom_logout(request):
    logout(request)
    return redirect('/accounts/logout/')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.is_superuser or user.is_staff:
                messages.error(request, "Administrator accounts cannot be created through registration.")
                user.delete()
                return redirect('register')
            
            Profile.objects.create(user=user, role='patron')
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'library/register.html', {'form': form})

@login_required
def assign_role(request):
    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'library/admin_blocked.html')

    librarian_emails = ["bjayden36@gmail.com", "chankyu2004@gmail.com", "haolinchen203@gmail.com", "xsn5hw@virginia.edu"]
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    # Only assign role if the profile was just created or doesn't have a role
    if created or not profile.role:
        if request.user.email in librarian_emails:
            profile.role = 'librarian'
            profile.save()
            return redirect('librarian_dashboard')
        else: 
            profile.role = 'patron'
            profile.save()

    # If profile already exists and has a role, redirect based on current role
    if profile.role == 'librarian':
        return redirect('librarian_dashboard')
    return redirect('my_library')


@login_required
@prevent_admin_access
def librarian_dashboard(request):
    if request.user.profile.role != 'librarian':
        return redirect('home')
    
    books = Book.objects.all()

    if request.method == 'POST':
        if 'delete_book' in request.POST:
            book_id = request.POST.get('book_id')
            book = get_object_or_404(Book, id=book_id)
            book.delete()
            return redirect('librarian_dashboard')
        else:
            title = request.POST.get('title')
            author = request.POST.get('author')
            isbn = request.POST.get('isbn')
            description = request.POST.get('description')
            rental_price = request.POST.get('rental_price')
            rental_duration_days = request.POST.get('rental_duration_days')
            condition = request.POST.get('condition')
            cover_image = request.FILES.get('cover_image')
            pdf_file = request.FILES.get('pdf_file')
            
            if title and author and isbn:
                try:
                    book = Book(
                        title=title,
                        author=author,
                        isbn=isbn,
                        description=description,
                        rental_price=rental_price,
                        rental_duration_days=rental_duration_days,
                        condition=condition
                    )
                    if cover_image:
                        book.cover_image = cover_image
                    if pdf_file:
                        book.pdf_file = pdf_file
                    book.save()
                    messages.success(request, f"Book '{title}' added successfully.")
                    return redirect('librarian_dashboard')
                except IntegrityError:
                    messages.error(request, "A book with this ISBN already exists.")
            else:
                messages.error(request, "Title, author, and ISBN are required.")

    return render(request, 'library/librarian_dashboard.html', {'books': books})

@login_required
@prevent_admin_access
def profile(request):
    profile = request.user.profile

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')
    else:
        form = ProfileForm(instance = profile)

    return render(request, "library/profilepage.html", {'form': form, 'profile': profile})

@login_required
@prevent_admin_access
def collections(request):
    # Remove all filtering - show all collections to everyone
    collections = Collection.objects.all().order_by('-id')  # Most recent first
    user_collections = Collection.objects.filter(user=request.user)

    if request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                collection = form.save(commit=False)
                collection.user = request.user
                collection.save()
                
                if form.cleaned_data.get('is_private') and form.cleaned_data.get('allowed_users'):
                    collection.allowed_users.set(form.cleaned_data['allowed_users'])
                
                messages.success(request, "Collection created successfully.")
                return redirect('collections')
            except Exception as e:
                if collection.id:
                    collection.delete()
                messages.error(request, f"Error creating collection: {str(e)}")
    else:
        form = CollectionForm(user=request.user)
    
    return render(request, 'library/collection_page.html', {
        'collections': collections,
        'user_collections': user_collections,
        'form': form
    })

@login_required
def add_to_collection(request, book_id):
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        if not collection_id:
            return redirect('explore_library')
            
        collection = get_object_or_404(Collection, id=collection_id)
        book = get_object_or_404(Book, id=book_id)

        # Check if user can add items to this collection
        if not collection.can_add_items(request.user):
            messages.error(request, "You don't have permission to add items to this collection.")
            return redirect('explore_library')

        try:
            # Check if book is in another private collection
            if Collection.objects.filter(is_private=True, books=book).exists():
                messages.error(request, "This book is in a private collection and cannot be added to other collections.")
                return redirect('explore_library')

            collection.books.add(book)
            
            # If the collection is private, remove the book from all user libraries
            if collection.is_private:
                UserLibrary.objects.filter(books=book).update(books=None)
                # Create notification for affected users
                affected_users = UserLibrary.objects.filter(books=book).values_list('user', flat=True)
                for user_id in affected_users:
                    Notification.objects.create(
                        user_id=user_id,
                        message=f"'{book.title}' has been moved to a private collection and is no longer available.",
                        link=reverse('explore_library')
                    )
            
            messages.success(request, f"Book added to collection '{collection.title}'")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('explore_library')

@login_required
def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    user_library, created = UserLibrary.objects.get_or_create(user=request.user)
    user_library_books = user_library.books.all()
    
    if request.method == 'POST':
        if 'request_access' in request.POST and request.user.profile.role == 'patron':
            collection.access_requests.add(request.user)
            messages.success(request, f"Access request sent for collection '{collection.title}'")
            # Notify all librarians about the access request
            librarians = User.objects.filter(profile__role='librarian')
            for librarian in librarians:
                Notification.objects.create(
                    user=librarian,
                    message=f"{request.user.username} has requested access to collection '{collection.title}'",
                    link=reverse('collection_detail', args=[collection.id])
                )
            return redirect('collections')
        elif request.user.profile.role == 'librarian':
            action = request.POST.get('action')
            user_id = request.POST.get('user_id')
            
            if action == 'remove_user' and user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                    collection.allowed_users.remove(target_user)
                    Notification.objects.create(
                        user=target_user,
                        message=f"Your access to collection '{collection.title}' has been removed",
                        link=reverse('collections')
                    )
                    messages.success(request, f"Access removed for {target_user.username}")
                except User.DoesNotExist:
                    messages.error(request, "User not found")
                return redirect('collection_detail', collection_id=collection_id)
            
            elif action == 'add_user' and user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                    collection.allowed_users.add(target_user)
                    collection.access_requests.remove(target_user)
                    Notification.objects.create(
                        user=target_user,
                        message=f"You have been granted access to collection '{collection.title}'",
                        link=reverse('collection_detail', args=[collection.id])
                    )
                    messages.success(request, f"Access granted to {target_user.username}")
                except User.DoesNotExist:
                    messages.error(request, "User not found")
                return redirect('collection_detail', collection_id=collection_id)
            
            elif action == 'reject_request' and user_id:
                try:
                    target_user = User.objects.get(id=user_id)
                    collection.access_requests.remove(target_user)
                    Notification.objects.create(
                        user=target_user,
                        message=f"Your access request for collection '{collection.title}' has been rejected",
                        link=reverse('collections')
                    )
                    messages.success(request, f"Access request from {target_user.username} has been rejected")
                except User.DoesNotExist:
                    messages.error(request, "User not found")
                return redirect('collection_detail', collection_id=collection_id)

    # Determine if the user can view the collection's contents
    can_view_contents = (
        not collection.is_private or
        request.user == collection.user or
        request.user in collection.allowed_users.all() or
        request.user.profile.role == 'librarian'
    )

    # Determine if the user can add items
    can_add_items = collection.can_add_items(request.user)

    # Check if user has already requested access
    has_requested_access = request.user in collection.access_requests.all()

    context = {
        'collection': collection,
        'can_view_contents': can_view_contents,
        'can_add_items': can_add_items,
        'has_requested_access': has_requested_access,
        'is_owner': request.user == collection.user,
        'is_librarian': request.user.profile.role == 'librarian',
    }

    if can_view_contents:
        context.update({
            'viewable_books': collection.books.filter(id__in=user_library_books),
            'non_viewable_books': collection.books.exclude(id__in=user_library_books),
        })

    # Allow all librarians to manage private collections
    if request.user.profile.role == 'librarian' and collection.is_private:
        context['available_users'] = User.objects.filter(profile__role='patron').exclude(
            id__in=collection.allowed_users.values_list('id', flat=True)
        )
        context['access_requests'] = collection.access_requests.all()
        context['current_allowed_users'] = collection.allowed_users.all()

    return render(request, 'library/collection_detail.html', context)

@login_required
def remove_from_collection(request, collection_id, book_id):
    if request.method == 'POST':
        # Allow both collection owners and librarians to remove books
        if request.user.profile.role == 'librarian':
            collection = get_object_or_404(Collection, id=collection_id)
        else:
            collection = get_object_or_404(Collection, id=collection_id, user=request.user)
            
        book = get_object_or_404(Book, id=book_id)
        collection.books.remove(book)
        
        # If this was a private collection and the book is no longer in any private collections,
        # create a notification to inform users it's available again
        if collection.is_private and not Collection.objects.filter(is_private=True, books=book).exists():
            Notification.objects.create(
                user=request.user,
                message=f"'{book.title}' is now available in the public library.",
                link=reverse('explore_library')
            )
            
        # Add notification for collection owner if a librarian removed the book
        if request.user.profile.role == 'librarian' and collection.user != request.user:
            Notification.objects.create(
                user=collection.user,
                message=f"A librarian has removed '{book.title}' from your collection '{collection.title}'",
                link=reverse('collection_detail', args=[collection.id])
            )
            
    return redirect('collection_detail', collection_id=collection_id)

@login_required
def view_pdf(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if book.pdf_file:
        try:
            # Open the file in binary mode
            response = FileResponse(
                book.pdf_file.open('rb'),
                as_attachment=True,  # This forces download
                filename=f"{book.title}.pdf"  # Set the download filename
            )
            # Set additional headers to force download
            response['Content-Type'] = 'application/force-download'
            response['Content-Disposition'] = f'attachment; filename="{book.title}.pdf"'
            response['X-Sendfile'] = book.pdf_file.name
            return response
        except FileNotFoundError:
            raise Http404()
    else:
        raise Http404("No PDF file found for this book")

def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user_library_books = []
    user_collections = []
    user_rating = None
    rating_form = None
    
    if request.user.is_authenticated:
        user_library, created = UserLibrary.objects.get_or_create(user=request.user)
        user_library_books = user_library.books.all()
        user_collections = Collection.objects.filter(user=request.user)
        user_rating = BookRating.objects.filter(book=book, user=request.user).first()
        
        if request.method == 'POST':
            if user_rating:
                rating_form = BookRatingForm(request.POST, instance=user_rating)
            else:
                rating_form = BookRatingForm(request.POST)
            
            if rating_form.is_valid():
                rating = rating_form.save(commit=False)
                rating.book = book
                rating.user = request.user
                rating.save()
                messages.success(request, "Your rating has been saved.")
                return redirect('book_detail', book_id=book_id)
        else:
            rating_form = BookRatingForm(instance=user_rating)
    
    # Get all ratings for the book
    ratings = book.bookrating_set.all().order_by('-created_at')
    
    return render(request, 'library/book_detail.html', {
        'book': book,
        'user_library_books': user_library_books,
        'user_collections': user_collections,
        'rating_form': rating_form,
        'user_rating': user_rating,
        'ratings': ratings,
    })

@login_required
def edit_book(request, book_id):
    if request.user.profile.role != 'librarian':
        return redirect('home')
        
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            try:
                book = form.save()
                messages.success(request, f"'{book.title}' has been updated successfully.")
                return redirect('librarian_dashboard')
            except Exception as e:
                messages.error(request, f"Error updating book: {str(e)}")
    else:
        form = BookForm(instance=book)
    
    return render(request, 'library/edit_book.html', {
        'form': form,
        'book': book
    })

def process_mock_payment(amount, card_number):
    """Mock payment processing - always succeeds if card number ends in even digit"""
    return card_number[-1] in '02468'

@login_required
@prevent_admin_access
def rent_book(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    current_time = timezone.now()
    
    # Check for existing rental
    existing_rental = Rental.objects.filter(
        user=request.user,
        book=book,
        status='active',
        end_date__gte=current_time
    ).first()
    
    if existing_rental:
        messages.warning(request, "You already have an active rental for this book.")
        return redirect('book_detail', book_id=book_id)

    if request.method == 'POST':
        form = RentalPaymentForm(request.POST)
        if form.is_valid():
            payment_successful = process_mock_payment(book.rental_price, form.cleaned_data['card_number'])
            
            if payment_successful:
                # Create rental
                rental = Rental.objects.create(
                    user=request.user,
                    book=book,
                    start_date=current_time,
                    end_date=current_time + timedelta(minutes=book.rental_duration_days),
                    status='active',
                    payment_id=f"MOCK_{current_time.timestamp()}"
                )
                
                # Add book to library
                user_library, _ = UserLibrary.objects.get_or_create(user=request.user)
                user_library.books.add(book)
                
                # Create success notification
                Notification.objects.create(
                    user=request.user,
                    message=f"Successfully rented {book.title} for {book.rental_duration_days} minutes",
                    link=reverse('my_library')
                )
                
                messages.success(request, f"Successfully rented {book.title} for {book.rental_duration_days} minutes!")
                return redirect('my_library')
            else:
                # Create failure notification
                Notification.objects.create(
                    user=request.user,
                    message=f"Payment failed for {book.title}. Please try again.",
                    link=reverse('rent_book', args=[book.id])
                )
                messages.error(request, "Payment failed. Please try again.")
    else:
        form = RentalPaymentForm()
    
    return render(request, 'library/rent_book.html', {
        'form': form,
        'book': book
    })

@login_required
@prevent_admin_access
def my_rentals(request):
    active_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__gte=timezone.now().date()
    )
    expired_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__lt=timezone.now().date()
    )
    
    # Update expired rentals
    for rental in expired_rentals:
        rental.status = 'expired'
        rental.save()
        # Remove book from user's library
        user_library = UserLibrary.objects.get(user=request.user)
        user_library.books.remove(rental.book)
    
    return render(request, 'library/my_rentals.html', {
        'active_rentals': active_rentals,
        'expired_rentals': expired_rentals
    })

@login_required
@prevent_admin_access
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    
    # Allow deletion if user is either:
    # 1. The collection owner
    # 2. A librarian (can delete any collection)
    if request.user.profile.role == 'librarian' or collection.user == request.user:
        try:
            collection_title = collection.title
            collection.delete()
            
            # Create notification for collection owner if deleted by librarian
            if request.user.profile.role == 'librarian' and collection.user != request.user:
                Notification.objects.create(
                    user=collection.user,
                    message=f"Your collection '{collection_title}' has been deleted by a librarian",
                    link=reverse('collections')
                )
            
            messages.success(request, f"Collection '{collection_title}' has been deleted.")
        except Exception as e:
            messages.error(request, f"Error deleting collection: {str(e)}")
    else:
        messages.error(request, "You don't have permission to delete this collection.")
    
    return redirect('collections')

@login_required
@prevent_admin_access
def manage_users(request):
    if request.user.profile.role != 'librarian':
        messages.error(request, "You don't have permission to access this page.")
        return redirect('home')
    
    users = User.objects.all()
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        
        if user_id and action:
            try:
                target_user = User.objects.get(id=user_id)
                profile = Profile.objects.get(user=target_user)
                
                if action == 'promote':
                    profile.role = 'librarian'
                    profile.save()
                    # Force refresh from database
                    profile.refresh_from_db()
                    if profile.role == 'librarian':
                        messages.success(request, f"{target_user.username} has been promoted to librarian.")
                    else:
                        messages.error(request, f"Role update failed. Current role: {profile.role}")
                
                elif action == 'demote':
                    profile.role = 'patron'
                    profile.save()
                    # Force refresh from database
                    profile.refresh_from_db()
                    if profile.role == 'patron':
                        messages.success(request, f"{target_user.username} has been demoted to patron.")
                    else:
                        messages.error(request, f"Role update failed. Current role: {profile.role}")
                
            except User.DoesNotExist:
                messages.error(request, f"User with ID {user_id} not found.")
            except Profile.DoesNotExist:
                messages.error(request, f"Profile for user with ID {user_id} not found.")
            except Exception as e:
                messages.error(request, f"Error updating role: {str(e)}")
    
    # Ensure we get fresh data after any updates
    users = User.objects.select_related('profile').all()
    return render(request, 'library/manage_users.html', {'users': users})

@login_required
def mark_notification_read(request, notification_id):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)