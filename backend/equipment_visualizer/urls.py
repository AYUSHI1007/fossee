from django.contrib import admin
from django.urls import path, include, re_path
from equipment_api import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('equipment_api.urls')),  # API endpoints
    re_path(r'^.*$', views.index),  # all other routes go to React
]
