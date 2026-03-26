"""
PayUnitService — Service d'intégration PayUnit Mobile Money

Responsabilités :
  1. initialize()          → initialise un paiement, retourne la payment_url
  2. verify()              → vérifie le statut d'un paiement via l'API
  3. confirmer_paiement()  → marque REUSSI + confirme la commande FSM
  4. echouer_paiement()    → marque ECHOUE

Flux complet :
  Client checkout
    → OrderService.create_from_cart()     # commande créée, statut EN_ATTENTE
    → PayUnitService.initialize()         # appel API PayUnit
    → retourne payment_url
    → client redirigé vers page PayUnit   # choisit OM ou MTN + paie via USSD
    → PayUnit redirige vers return_url    # /commandes/paiement/retour/
    → JS polle /api/commandes/<ref>/paiement-statut/ toutes les 3s
    → PayUnit appelle notify_url (webhook) en arrière-plan
    → paiement.statut = REUSSI → commande.confirmer()

Authentification PayUnit (HTTP Basic Auth) :
  Authorization: Basic Base64(api_user:api_password)
  x-api-key:     application_token (sandbox ou live selon PAYUNIT_MODE)

Environnements :
  .env.dev  → PAYUNIT_MODE=test  + PAYUNIT_APP_TOKEN=sand_xxx
  .env.prod → PAYUNIT_MODE=live  + PAYUNIT_APP_TOKEN=live_xxx
"""
import base64
import logging
import requests

from django.conf import settings
from django.utils import timezone

from .models import Paiement

logger = logging.getLogger(__name__)

PAYUNIT_BASE_URL = 'https://gateway.payunit.net'


class PayUnitError(Exception):
    """Exception levée quand l'API PayUnit retourne une erreur."""
    pass


