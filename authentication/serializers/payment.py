from ..models import Payment
from rest_framework import serializers




class PaymentSerializer(serializers.ModelSerializer):
    category_title = serializers.CharField(source='category.title', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'category', 'category_title', 'amount', 'currency', 'transaction_id', 'description', 'created_at', 'updated_at']
        read_only_fields = ['transaction_id', 'created_at', 'updated_at']