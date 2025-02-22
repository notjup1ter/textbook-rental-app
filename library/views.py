from django.shortcuts import render

def home(request):
    return render(request, 'library/home.html')

def explore_library(request):
    # You can add logic here to fetch books from the database
    # For now, we'll just pass an empty context
    context = {}
    return render(request, 'library/explore_library.html', context)

def my_library(request):
    context = {}
    return render(request, 'library/my_library.html', context) 