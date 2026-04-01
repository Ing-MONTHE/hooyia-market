"""
webhook.py — Notifications asynchrones PayUnit V2
Payload V2 : { "data": { "checkout_id": "PU_payment_xxx", "status": "SUCCESS|FAILED|CANCELLED|PENDING" } }
Sécurité : double vérification via PayUnitService.verify() avant d'agir.
"""

import json
import logging

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import Paiement
from .payment_service import PayUnitService, PayUnitError

logger = logging.getLogger(__name__)


class PayUnitWebhookView(APIView):
    """POST /api/commandes/webhook/payunit/ — public, appelé par PayUnit."""

    permission_classes = []
    authentication_classes = []

    def post(self, request):
        # 1. Parser le payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return Response(
                {"erreur": "Payload invalide."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Extraire checkout_id (V2 : data.checkout_id)
        checkout_id = payload.get("data", {}).get("checkout_id", "")
        if not checkout_id:
            logger.warning("[Webhook] checkout_id manquant")
            return Response(
                {"erreur": "checkout_id manquant."}, status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f"[Webhook] Notification | checkout_id: {checkout_id}")

        # 3. Retrouver le paiement via reference_externe = checkout_id
        try:
            paiement = Paiement.objects.select_related("commande").get(
                reference_externe=checkout_id
            )
        except Paiement.DoesNotExist:
            # Retourner 200 pour éviter les retries PayUnit sur des IDs inconnus
            return Response({"message": "Ignoré."}, status=status.HTTP_200_OK)

        # 4. Idempotence — ignorer si déjà traité
        if paiement.statut == Paiement.StatutPaiement.REUSSI:
            return Response({"message": "Déjà traité."}, status=status.HTTP_200_OK)

        # 5. Double vérification auprès de l'API PayUnit
        try:
            result = PayUnitService.verify(checkout_id)
            statut_payunit = result["status"]  # SUCCESS | FAILED | CANCELLED | PENDING
        except PayUnitError as e:
            logger.error(f"[Webhook] Vérification impossible : {e}")
            return Response(
                {"erreur": "Vérification impossible."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # 6. Agir selon le statut confirmé
        if statut_payunit == "SUCCESS":
            PayUnitService.confirmer_paiement(paiement)
            logger.info(f"[Webhook] Paiement confirmé | checkout_id: {checkout_id}")
            return Response(
                {"message": "Paiement confirmé."}, status=status.HTTP_200_OK
            )

        if statut_payunit in ("FAILED", "CANCELLED"):
            PayUnitService.echouer_paiement(paiement)
            logger.warning(
                f"[Webhook] Paiement échoué ({statut_payunit}) | checkout_id: {checkout_id}"
            )
            return Response({"message": "Paiement échoué."}, status=status.HTTP_200_OK)

        # PENDING ou autre — PayUnit retentera
        return Response(
            {"message": f"Statut {statut_payunit} — en attente."},
            status=status.HTTP_200_OK,
        )
