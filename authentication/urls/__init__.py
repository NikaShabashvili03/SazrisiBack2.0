from django.urls import path, include

urlpatterns = [
    path('user/', include("authentication.urls.user")),
    path('payment/', include("authentication.urls.payment"))
]