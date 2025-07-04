from ..models import Payment
from ..serializers import (
    PaymentSerializer
)
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
import uuid
from quiz.models.category import Category, UserCategoryAccess

class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)
    


class PaymentCategoryPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, categoryId):
        category = get_object_or_404(Category, id=categoryId)
        
        if not category.is_paid:
            return Response(
                {'error': 'This category is free'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        existing_access = UserCategoryAccess.objects.filter(
            user=request.user,
            category=category,
            expires_at__gt=timezone.now(),
            is_active=True
        ).exists()
        
        if existing_access:
            return Response(
                {'error': 'You already have access to this category'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment
        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            category=category,
            amount=category.price,
            description=f"Purchase access to {category.title}",
            transaction_id=transaction_id
        )

        payment.mark_completed()
        
        return Response({
            'payment_id': payment.id,
            'transaction_id': payment.transaction_id,
            'amount': payment.amount,
            'currency': payment.currency,
        })