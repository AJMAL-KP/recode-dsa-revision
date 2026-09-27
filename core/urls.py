from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('api/inspect-problem-url/', views.api_inspect_problem_url, name='api_inspect_problem_url'),
    path('api/patterns/search/', views.api_search_patterns, name='api_search_patterns'),
    path('problems/add/', views.add_problem_view, name='add_problem'),
]
