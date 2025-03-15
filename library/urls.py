from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('explore/', views.explore_library, name='explore_library'),
    path('my-library/', views.my_library, name='my_library'),
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('redirect/', views.assign_role, name='redirect'),
] 