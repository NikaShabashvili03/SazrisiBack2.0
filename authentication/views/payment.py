import uuid
import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from ..models import Payment
from ..serializers import PaymentSerializer
from ..services import bog as bog_service
from quiz.models.quiz import Quiz
from quiz.models.category import UserQuizAccess
from imitation_quiz.models.imitation_quiz import ImitationQuiz, UserImitationQuizAccess

logger = logging.getLogger(__name__)


# ── Payment list / detail ─────────────────────────────────────────────────────

class PaymentListView(generics.ListAPIView):
    serializer_class   = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


class PaymentDetailView(generics.RetrieveAPIView):
    serializer_class   = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)


# ── Shared BOG order helper ───────────────────────────────────────────────────

def _initiate_bog_payment(request, payment, title):
    frontend_url = settings.FRONTEND_URL
    user = request.user
    transaction_id = payment.transaction_id

    bog_data = bog_service.create_order(
        amount=float(payment.amount),
        currency=payment.currency,
        external_order_id=transaction_id,
        description=f"Sazrisi – {title}",
        callback_url=f"{settings.BACKEND_URL}/api/v1/payment/bog/callback/",
        success_url=f"{frontend_url}/payment/success?order_id={transaction_id}",
        fail_url=f"{frontend_url}/payment/fail?order_id={transaction_id}",
        buyer_full_name=f"{user.firstname} {user.lastname}".strip() or None,
        buyer_email=getattr(user, 'email', None),
        buyer_phone=getattr(user, 'phone', None),
    )
    return bog_data["id"], bog_data["_links"]["redirect"]["href"]


# ── Initiate Quiz payment ─────────────────────────────────────────────────────

