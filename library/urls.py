from django.urls import path
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),
    path('explore/', views.explore_library, name='explore_library'),
    path('my-library/', views.my_library, name='my_library'),
    path('librarian/', views.librarian_dashboard, name='librarian_dashboard'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('redirect/', views.assign_role, name='redirect'),
    path('profile/', views.profile, name='profile'),
    path('change-password/', 
        login_required(auth_views.PasswordChangeView.as_view(
            template_name='library/change_password.html',
            success_url='/library/change-password-done/'
        )), 
        name='change_password'),
    path('change-password-done/', 
        login_required(auth_views.PasswordChangeDoneView.as_view(
            template_name='library/change_password_done.html'
        )),
        name='password_change_done'),
] 