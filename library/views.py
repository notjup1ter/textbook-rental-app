from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail, Collection
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from .forms import CustomUserCreationForm, ProfileForm, CollectionForm
from django.http import FileResponse, Http404

def home(request):
    return render(request, 'library/home.html')

def explore_library(request):
    books = Book.objects.all()
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
        'user_collections': user_collections
    })

@login_required(login_url='/library/login/')
def my_library(request):
    user_library, created = UserLibrary.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        book_id = request.POST.get('book_id')
        book = Book.objects.get(id=book_id)
        if request.user.is_authenticated:
            user_library.books.remove(book)
            return redirect('my_library')
    return render(request, 'library/my_library.html', {'books': user_library.books.all()})

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
            # Handle book deletion
            book_id = request.POST.get('book_id')
            book = get_object_or_404(Book, id=book_id)
            book.delete()
            return redirect('librarian_dashboard')
        else:
            # Handle book creation
            title = request.POST.get('title')
            author = request.POST.get('author')
            cover_image = request.FILES.get('cover_image')
            pdf_file = request.FILES.get('pdf_file')
            
            if title and author:
                book = Book(title=title, author=author)
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
        collection = get_object_or_404(Collection, id=collection_id, user=request.user)
        book = get_object_or_404(Book, id=book_id)
        collection.books.add(book)
    return redirect('explore_library')

@login_required
def collection_detail(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    books = collection.books.all()
    
    return render(request, 'library/collection_detail.html', {
        'collection': collection,
        'books': books,
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