class PaymentQuizPurchaseView(APIView):
    """
    POST /api/v1/payment/quiz/<quizId>/pay/

    Creates a BOG ecommerce order for a paid quiz and returns the redirect URL.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, quizId):
        quiz = get_object_or_404(Quiz, id=quizId)

        if not quiz.is_paid:
            return Response(
                {'error': 'ეს ტესტი უფასოა'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_access = UserQuizAccess.objects.filter(
            user=request.user,
            quiz=quiz,
            expires_at__gt=timezone.now(),
            is_active=True,
        ).exists()

        if existing_access:
            return Response(
                {'error': 'თქვენ უკვე გაქვთ წვდომა ამ ტესტზე'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            quiz=quiz,
            amount=quiz.price,
            currency='GEL',
            description=f"წვდომა ტესტზე: {quiz.title}",
            transaction_id=transaction_id,
            status=Payment.STATUS_PENDING,
        )

        try:
            bog_order_id, redirect_href = _initiate_bog_payment(request, payment, quiz.title)
            payment.bog_order_id = bog_order_id
            payment.save(update_fields=["bog_order_id"])

            return Response({
                'payment_id':     payment.id,
                'transaction_id': payment.transaction_id,
                'bog_order_id':   bog_order_id,
                'redirect_url':   redirect_href,
                'amount':         str(payment.amount),
                'currency':       payment.currency,
            })
        except Exception as exc:
            payment.mark_failed()
            logger.error("BOG order creation failed (quiz): %s", exc)
            return Response(
                {'error': 'გადახდის სისტემასთან კავშირი ვერ დამყარდა. სცადეთ თავიდან.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )


# ── Initiate ImitationQuiz payment ────────────────────────────────────────────

class PaymentImitationQuizPurchaseView(APIView):
    """
    POST /api/v1/payment/imitation-quiz/<quizId>/pay/

    Creates a BOG ecommerce order for a paid imitation quiz and returns the redirect URL.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, quizId):
        quiz = get_object_or_404(ImitationQuiz, id=quizId)

        if not quiz.is_paid:
            return Response(
                {'error': 'ეს გამოცდა უფასოა'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_access = UserImitationQuizAccess.objects.filter(
            user=request.user,
            imitation_quiz=quiz,
            expires_at__gt=timezone.now(),
            is_active=True,
        ).exists()

        if existing_access:
            return Response(
                {'error': 'თქვენ უკვე გაქვთ წვდომა ამ გამოცდაზე'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
        payment = Payment.objects.create(
            user=request.user,
            imitation_quiz=quiz,
            amount=quiz.price,
            currency='GEL',
            description=f"წვდომა გამოცდაზე: {quiz.title}",
            transaction_id=transaction_id,
            status=Payment.STATUS_PENDING,
        )

        try:
            bog_order_id, redirect_href = _initiate_bog_payment(request, payment, quiz.title)
            payment.bog_order_id = bog_order_id
            payment.save(update_fields=["bog_order_id"])

            return Response({
                'payment_id':     payment.id,
                'transaction_id': payment.transaction_id,
                'bog_order_id':   bog_order_id,
                'redirect_url':   redirect_href,
                'amount':         str(payment.amount),
                'currency':       payment.currency,
            })
        except Exception as exc:
            payment.mark_failed()
            logger.error("BOG order creation failed (imitation quiz): %s", exc)
            return Response(
                {'error': 'გადახდის სისტემასთან კავშირი ვერ დამყარდა. სცადეთ თავიდან.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )


# ── BOG Callback (webhook) ────────────────────────────────────────────────────

@method_decorator(csrf_exempt, name='dispatch')
class BOGCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request.body
        signature = request.headers.get("Callback-Signature", "")

        if not settings.DEBUG:
            if not signature or not bog_service.verify_callback_signature(raw_body, signature):
                logger.warning("BOG callback: invalid or missing signature")
                return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("BOG callback: invalid JSON body")
            return Response({"error": "Invalid JSON"}, status=status.HTTP_400_BAD_REQUEST)

        body = payload.get("body") or {}
        bog_order_id = body.get("order_id")
        order_status = (body.get("order_status") or {}).get("key")
        payment_detail = body.get("payment_detail") or {}
        response_code = str(payment_detail.get("code")) if payment_detail.get("code") is not None else None

        logger.info(
            "BOG callback received: order_id=%s status=%s code=%s payload=%s",
            bog_order_id,
            order_status,
            response_code,
            payload,
        )

        if not bog_order_id:
            logger.warning("BOG callback: missing order_id")
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        payment = Payment.objects.filter(bog_order_id=bog_order_id).first()
        if not payment:
            logger.warning("BOG callback: no payment found for order_id=%s", bog_order_id)
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        if order_status == "completed" and response_code == "100":
            if payment.status != Payment.STATUS_COMPLETED:
                payment.mark_completed()
                logger.info("Payment #%s marked completed", payment.id)

        elif order_status in ("rejected", "failed"):
            if payment.status != Payment.STATUS_FAILED:
                payment.mark_failed()
                logger.info("Payment #%s marked failed", payment.id)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)


# ── Payment status (frontend polling) ────────────────────────────────────────

class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, transaction_id):
        payment = get_object_or_404(
            Payment, transaction_id=transaction_id, user=request.user
        )

        if payment.status == Payment.STATUS_PENDING and payment.bog_order_id:
            try:
                bog_data = bog_service.get_order_status(payment.bog_order_id)
                order_status = (bog_data.get("order_status") or {}).get("key")
                payment_detail = bog_data.get("payment_detail") or {}
                response_code = str(payment_detail.get("code")) if payment_detail.get("code") is not None else None

                if order_status == "completed" and response_code == "100":
                    payment.mark_completed()
                elif order_status in ("rejected", "failed"):
                    payment.mark_failed()

            except Exception as exc:
                logger.warning("Could not fetch BOG status for payment #%s: %s", payment.id, exc)

        quiz_access = None
        imitation_access = None

        if payment.quiz:
            quiz_access = UserQuizAccess.objects.filter(
                user=request.user,
                quiz=payment.quiz,
                expires_at__gt=timezone.now(),
                is_active=True,
            ).select_related("quiz__category").first()

        elif payment.imitation_quiz:
            imitation_access = UserImitationQuizAccess.objects.filter(
                user=request.user,
                imitation_quiz=payment.imitation_quiz,
                expires_at__gt=timezone.now(),
                is_active=True,
            ).select_related("imitation_quiz__category").first()

        has_access = bool(quiz_access or imitation_access)
                
        return Response({
            "payment_id": payment.id,
            "transaction_id": payment.transaction_id,
            "status": payment.status,
            "amount": str(payment.amount),
            "currency": payment.currency,

            "quiz_category_id": quiz_access.quiz.category.id if quiz_access else None,
            "imitation_category_id": imitation_access.imitation_quiz.category.id if imitation_access else None,

            "quiz_id": payment.quiz_id,
            "imitation_quiz_id": payment.imitation_quiz_id,
            "has_access": has_access,
        })