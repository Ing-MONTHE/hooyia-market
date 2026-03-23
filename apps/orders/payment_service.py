"""
NotchPayService — Service d'intégration NotchPay Mobile Money

Responsabilités :
  1. initialize()  → crée un paiement chez NotchPay, retourne l'authorization_url
  2. verify()      → vérifie le statut d'un paiement (polling ou après webhook)
  3. verify_webhook_signature() → valide qu'un webhook vient bien de NotchPay

Flux complet :
  Client checkout
    → OrderService.create_from_cart()        # commande créée, statut EN_ATTENTE
    → NotchPayService.initialize()           # appel API NotchPay
    → retourne authorization_url
    → client redirigé vers NotchPay
    → client paie sur son téléphone (USSD)
    → NotchPay appelle POST /api/commandes/webhook/notchpay/
    → NotchPayService.verify_webhook_signature()  # sécurité
    → paiement.statut = REUSSI
    → commande.confirmer()                   # email envoyé

Mode sandbox (dev) :
  NOTCHPAY_PUBLIC_KEY=sb.pk.xxx → appels réels à l'API sandbox NotchPay
  Aucun vrai argent n'est débité.

Mode live (prod) :
  NOTCHPAY_PUBLIC_KEY=b.pk.xxx → appels réels, vrais paiements.
"""
import hashlib
import hmac
import logging
import requests

from django.conf import settings
from django.utils import timezone

from .models import Paiement

logger = logging.getLogger(__name__)

# URL de base de l'API NotchPay (définie dans settings.py)
NOTCHPAY_API_URL = getattr(settings, 'NOTCHPAY_API_URL', 'https://api.notchpay.co')


class NotchPayError(Exception):
    """
    Exception levée quand l'API NotchPay retourne une erreur.
    Contient le message d'erreur de NotchPay pour affichage au client.
    """
    pass


