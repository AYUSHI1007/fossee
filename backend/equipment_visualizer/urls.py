from django.contrib import admin
from django.urls import path, include
from equipment_api.views import index  # import the view we just created

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('equipment_api.urls')),  # your existing API routes
    path('', index),  # serve React frontend at root
]
