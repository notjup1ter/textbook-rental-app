from django.urls import path
from . import views

urlpatterns = [
    path('explore/', views.explore_library, name='explore_library'),
    path('my-library/', views.my_library, name='my_library'),
    path('register/', views.register, name='register'),
] 