class NotchPayService:
    """
    Interface Python vers l'API REST NotchPay.

    Toutes les méthodes sont statiques : pas besoin d'instancier la classe.

    Usage :
      result = NotchPayService.initialize(paiement, request)
      # result = {'authorization_url': 'https://pay.notchpay.co/...', 'reference': 'trx.xxx'}
    """

    # ── Canal NotchPay par mode de paiement ──────────────────
    # Ces codes sont définis par NotchPay dans leur documentation
    CANAUX = {
        'orange_money': 'cm.orange',   # Orange Money Cameroun
        'mtn_momo':     'cm.mtn',      # MTN MoMo Cameroun
    }

    @staticmethod
    def _headers():
        """
        Construit les headers HTTP pour chaque appel API NotchPay.
        La clé publique sert d'authentification (Bearer token).
        """
        return {
            'Authorization': settings.NOTCHPAY_PUBLIC_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    @staticmethod
    def initialize(paiement, request):
        """
        Initialise un paiement chez NotchPay.

        Envoie les détails de la commande à l'API NotchPay qui retourne
        une authorization_url vers laquelle rediriger le client.

        Args:
            paiement : instance Paiement (liée à une Commande)
            request  : HttpRequest Django (pour construire les URLs de callback)

        Returns:
            dict : {
                'authorization_url': str,  ← URL vers laquelle rediriger le client
                'reference': str,          ← référence NotchPay (ex: trx.abc123)
            }

        Raises:
            NotchPayError : si l'API retourne une erreur
        """
        commande = paiement.commande
        client   = commande.client

        # ── URL de callback : où NotchPay redirige après paiement ──
        # Le client arrive ici après avoir payé (succès ou échec)
        callback_url = request.build_absolute_uri(
            f'/commandes/paiement/retour/?ref={commande.reference}'
        )

        # ── URL webhook : où NotchPay envoie la confirmation async ──
        # Appelé en arrière-plan par NotchPay dès que le paiement est traité
        webhook_url = request.build_absolute_uri(
            '/api/commandes/webhook/notchpay/'
        )

        # ── Canal de paiement (cm.orange ou cm.mtn) ──────────────
        canal = NotchPayService.CANAUX.get(paiement.mode, '')

        # ── Corps de la requête NotchPay ──────────────────────────
        payload = {
            'amount':      int(paiement.montant),   # NotchPay attend un entier pour XAF
            'currency':    'XAF',
            'description': f'Commande HooYia #{commande.reference_courte}',
            'reference':   str(commande.reference), # Notre référence interne (UUID)
            'callback':    callback_url,
            'webhook':     webhook_url,
            'customer': {
                'name':  f'{client.prenom} {client.nom}'.strip() or client.username,
                'email': client.email,
                'phone': paiement.telephone_paiement,
            },
            # Force le canal Mobile Money (évite que le client choisisse autre chose)
            'locked_channel': canal,
        }

        logger.info(
            f"NotchPay initialize — Commande #{commande.reference_courte} "
            f"| Montant: {paiement.montant} XAF | Canal: {canal}"
        )

        # ── Mode MOCK (dev local sans vraies clés NotchPay) ──────────────────
        # Activé si la clé commence par "sb.pk.test" ou si NOTCHPAY_MOCK=True.
        # Redirige vers une page locale qui simule la confirmation du paiement.
        cle = getattr(settings, 'NOTCHPAY_PUBLIC_KEY', '')
        is_mock = (
            getattr(settings, 'NOTCHPAY_MOCK', False)
            or cle.startswith('sb.pk.test')
            or not cle
        )

        if is_mock:
            import uuid as _uuid
            ref_mock = f'trx.mock.{str(_uuid.uuid4())[:8]}'
            mock_url = request.build_absolute_uri(
                f'/commandes/paiement/mock/?ref={commande.reference}&trx={ref_mock}'
            )
            paiement.reference_externe = ref_mock
            paiement.authorization_url = mock_url
            paiement.save(update_fields=['reference_externe', 'authorization_url'])
            logger.warning(f"NotchPay MOCK actif — Commande #{commande.reference_courte} | Ref: {ref_mock}")
            return {'authorization_url': mock_url, 'reference': ref_mock}

        # ── Appel API NotchPay (sandbox réel ou production) ──────────────────
        try:
            response = requests.post(
                f'{NOTCHPAY_API_URL}/payments',
                json=payload,
                headers=NotchPayService._headers(),
                timeout=15,  # 15 secondes max
            )
            data = response.json()
        except requests.Timeout:
            logger.error("NotchPay initialize — Timeout")
            raise NotchPayError("Le service de paiement est temporairement indisponible. Réessaie dans quelques instants.")
        except requests.RequestException as e:
            logger.error(f"NotchPay initialize — Erreur réseau : {e}")
            raise NotchPayError("Impossible de contacter le service de paiement.")

        # ── Gestion des erreurs API ───────────────────────────────
        if response.status_code not in (200, 201):
            message = data.get('message', 'Erreur inconnue NotchPay')
            logger.error(f"NotchPay initialize — Erreur {response.status_code} : {message}")
            raise NotchPayError(f"Erreur paiement : {message}")

        # ── Extraction des données utiles ─────────────────────────
        transaction     = data.get('transaction', {})
        authorization_url = data.get('authorization_url', '')
        reference_notchpay = transaction.get('reference', '')

        if not authorization_url:
            raise NotchPayError("NotchPay n'a pas retourné d'URL de paiement.")

        # ── Sauvegarde en base ────────────────────────────────────
        # On stocke la référence et l'URL pour le suivi et le webhook
        paiement.reference_externe = reference_notchpay
        paiement.authorization_url = authorization_url
        paiement.save(update_fields=['reference_externe', 'authorization_url'])

        logger.info(
            f"NotchPay initialize — OK | Référence: {reference_notchpay} "
            f"| URL: {authorization_url}"
        )

        return {
            'authorization_url': authorization_url,
            'reference':         reference_notchpay,
        }

    @staticmethod
    def verify(reference_notchpay):
        """
        Vérifie le statut d'un paiement auprès de l'API NotchPay.

        Utilisé :
          - Dans le webhook pour confirmer avant de valider la commande
          - En polling depuis le frontend si besoin

        Args:
            reference_notchpay : str — référence de transaction NotchPay (ex: trx.abc123)

        Returns:
            dict : {
                'status': str,    ← 'complete', 'failed', 'pending', 'canceled'
                'amount': int,
                'reference': str,
            }

        Raises:
            NotchPayError : si l'API retourne une erreur
        """
        try:
            response = requests.get(
                f'{NOTCHPAY_API_URL}/payments/{reference_notchpay}',
                headers=NotchPayService._headers(),
                timeout=10,
            )
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"NotchPay verify — Erreur réseau : {e}")
            raise NotchPayError("Impossible de vérifier le paiement.")

        if response.status_code != 200:
            raise NotchPayError(data.get('message', 'Erreur vérification NotchPay'))

        transaction = data.get('transaction', {})
        return {
            'status':    transaction.get('status', 'pending'),
            'amount':    transaction.get('amount', 0),
            'reference': transaction.get('reference', ''),
        }

    @staticmethod
    def verify_webhook_signature(payload_bytes, signature_header):
        """
        Vérifie que le webhook vient bien de NotchPay (et non d'un attaquant).

        NotchPay signe chaque webhook avec NOTCHPAY_HASH_KEY via HMAC-SHA256.
        On recalcule la signature et on compare.

        Args:
            payload_bytes    : bytes — corps brut de la requête HTTP
            signature_header : str   — valeur du header 'x-notch-signature'

        Returns:
            bool : True si la signature est valide, False sinon
        """
        hash_key = getattr(settings, 'NOTCHPAY_HASH_KEY', '')

        if not hash_key:
            # En dev sans clé de hachage configurée, on accepte (à ne pas faire en prod)
            logger.warning("NOTCHPAY_HASH_KEY non configuré — vérification webhook désactivée")
            return True

        # Calcul HMAC-SHA256
        expected = hmac.new(
            hash_key.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        # Comparaison sécurisée (résistante aux timing attacks)
        return hmac.compare_digest(expected, signature_header or '')

    @staticmethod
    def confirmer_paiement(paiement):
        """
        Marque le paiement comme réussi et confirme la commande.

        Appelé par la vue webhook après vérification de la signature
        et du statut NotchPay.

        Args:
            paiement : instance Paiement à confirmer
        """
        commande = paiement.commande

        # Mettre le paiement à REUSSI
        paiement.statut       = Paiement.StatutPaiement.REUSSI
        paiement.date_paiement = timezone.now()
        paiement.save(update_fields=['statut', 'date_paiement'])

        # Confirmer la commande via FSM → déclenche signal → email Celery
        commande.confirmer()
        commande.save()

        logger.info(
            f"Paiement confirmé — Commande #{commande.reference_courte} "
            f"| Ref NotchPay: {paiement.reference_externe}"
        )

    @staticmethod
    def echouer_paiement(paiement):
        """
        Marque le paiement comme échoué.

        Appelé par le webhook si NotchPay signale un échec (refus, timeout, annulation).
        La commande reste EN_ATTENTE — le client peut retenter.

        Args:
            paiement : instance Paiement à marquer comme échoué
        """
        paiement.statut = Paiement.StatutPaiement.ECHOUE
        paiement.save(update_fields=['statut'])

        logger.warning(
            f"Paiement échoué — Commande #{paiement.commande.reference_courte} "
            f"| Ref NotchPay: {paiement.reference_externe}"
        )