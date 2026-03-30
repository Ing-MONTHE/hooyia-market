"""
PayUnitService — Intégration PayUnit V2 (Checkout API)
======================================================

Flux complet :
  1. initialize()        → crée la session checkout PayUnit, retourne redirect URL
  2. verify()            → vérifie le statut via checkout_ID
  3. confirmer_paiement() → marque REUSSI + FSM commande.confirmer()
  4. echouer_paiement()  → marque ECHOUE

Endpoints V2 :
  POST /api/gateway/checkout/initialize  → crée la session, retourne data.redirect
  GET  /api/gateway/checkout/status/{checkout_ID} → statut PENDING|SUCCESS|FAILED|CANCELLED

Authentification (HTTP Basic Auth) :
  Authorization: Basic Base64(api_user:api_password)
  x-api-key: application_token
  mode: live | test

Variables .env requises :
  PAYUNIT_API_USER       → identifiant API
  PAYUNIT_API_PASSWORD   → mot de passe API
  PAYUNIT_APP_TOKEN      → token de l'application (sandbox ou live)
  PAYUNIT_MODE           → test | live
  SITE_URL               → URL publique du site (ex: https://hooyia.com)
"""

import base64
import logging
import requests

from django.conf import settings
from django.utils import timezone

from .models import Paiement

logger = logging.getLogger(__name__)

# URL de base de l'API PayUnit
PAYUNIT_BASE_URL = "https://gateway.payunit.net"


class PayUnitError(Exception):
    """Exception levée quand l'API PayUnit retourne une erreur."""

    pass


