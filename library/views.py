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
                    book=book,
                    user=request.user,
                    status='active'
                ).update(status='cancelled')
                
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
            return redirect('my_library')
    
    # If role is already assigned, redirect based on role
    if profile.role == 'librarian':
        return redirect('librarian_dashboard')
    else:
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
                        condition=condition,
                        cover_image=cover_image
                    )
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

@prevent_admin_access
def collections(request):
    # Get search query from request
    query = request.GET.get('q', '')
    
    # Base queryset - show all collections for logged-in users, only public ones for anonymous users
    if request.user.is_authenticated:
        collections = Collection.objects.all()
    else:
        collections = Collection.objects.filter(is_private=False)
    
    # Apply search if query exists
    if query:
        collections = collections.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(user__username__icontains=query) |
            Q(books__title__icontains=query)
        ).distinct()
    
    collections = collections.order_by('-id')  # Most recent first
    
    context = {
        'collections': collections,
        'query': query,
    }
    
    # Only add user-specific context if user is authenticated
    if request.user.is_authenticated:
        user_collections = Collection.objects.filter(user=request.user)
        form = CollectionForm(user=request.user)
        context.update({
            'user_collections': user_collections,
            'form': form,
        })

    return render(request, 'library/collection_page.html', context)

@login_required
def add_to_collection(request, book_id):
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        if not collection_id:
            return redirect('explore_library')
            
        collection = get_object_or_404(Collection, id=collection_id)
        book = get_object_or_404(Book, id=book_id)

        # Check permissions
        if request.user.profile.role == 'librarian' or collection.user == request.user:
            try:
                # Check if book is in another private collection
                if Collection.objects.filter(is_private=True, books=book).exists():
                    messages.error(request, "This book is in a private collection and cannot be added to other collections.")
                    return redirect('explore_library')

                collection.books.add(book)
                messages.success(request, f"Book added to collection '{collection.title}'")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "You don't have permission to add books to this collection.")

    return redirect('explore_library')

def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    
    # Initialize user_library_books as empty list for anonymous users
    user_library_books = []
    
    # Get user's library books if authenticated
    if request.user.is_authenticated:
        user_library, created = UserLibrary.objects.get_or_create(user=request.user)
        user_library_books = user_library.books.all()
    
    # Add search functionality
    query = request.GET.get('q', '')
    
    # Determine if the user can view the collection's contents
    can_view_contents = (
        not collection.is_private or  # Public collections are visible to all
        (request.user.is_authenticated and (
            request.user == collection.user or
            request.user in collection.allowed_users.all() or
            request.user.profile.role == 'librarian'
        ))
    )

    context = {
        'collection': collection,
        'can_view_contents': can_view_contents,
        'is_owner': request.user.is_authenticated and request.user == collection.user,
        'is_librarian': request.user.is_authenticated and request.user.profile.role == 'librarian',
        'query': query,
    }

    # Only add request-related context for authenticated users
    if request.user.is_authenticated:
        context['has_requested_access'] = request.user in collection.access_requests.all()

    if can_view_contents:
        books = collection.books.all()
        
        # Apply search if query exists
        if query:
            books = books.filter(
                Q(title__icontains=query) |
                Q(author__icontains=query) |
                Q(description__icontains=query) |
                Q(isbn__icontains=query)
            )
        
        # For authenticated users, separate books into viewable and non-viewable
        if request.user.is_authenticated:
            viewable_books = books.filter(id__in=user_library_books)
            non_viewable_books = books.exclude(id__in=user_library_books)
        else:
            # For anonymous users, all books are non-viewable (they need to register to access)
            viewable_books = []
            non_viewable_books = books
        
        context.update({
            'viewable_books': viewable_books,
            'non_viewable_books': non_viewable_books,
        })

    # Add librarian management context if applicable
    if request.user.is_authenticated and request.user.profile.role == 'librarian' and collection.is_private:
        context.update({
            'available_users': User.objects.filter(profile__role='patron').exclude(
                id__in=collection.allowed_users.values_list('id', flat=True)
            ),
            'access_requests': collection.access_requests.all(),
            'current_allowed_users': collection.allowed_users.all()
        })

    return render(request, 'library/collection_detail.html', context)

