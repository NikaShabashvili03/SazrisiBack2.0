from django.urls import path
from ..views import payment

urlpatterns = [
    # Payment history
    path('list/',          payment.PaymentListView.as_view(),   name='payment-list'),
    path('list/<int:pk>/', payment.PaymentDetailView.as_view(), name='payment-detail'),

    # Initiate BOG payment — returns redirect_url for the frontend
    path('category/<int:categoryId>/pay/', payment.PaymentCategoryPurchaseView.as_view(), name='purchase-category'),

    # BOG webhook — called server-to-server by BOG after payment
    path('bog/callback/', payment.BOGCallbackView.as_view(), name='bog-callback'),

    # Frontend polls this after returning from BOG redirect
    path('status/<str:transaction_id>/', payment.PaymentStatusView.as_view(), name='payment-status'),
]