class PayUnitService:
    """
    Interface Python vers l'API Checkout PayUnit V2.
    Toutes les méthodes sont statiques — pas d'état interne.
    """

    # ──────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _headers():
        """
        Construit les headers HTTP requis par PayUnit V2.
        - Authorization : HTTP Basic Auth encodé en Base64
        - x-api-key     : token de l'application
        - mode          : live ou test
        """
        api_user = getattr(settings, "PAYUNIT_API_USER", "")
        api_password = getattr(settings, "PAYUNIT_API_PASSWORD", "")
        app_token = getattr(settings, "PAYUNIT_APP_TOKEN", "")
        mode = getattr(settings, "PAYUNIT_MODE", "test")

        credentials = base64.b64encode(
            f"{api_user}:{api_password}".encode("utf-8")
        ).decode("utf-8")

        return {
            "Authorization": f"Basic {credentials}",
            "x-api-key": app_token,
            "mode": mode,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _is_mock():
        """
        Retourne True si le mode mock doit être activé.
        Cas : PAYUNIT_MOCK=True, token absent, ou SITE_URL en localhost.
        """
        app_token = getattr(settings, "PAYUNIT_APP_TOKEN", "")
        site_url = getattr(settings, "SITE_URL", "")

        return (
            getattr(settings, "PAYUNIT_MOCK", False)
            or not app_token
            or app_token == "your_sandbox_token_here"
            or not site_url
            or "localhost" in site_url
            or "127.0.0.1" in site_url
        )

    @staticmethod
    def _build_items(commande):
        """
        Construit le tableau `items` requis par l'API V2.
        Chaque ligne de commande devient un item avec :
          - price_description.unit_amount : prix unitaire (int)
          - product_description.name      : nom du produit (snapshot)
          - product_description.image_url : image publique HTTPS
          - quantity                       : quantité commandée
        """
        items = []
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")

        for ligne in commande.lignes.all():
            # Récupère l'image du produit si disponible, sinon image par défaut
            image_url = f"{site_url}/static/img/product_default.png"
            if (
                hasattr(ligne, "produit")
                and ligne.produit
                and ligne.produit.images.exists()
            ):
                try:
                    image_url = f"{site_url}{ligne.produit.images.first().image.url}"
                except Exception:
                    pass  # Garde l'image par défaut

            items.append(
                {
                    "price_description": {
                        "unit_amount": int(
                            ligne.prix_unitaire
                        ),  # montant entier (FCFA)
                    },
                    "product_description": {
                        "name": ligne.produit_nom,  # snapshot du nom
                        "image_url": image_url,  # doit être HTTPS en prod
                        "about_product": f"Ref: {commande.reference_courte}",
                    },
                    "quantity": ligne.quantite,
                }
            )

        # Sécurité : si la commande n'a pas de lignes, on crée un item générique
        if not items:
            items.append(
                {
                    "price_description": {
                        "unit_amount": int(commande.montant_total),
                    },
                    "product_description": {
                        "name": f"Commande #{commande.reference_courte}",
                        "image_url": f"{site_url}/static/img/product_default.png",
                        "about_product": "HooYia Market",
                    },
                    "quantity": 1,
                }
            )

        return items

    # ──────────────────────────────────────────────────────────────
    # Méthodes publiques
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def initialize(paiement, request):
        """
        Initialise une session de paiement Checkout PayUnit V2.

        Args:
            paiement : instance Paiement (liée à une Commande)
            request  : HttpRequest Django (utilisé uniquement en mode mock)

        Returns:
            dict : {
                'payment_url'    : str  ← URL de redirection vers PayUnit
                'checkout_id'    : str  ← ID de la session checkout (pour verify)
                'transaction_id' : str  ← référence interne (purchaseRef)
            }

        Raises:
            PayUnitError : si l'API retourne une erreur ou est injoignable
        """
        commande = paiement.commande
        client = commande.client

        # ── Mode MOCK (dev local ou token absent) ──────────────────────────
        if PayUnitService._is_mock():
            import uuid as _uuid

            ref_mock = f"pu_mock_{str(_uuid.uuid4())[:8]}"
            mock_url = request.build_absolute_uri(
                f"/commandes/paiement/mock/?ref={commande.reference}&trx={ref_mock}"
            )
            # Stocke la référence mock comme checkout_id
            paiement.reference_externe = ref_mock
            paiement.authorization_url = mock_url
            paiement.save(update_fields=["reference_externe", "authorization_url"])

            logger.warning(
                f"[PayUnit MOCK] Commande #{commande.reference_courte} | Ref: {ref_mock}"
            )
            return {
                "payment_url": mock_url,
                "checkout_id": ref_mock,
                "transaction_id": ref_mock,
            }

        # ── URLs de retour (doivent être publiques et HTTPS) ───────────────
        site_url = getattr(settings, "SITE_URL", "").rstrip("/")
        success_url = f"{site_url}/commandes/paiement/retour/?ref={commande.reference}&status=success"
        cancel_url = f"{site_url}/commandes/paiement/retour/?ref={commande.reference}&status=cancel"
        notify_url = f"{site_url}/api/commandes/webhook/payunit/"

        # ── Payload V2 ─────────────────────────────────────────────────────
        # Champs obligatoires selon la doc V2 :
        # total_amount, transaction_id, mode, currency,
        # success_url, cancel_url, items, meta
        payload = {
            "total_amount": int(paiement.montant),  # montant entier en FCFA
            "transaction_id": str(commande.reference),  # référence unique interne
            "mode": "payment",  # toujours 'payment'
            "currency": "XAF",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "notify_url": notify_url,  # webhook (optionnel mais requis pour nous)
            "payment_country": "CM",  # affiche uniquement les opérateurs CM
            "items": PayUnitService._build_items(commande),
            "meta": {
                "phone_number_collection": True,  # PayUnit affiche le champ téléphone
                "address_collection": False,  # on gère l'adresse en interne
            },
        }

        logger.info(
            f"[PayUnit] initialize — Commande #{commande.reference_courte} "
            f"| Montant: {paiement.montant} XAF"
        )

        # ── Appel API PayUnit ──────────────────────────────────────────────
        try:
            response = requests.post(
                f"{PAYUNIT_BASE_URL}/api/gateway/checkout/initialize",
                json=payload,
                headers=PayUnitService._headers(),
                timeout=15,
            )
            data = response.json()
        except requests.Timeout:
            logger.error("[PayUnit] initialize — Timeout")
            raise PayUnitError(
                "Le service de paiement est temporairement indisponible. "
                "Réessaie dans quelques instants."
            )
        except requests.RequestException as e:
            logger.error(f"[PayUnit] initialize — Erreur réseau : {e}")
            raise PayUnitError("Impossible de contacter le service de paiement.")

        # ── Gestion des erreurs HTTP ────────────────────────────────────────
        if response.status_code not in (200, 201):
            message = data.get("message", data.get("error", "Erreur PayUnit inconnue"))
            logger.error(
                f"[PayUnit] initialize — Erreur {response.status_code} : {message}"
            )
            raise PayUnitError(f"Erreur paiement : {message}")

        # ── Extraction de la réponse V2 ─────────────────────────────────────
        # Réponse V2 : { "status": "SUCCESS", "data": { "redirect": "https://..." } }
        result_data = data.get("data", {})
        payment_url = result_data.get("redirect", "")  # V2 → clé "redirect"
        checkout_id = (
            payment_url.split("/")[-1] if payment_url else ""
        )  # extrait l'ID depuis l'URL

        if not payment_url:
            logger.error(f"[PayUnit] initialize — Pas d'URL dans la réponse : {data}")
            raise PayUnitError("PayUnit n'a pas retourné d'URL de paiement.")

        # ── Sauvegarde ──────────────────────────────────────────────────────
        # reference_externe = checkout_id (utilisé pour vérifier le statut)
        # authorization_url = URL de redirection vers PayUnit
        paiement.reference_externe = checkout_id or str(commande.reference)
        paiement.authorization_url = payment_url
        paiement.save(update_fields=["reference_externe", "authorization_url"])

        logger.info(
            f"[PayUnit] initialize — OK | checkout_id: {checkout_id} | URL: {payment_url}"
        )

        return {
            "payment_url": payment_url,
            "checkout_id": checkout_id,
            "transaction_id": str(commande.reference),
        }

    @staticmethod
    def verify(checkout_id):
        """
        Vérifie le statut d'une session checkout auprès de PayUnit V2.

        Args:
            checkout_id : str — ID de la session checkout (ex: PU_payment_xxx)

        Returns:
            dict : {
                'status'      : str  ← 'SUCCESS', 'FAILED', 'PENDING', 'CANCELLED'
                'amount'      : int
                'checkout_id' : str
            }

        Raises:
            PayUnitError : si l'API retourne une erreur
        """
        try:
            response = requests.get(
                f"{PAYUNIT_BASE_URL}/api/gateway/checkout/status/{checkout_id}",
                headers=PayUnitService._headers(),
                timeout=10,
            )
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"[PayUnit] verify — Erreur réseau : {e}")
            raise PayUnitError("Impossible de vérifier le paiement.")

        if response.status_code != 200:
            raise PayUnitError(data.get("message", "Erreur vérification PayUnit"))

        # Réponse V2 : data.status = PENDING | SUCCESS | FAILED | CANCELLED
        result_data = data.get("data", {})
        status = result_data.get("status", "PENDING")
        amount = result_data.get("total_amount", 0)

        logger.info(f"[PayUnit] verify — checkout_id: {checkout_id} | status: {status}")

        return {
            "status": status,
            "amount": amount,
            "checkout_id": checkout_id,
        }

    @staticmethod
    def confirmer_paiement(paiement):
        """
        Marque le paiement REUSSI et confirme la commande via FSM.
        Appelé par le webhook après notification PayUnit (status = SUCCESS).
        Vide également le panier du client.
        """
        commande = paiement.commande

        paiement.statut = Paiement.StatutPaiement.REUSSI
        paiement.date_paiement = timezone.now()
        paiement.save(update_fields=["statut", "date_paiement"])

        # Transition FSM : EN_ATTENTE → CONFIRMEE
        commande.confirmer()
        commande.save()

        # Vider le panier maintenant que le paiement est confirmé
        try:
            panier = commande.client.panier
            if not panier.est_vide:
                panier.vider()
        except Exception:
            pass  # Panier déjà vide ou inexistant

        logger.info(
            f"[PayUnit] Paiement confirmé | Commande #{commande.reference_courte} "
            f"| checkout_id: {paiement.reference_externe}"
        )

    @staticmethod
    def echouer_paiement(paiement):
        """
        Marque le paiement ECHOUE.
        La commande reste EN_ATTENTE — le client peut retenter.
        """
        paiement.statut = Paiement.StatutPaiement.ECHOUE
        paiement.save(update_fields=["statut"])

        logger.warning(
            f"[PayUnit] Paiement échoué | Commande #{paiement.commande.reference_courte} "
            f"| checkout_id: {paiement.reference_externe}"
        )
