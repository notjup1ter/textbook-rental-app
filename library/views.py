from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail, Collection, Rental, Notification
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from .forms import CustomUserCreationForm, ProfileForm, CollectionForm, BookForm, RentalPaymentForm
from django.http import FileResponse, Http404
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse

#predefined price ranges
PRICE_RANGES = [
    ('under_10', 'Under $10'),
    ('10_to_50', '$10 - $50'),
    ('51_to_100', '$51 - $100'),
    ('over_100', 'Over $100'),
]

def home(request):
    if request.user.is_authenticated:
        theme = request.user.profile.preference
    else:
        theme = request.session.get('theme', 'light')
    return render(request, 'library/home.html', {'theme': theme})

def explore_library(request):
    books = Book.objects.all()
    query  = request.GET.get('q')
    selected_conditions = request.GET.getlist('conditions')
    selected_price_ranges = request.GET.getlist('price_ranges')
    
    if query:
        books = Book.objects.filter(
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

@login_required(login_url='/library/login/')
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
        # Create expiration warning notification if not already created
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
        
        # Create expiration notification
        Notification.objects.create(
            user=request.user,
            message=f"Your rental of {rental.book.title} has expired",
            link=reverse('explore_library')
        )
    
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
            # Set the default role to 'patron'
            Profile.objects.create(user=user, role='patron')
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'library/register.html', {'form': form})

@login_required
def assign_role(request):
    librarian_emails = ["bjayden36@gmail.com", "chankyu2004@gmail.com", "haolinchen203@gmail.com", "xsn5hw@virginia.edu"]
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.user.email in librarian_emails:
        profile.role = 'librarian'
        profile.save()
        return redirect('librarian_dashboard')
    else: 
        profile.role = 'patron'
        profile.save()

    return redirect('my_library')


@login_required
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
            rental_price = request.POST.get('rental_price')
            rental_duration_days = request.POST.get('rental_duration_days')
            condition = request.POST.get('condition')
            cover_image = request.FILES.get('cover_image')
            pdf_file = request.FILES.get('pdf_file')
            
            if title and author:
                book = Book(
                    title=title,
                    author=author,
                    rental_price=rental_price,
                    rental_duration_days=rental_duration_days,
                    condition=condition
                )
                if cover_image:
                    book.cover_image = cover_image
                if pdf_file:
                    book.pdf_file = pdf_file
                book.save()
                return redirect('librarian_dashboard')

    return render(request, 'library/librarian_dashboard.html', {'books': books})

@login_required
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
def collections(request):
    collections = Collection.objects.all()
    user_collections = Collection.objects.filter(user=request.user)
    
    if request.method == 'POST':
        form = CollectionForm(request.POST, request.FILES)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.user = request.user
            collection.save()
            return redirect('collections')
    else:
        form = CollectionForm()
    
    return render(request, 'library/collection_page.html', {
        'collections': collections,
        'user_collections': user_collections,
        'form': form
    })

@login_required
def add_to_collection(request, book_id):
    if request.method == 'POST':
        collection_id = request.POST.get('collection_id')
        if not collection_id:  # If no collection was selected
            return redirect('explore_library')  # Redirect back without doing anything
            
        collection = get_object_or_404(Collection, id=collection_id, user=request.user)
        book = get_object_or_404(Book, id=book_id)
        collection.books.add(book)
    return redirect('explore_library')

@login_required
def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    
    # Get user's library books
    user_library, created = UserLibrary.objects.get_or_create(user=request.user)
    user_library_books = user_library.books.all()
    
    # Filter collection books to only show those in user's library
    viewable_books = collection.books.filter(id__in=user_library_books)
    non_viewable_books = collection.books.exclude(id__in=user_library_books)
    
    return render(request, 'library/collection_detail.html', {
        'collection': collection,
        'viewable_books': viewable_books,
        'non_viewable_books': non_viewable_books,
    })

@login_required
def remove_from_collection(request, collection_id, book_id):
    if request.method == 'POST':
        collection = get_object_or_404(Collection, id=collection_id, user=request.user)
        book = get_object_or_404(Book, id=book_id)
        collection.books.remove(book)
    return redirect('collection_detail', collection_id=collection_id)

@login_required
def view_pdf(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if book.pdf_file:
        try:
            return FileResponse(book.pdf_file.open(), content_type='application/pdf')
        except FileNotFoundError:
            raise Http404()
    else:
        raise Http404("No PDF file found for this book")

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    user_library_books = []
    user_collections = []
    
    if request.user.is_authenticated:
        user_library, created = UserLibrary.objects.get_or_create(user=request.user)
        user_library_books = user_library.books.all()
        user_collections = Collection.objects.filter(user=request.user)
    
    return render(request, 'library/book_detail.html', {
        'book': book,
        'user_library_books': user_library_books,
        'user_collections': user_collections,
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

def toggle_theme(request):
    if request.user.is_authenticated:
        profile = request.user.profile
        profile.preference = 'dark' if profile.preference == 'light' else 'light'
        profile.save()
    else:
        current_theme = request.session.get('theme', 'light')
        request.session['theme'] = 'dark' if current_theme == 'light' else 'light'

    return redirect(request.META.get('HTTP_REFERER', 'home'))

def process_mock_payment(amount, card_number):
    """Mock payment processing - always succeeds if card number ends in even digit"""
    return card_number[-1] in '02468'

@login_required
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
def delete_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id, user=request.user)
    if request.method == 'POST':
        collection.delete()
        messages.success(request, f"Collection '{collection.title}' has been deleted.")
        return redirect('collections')
    return redirect('collection_detail', collection_id=collection_id)