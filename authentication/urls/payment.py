from django.urls import path
from ..views import payment


urlpatterns = [
    path('list/', payment.PaymentListView.as_view(), name='payment-list'),
    path('list/<int:pk>/', payment.PaymentDetailView.as_view(), name='payment-detail'),
    path('category/<int:categoryId>/pay/', payment.PaymentCategoryPurchaseView.as_view(), name='purchase-category'),
]