@login_required
def remove_from_collection(request, collection_id, book_id):
    if request.method == 'POST':
        collection = get_object_or_404(Collection, id=collection_id)
        book = get_object_or_404(Book, id=book_id)
        
        # Check if user has permission to remove books
        if request.user.profile.role == 'librarian' or collection.user == request.user:
            collection.books.remove(book)
            
            # Create notification for collection owner if a librarian removed the book
            if request.user.profile.role == 'librarian' and collection.user != request.user:
                Notification.objects.create(
                    user=collection.user,
                    message=f"A librarian has removed '{book.title}' from your collection '{collection.title}'",
                    link=reverse('collection_detail', args=[collection.id])
                )
            
            messages.success(request, f"'{book.title}' has been removed from the collection.")
        else:
            messages.error(request, "You don't have permission to remove books from this collection.")
            
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
        status__in=['pending_approval', 'pending', 'active'],
        end_date__gte=current_time
    ).first()
    
    if existing_rental:
        if existing_rental.status == 'pending_approval':
            messages.warning(request, "You already have a pending rental request for this book.")
        else:
            messages.warning(request, "You already have an active rental for this book.")
        return redirect('book_detail', book_id=book_id)

    if request.method == 'POST':
        form = RentalPaymentForm(request.POST)
        if form.is_valid():
            # Create rental with pending_approval status
            rental = Rental.objects.create(
                user=request.user,
                book=book,
                start_date=current_time,
                end_date=current_time + timedelta(minutes=book.rental_duration_days),
                status='pending_approval',
                payment_id=form.cleaned_data['card_number']  # Store the card number for payment processing
            )
            
            # Create a single notification for librarians
            librarians = User.objects.filter(profile__role='librarian')
            for librarian in librarians:
                Notification.objects.create(
                    user=librarian,
                    message=f"New rental request: {request.user.username} wants to rent '{book.title}'",
                    link=reverse('approve_rentals')
                )
            
            messages.success(request, "Your rental request has been submitted and is pending librarian approval.")
            return redirect('my_pending_rentals')
    else:
        form = RentalPaymentForm()
    
    return render(request, 'library/rent_book.html', {
        'form': form,
        'book': book
    })

@login_required
@prevent_admin_access
def my_pending_rentals(request):
    # Get all rentals for the current user
    pending_rentals = Rental.objects.filter(
        user=request.user,
        status='pending_approval'
    ).select_related('book')
    
    active_rentals = Rental.objects.filter(
        user=request.user,
        status='active',
        end_date__gte=timezone.now()
    ).select_related('book')
    
    expired_rentals = Rental.objects.filter(
        user=request.user,
        status__in=['expired', 'cancelled', 'rejected']
    ).select_related('book')
    
    return render(request, 'library/my_pending_rentals.html', {
        'pending_rentals': pending_rentals,
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
def approve_rentals(request):
    if request.user.profile.role != 'librarian':
        messages.error(request, "Only librarians can approve rentals.")
        return redirect('home')
    
    if request.method == 'POST':
        rental_id = request.POST.get('rental_id')
        action = request.POST.get('action')
        
        if rental_id and action:
            rental = get_object_or_404(Rental, id=rental_id)
            
            if action == 'approve':
                # Process payment
                payment_successful = process_mock_payment(rental.book.rental_price, rental.payment_id)
                
                if payment_successful:
                    rental.status = 'active'
                    rental.save()
                    
                    # Add book to user's library
                    user_library, _ = UserLibrary.objects.get_or_create(user=rental.user)
                    user_library.books.add(rental.book)
                    
                    messages.success(request, f"Rental approved for {rental.user.username}")
                else:
                    rental.status = 'cancelled'
                    rental.save()
                    messages.error(request, "Payment processing failed")
            
            elif action == 'reject':
                rental.status = 'rejected'
                rental.save()
                messages.success(request, f"Rental rejected for {rental.user.username}")
    
    pending_rentals = Rental.objects.filter(status='pending_approval').select_related('user', 'book')
    return render(request, 'library/approve_rentals.html', {
        'pending_rentals': pending_rentals
    })