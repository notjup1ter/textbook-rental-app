from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import Group
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from .forms import CustomUserCreationForm, ProfileForm

def home(request):
    if request.user.is_authenticated:
        theme = request.user.profile.theme_preference
    else:
        theme = request.session.get('theme', 'light')
    return render(request, 'library/home.html', {'theme': theme})

def explore_library(request):
    books = Book.objects.all()
    user_library_books = []
    if request.user.is_authenticated:
        user_library, created = UserLibrary.objects.get_or_create(user=request.user)
        user_library_books = user_library.books.all()
    
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
        'user_library_books': user_library_books
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
            
            if title and author:
                book = Book(title=title, author=author)
                if cover_image:
                    book.cover_image = cover_image
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

def toggle_theme(request):
    if request.user.is_authenticated:
        profile = request.user.profile
        if (profile.prefernece == 'light'):
            profile.theme = 'dark'
        else:
            profile.theme = 'light'
        profile.save()
    else:
        cur = request.session.get('theme', 'light')
        if cur == 'light':
            changed = 'dark'
        else:
            changed = 'light'
        request.session['theme'] = changed

    return redirect('home')