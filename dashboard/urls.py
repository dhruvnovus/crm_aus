from django.urls import path
from .views import DashboardSummaryView


urlpatterns = [
    path('dashboard/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]