class PayUnitService:
    """
    Interface Python vers l'API REST PayUnit.
    Toutes les méthodes sont statiques.
    """

    @staticmethod
    def _headers():
        """
        Headers HTTP pour chaque appel API PayUnit.
        PayUnit utilise HTTP Basic Auth + x-api-key.
        """
        api_user     = getattr(settings, 'PAYUNIT_API_USER', '')
        api_password = getattr(settings, 'PAYUNIT_API_PASSWORD', '')
        app_token    = getattr(settings, 'PAYUNIT_APP_TOKEN', '')
        mode         = getattr(settings, 'PAYUNIT_MODE', 'test')

        credentials = base64.b64encode(
            f'{api_user}:{api_password}'.encode('utf-8')
        ).decode('utf-8')

        return {
            'Authorization': f'Basic {credentials}',
            'x-api-key':     app_token,
            'mode':          mode,
            'Content-Type':  'application/json',
        }

    @staticmethod
    def _is_mock():
        """Détecte le mode mock (dev sans vraies clés)."""
        app_token = getattr(settings, 'PAYUNIT_APP_TOKEN', '')
        return (
            getattr(settings, 'PAYUNIT_MOCK', False)
            or not app_token
            or app_token == 'your_sandbox_token_here'
        )

    @staticmethod
    def initialize(paiement, request):
        """
        Initialise un paiement chez PayUnit.

        Args:
            paiement : instance Paiement (liée à une Commande)
            request  : HttpRequest Django

        Returns:
            dict : {
                'payment_url':       str,  ← URL vers laquelle rediriger le client
                'authorization_url': str,  ← alias (compatibilité)
                'transaction_id':    str,  ← ID de transaction PayUnit
            }

        Raises:
            PayUnitError : si l'API retourne une erreur
        """
        commande = paiement.commande
        client   = commande.client

        # ── Mode MOCK (dev local) ─────────────────────────────────────────────
        if PayUnitService._is_mock():
            import uuid as _uuid
            ref_mock = f'pu_mock_{str(_uuid.uuid4())[:8]}'
            mock_url = request.build_absolute_uri(
                f'/commandes/paiement/mock/?ref={commande.reference}&trx={ref_mock}'
            )
            paiement.reference_externe = ref_mock
            paiement.authorization_url = mock_url
            paiement.save(update_fields=['reference_externe', 'authorization_url'])
            logger.warning(
                f"PayUnit MOCK actif — Commande #{commande.reference_courte} "
                f"| Ref: {ref_mock}"
            )
            return {
                'payment_url':       mock_url,
                'authorization_url': mock_url,
                'transaction_id':    ref_mock,
            }

        # ── URLs de retour ────────────────────────────────────────────────────
        # On utilise SITE_URL pour garantir une URL publique.
        # build_absolute_uri() retourne localhost en dev, ce que PayUnit refuse.
        site_url = getattr(settings, 'SITE_URL', '').rstrip('/')

        # Si SITE_URL est localhost → mock automatique
        if not site_url or 'localhost' in site_url or '127.0.0.1' in site_url:
            import uuid as _uuid
            ref_mock = f'pu_mock_{str(_uuid.uuid4())[:8]}'
            mock_url = request.build_absolute_uri(
                f'/commandes/paiement/mock/?ref={commande.reference}&trx={ref_mock}'
            )
            paiement.reference_externe = ref_mock
            paiement.authorization_url = mock_url
            paiement.save(update_fields=['reference_externe', 'authorization_url'])
            logger.warning(
                f"PayUnit MOCK auto (SITE_URL=localhost) — Commande #{commande.reference_courte}"
            )
            return {
                'payment_url':       mock_url,
                'authorization_url': mock_url,
                'transaction_id':    ref_mock,
            }

        return_url     = f'{site_url}/commandes/paiement/retour/?ref={commande.reference}'
        notify_url     = f'{site_url}/api/commandes/webhook/payunit/'
        cancel_url     = f'{site_url}/commandes/passer/'
        success_url    = f'{site_url}/commandes/paiement/retour/?ref={commande.reference}'
        transaction_id = str(commande.reference)

        # ── Corps de la requête ───────────────────────────────────────────────
        payload = {
            'total_amount':   int(paiement.montant),
            'currency':       'XAF',
            'return_url':     return_url,
            'notify_url':     notify_url,
            'cancel_url':     cancel_url,
            'success_url':    success_url,
            'transaction_id': transaction_id,
            'purchaseRef':    transaction_id,
            'mode':           getattr(settings, 'PAYUNIT_MODE', 'test'),
            'description':    f'Commande HooYia #{commande.reference_courte}',
            'name':           f'{client.prenom} {client.nom}'.strip() or client.username,
            'email':          client.email,
            'phone':          paiement.telephone_paiement,
        }

        logger.info(
            f"PayUnit initialize — Commande #{commande.reference_courte} "
            f"| Montant: {paiement.montant} XAF"
        )

        # ── Appel API ─────────────────────────────────────────────────────────
        try:
            response = requests.post(
                f'{PAYUNIT_BASE_URL}/api/gateway/checkout/initialize',
                json=payload,
                headers=PayUnitService._headers(),
                timeout=15,
            )
            data = response.json()
        except requests.Timeout:
            logger.error("PayUnit initialize — Timeout")
            raise PayUnitError(
                "Le service de paiement est temporairement indisponible. "
                "Réessaie dans quelques instants."
            )
        except requests.RequestException as e:
            logger.error(f"PayUnit initialize — Erreur réseau : {e}")
            raise PayUnitError("Impossible de contacter le service de paiement.")

        # ── Gestion des erreurs ───────────────────────────────────────────────
        if response.status_code not in (200, 201):
            message = data.get('message', data.get('error', 'Erreur PayUnit inconnue'))
            logger.error(f"PayUnit initialize — Erreur {response.status_code} : {message}")
            raise PayUnitError(f"Erreur paiement : {message}")

        # ── Extraction ────────────────────────────────────────────────────────
        # PayUnit retourne :
        # { "status": "SUCCESS", "message": "...",
        #   "data": { "payment_url": "...", "transaction_id": "..." } }
        result_data    = data.get('data', data)
        payment_url    = result_data.get('payment_url', '')
        transaction_id = result_data.get('transaction_id', str(commande.reference))

        if not payment_url:
            logger.error(f"PayUnit initialize — Pas d'URL dans la réponse : {data}")
            raise PayUnitError("PayUnit n'a pas retourné d'URL de paiement.")

        # ── Sauvegarde ───────────────────────────────────────────────────────
        paiement.reference_externe = transaction_id
        paiement.authorization_url = payment_url
        paiement.save(update_fields=['reference_externe', 'authorization_url'])

        logger.info(
            f"PayUnit initialize — OK | Transaction: {transaction_id} "
            f"| URL: {payment_url}"
        )

        return {
            'payment_url':       payment_url,
            'authorization_url': payment_url,
            'transaction_id':    transaction_id,
        }

    @staticmethod
    def verify(transaction_id):
        """
        Vérifie le statut d'un paiement auprès de l'API PayUnit.

        Args:
            transaction_id : str — identifiant de transaction PayUnit

        Returns:
            dict : {
                'status':         str,  ← 'SUCCESS', 'FAILED', 'PENDING'
                'amount':         int,
                'transaction_id': str,
            }

        Raises:
            PayUnitError : si l'API retourne une erreur
        """
        try:
            response = requests.get(
                f'{PAYUNIT_BASE_URL}/api/gateway/checkout/status/{transaction_id}',
                headers=PayUnitService._headers(),
                timeout=10,
            )
            data = response.json()
        except requests.RequestException as e:
            logger.error(f"PayUnit verify — Erreur réseau : {e}")
            raise PayUnitError("Impossible de vérifier le paiement.")

        if response.status_code != 200:
            raise PayUnitError(data.get('message', 'Erreur vérification PayUnit'))

        result_data = data.get('data', data)
        return {
            'status':         result_data.get('status', 'PENDING'),
            'amount':         result_data.get('amount', 0),
            'transaction_id': result_data.get('transaction_id', transaction_id),
        }

    @staticmethod
    def confirmer_paiement(paiement):
        """
        Marque le paiement REUSSI et confirme la commande via FSM.
        Appelé par le webhook après notification PayUnit.
        """
        commande = paiement.commande

        paiement.statut        = Paiement.StatutPaiement.REUSSI
        paiement.date_paiement = timezone.now()
        paiement.save(update_fields=['statut', 'date_paiement'])

        commande.confirmer()
        commande.save()

        # ── Vider le panier maintenant que le paiement est confirmé ──
        # On vide seulement ici pour permettre une nouvelle tentative
        # si le paiement avait échoué avant d'arriver à ce point.
        try:
            panier = commande.client.panier
            if not panier.est_vide:
                panier.vider()
        except Exception:
            pass  # Panier déjà vide ou inexistant

        logger.info(
            f"PayUnit — Paiement confirmé | Commande #{commande.reference_courte} "
            f"| Transaction: {paiement.reference_externe}"
        )

    @staticmethod
    def echouer_paiement(paiement):
        """
        Marque le paiement ECHOUE.
        La commande reste EN_ATTENTE — le client peut retenter.
        """
        paiement.statut = Paiement.StatutPaiement.ECHOUE
        paiement.save(update_fields=['statut'])

        logger.warning(
            f"PayUnit — Paiement échoué | Commande #{paiement.commande.reference_courte} "
            f"| Transaction: {paiement.reference_externe}"
        )