from django.shortcuts import render, redirect
from django.contrib.auth.models import Group
from .models import Book, UserLibrary, Profile, ApprovedLibrarianEmail
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from .forms import CustomUserCreationForm

def home(request):
    return render(request, 'library/home.html')

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
            return redirect('my_library')
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
        title = request.POST.get('title')
        author = request.POST.get('author')
        if title and author:
            Book.objects.create(title=title, author=author)
            return redirect('librarian_dashboard')

    return render(request, 'library/librarian_dashboard.html', {'books': books})