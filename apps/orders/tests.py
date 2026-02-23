"""
Tests pour l'app orders.

Couverture :
  - Modèle Commande (création, référence courte, FSM complet)
  - Transitions FSM (cycle légal, transitions interdites)
  - OrderService (create_from_cart, annuler_commande)
  - API Commandes (créer, lister, détail, annuler)

Note importante sur les mocks :
  Les signals orders/signals.py appellent Celery (.delay() / .apply_async()).
  En tests, Celery n'est pas lancé → on mock les tâches pour éviter les erreurs.
  Le décorateur @patch est appliqué au niveau de la méthode de test concernée.
"""
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from unittest.mock import patch

from apps.orders.models import Commande, LigneCommande, Paiement
from apps.orders.services import OrderService
from apps.users.models import CustomUser, AdresseLivraison
from apps.products.models import Produit, Categorie
from apps.cart.services import CartService


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_client(email='client@hooyia.com', username='client'):
    return CustomUser.objects.create_user(
        email=email, username=username, password='Client123!', is_active=True,
    )

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_vendeur():
    return CustomUser.objects.create_user(
        email='vendeur@hooyia.com', username='vendeur',
        password='Vendeur123!', is_active=True, is_vendeur=True,
    )

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_admin():
    return CustomUser.objects.create_user(
        email='admin@hooyia.com', username='admin',
        password='Admin123!', is_active=True, is_admin=True, is_staff=True,
    )

def creer_produit(vendeur, prix=Decimal('50000.00'), stock=10, **kwargs):
    categorie, _ = Categorie.objects.get_or_create(nom='Électronique')
    defaults = {
        'nom': 'Produit Test', 'description': 'Desc',
        'prix': prix, 'stock': stock, 'statut': 'actif',
        'categorie': categorie, 'vendeur': vendeur,
    }
    defaults.update(kwargs)
    return Produit.objects.create(**defaults)

def creer_adresse(utilisateur):
    return AdresseLivraison.objects.create(
        utilisateur=utilisateur,
        nom_complet='Jean Dupont', telephone='699000000',
        adresse='123 Rue Test', ville='Yaoundé',
        region='Centre', pays='Cameroun', is_default=True,
    )

def preparer_panier(utilisateur, vendeur, quantite=2):
    """Prépare un panier avec un produit. Retourne (panier, produit)."""
    produit = creer_produit(vendeur, prix=Decimal('50000.00'), stock=10)
    CartService.add_item(utilisateur.panier, produit.pk, quantite=quantite)
    return utilisateur.panier, produit


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Commande + Machine à États (FSM)
# ═══════════════════════════════════════════════════════════════

class CommandeModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.client_user = creer_client()
        self.adresse     = creer_adresse(self.client_user)

    def _creer_commande(self):
        """Crée une commande minimale en EN_ATTENTE."""
        return Commande.objects.create(
            client=self.client_user,
            montant_total=Decimal('100000.00'),
            adresse_livraison_nom='Jean Dupont',
            adresse_livraison_telephone='699000000',
            adresse_livraison_adresse='123 Rue Test',
            adresse_livraison_ville='Yaoundé',
            adresse_livraison_region='Centre',
            adresse_livraison_pays='Cameroun',
        )

    def test_statut_initial_en_attente(self):
        """Une nouvelle commande est en EN_ATTENTE."""
        commande = self._creer_commande()
        self.assertEqual(commande.statut, Commande.EN_ATTENTE)

    def test_reference_uuid_unique(self):
        """La référence UUID est unique et non vide."""
        c1 = self._creer_commande()
        c2 = self._creer_commande()
        self.assertNotEqual(c1.reference, c2.reference)

    def test_reference_courte_8_chars(self):
        """reference_courte a exactement 8 caractères."""
        commande = self._creer_commande()
        self.assertEqual(len(commande.reference_courte), 8)

    def test_peut_etre_annulee_en_attente(self):
        """peut_etre_annulee est True quand la commande est EN_ATTENTE."""
        commande = self._creer_commande()
        self.assertTrue(commande.peut_etre_annulee)

    # ── Transitions FSM légales ───────────────────────────────

    def test_transition_en_attente_vers_confirmee(self):
        """EN_ATTENTE → CONFIRMEE."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.save()
        self.assertEqual(commande.statut, Commande.CONFIRMEE)

    def test_transition_confirmee_vers_preparation(self):
        """CONFIRMEE → EN_PREPARATION."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.mettre_en_preparation()
        commande.save()
        self.assertEqual(commande.statut, Commande.EN_PREPARATION)

    def test_transition_cycle_complet(self):
        """Cycle complet EN_ATTENTE → CONFIRMEE → EN_PREPARATION → EXPEDIEE → LIVREE."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.mettre_en_preparation()
        commande.expedier()
        commande.livrer()
        commande.save()
        self.assertEqual(commande.statut, Commande.LIVREE)

    def test_annulation_depuis_en_attente(self):
        """Une commande EN_ATTENTE peut être annulée."""
        commande = self._creer_commande()
        commande.annuler()
        commande.save()
        self.assertEqual(commande.statut, Commande.ANNULEE)

    def test_annulation_depuis_confirmee(self):
        """Une commande CONFIRMEE peut être annulée."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.annuler()
        commande.save()
        self.assertEqual(commande.statut, Commande.ANNULEE)

    # ── Transitions FSM interdites ────────────────────────────

    def test_transition_interdite_en_attente_vers_expediee(self):
        """Sauter les étapes (EN_ATTENTE → EXPEDIEE) lève TransitionNotAllowed."""
        commande = self._creer_commande()
        with self.assertRaises(TransitionNotAllowed):
            commande.expedier()

    def test_transition_interdite_en_attente_vers_livree(self):
        """EN_ATTENTE → LIVREE est interdit."""
        commande = self._creer_commande()
        with self.assertRaises(TransitionNotAllowed):
            commande.livrer()

    def test_annulation_impossible_si_livree(self):
        """Une commande LIVREE ne peut pas être annulée."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.mettre_en_preparation()
        commande.expedier()
        commande.livrer()
        commande.save()
        with self.assertRaises(TransitionNotAllowed):
            commande.annuler()

    def test_peut_etre_annulee_false_si_livree(self):
        """peut_etre_annulee est False pour une commande LIVREE."""
        commande = self._creer_commande()
        commande.confirmer()
        commande.mettre_en_preparation()
        commande.expedier()
        commande.livrer()
        commande.save()
        self.assertFalse(commande.peut_etre_annulee)

    def test_peut_etre_annulee_false_si_annulee(self):
        """peut_etre_annulee est False pour une commande déjà ANNULEE."""
        commande = self._creer_commande()
        commande.annuler()
        commande.save()
        self.assertFalse(commande.peut_etre_annulee)


# ═══════════════════════════════════════════════════════════════
# TESTS — OrderService
# ═══════════════════════════════════════════════════════════════

class OrderServiceTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.adresse     = creer_adresse(self.client_user)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_cree_commande_complete(self, mock_email):
        """create_from_cart crée une commande avec ses lignes et son paiement."""
        panier, produit = preparer_panier(self.client_user, self.vendeur, quantite=2)

        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse,
        )

        self.assertEqual(commande.client, self.client_user)
        self.assertEqual(commande.statut, Commande.CONFIRMEE)
        self.assertEqual(commande.montant_total, Decimal('100000.00'))  # 2 × 50000
        self.assertEqual(commande.lignes.count(), 1)

        ligne = commande.lignes.first()
        self.assertEqual(ligne.quantite, 2)
        self.assertEqual(ligne.produit_nom, produit.nom)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_vide_panier(self, mock_email):
        """Après create_from_cart, le panier est vide."""
        panier, _ = preparer_panier(self.client_user, self.vendeur)
        OrderService.create_from_cart(utilisateur=self.client_user, adresse=self.adresse)
        self.assertTrue(panier.est_vide)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_decremente_stock(self, mock_email):
        """Après create_from_cart, le stock est décrémenté."""
        _, produit = preparer_panier(self.client_user, self.vendeur, quantite=3)
        OrderService.create_from_cart(utilisateur=self.client_user, adresse=self.adresse)
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 7)  # 10 - 3

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_cree_paiement(self, mock_email):
        """create_from_cart crée un paiement associé à la commande."""
        preparer_panier(self.client_user, self.vendeur)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        self.assertTrue(hasattr(commande, 'paiement'))
        self.assertEqual(commande.paiement.montant, commande.montant_total)

    def test_create_from_cart_panier_vide(self):
        """create_from_cart avec panier vide lève ValidationError."""
        with self.assertRaises(ValidationError):
            OrderService.create_from_cart(
                utilisateur=self.client_user, adresse=self.adresse
            )

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_stock_insuffisant(self, mock_email):
        """create_from_cart avec stock insuffisant lève ValidationError."""
        produit = creer_produit(self.vendeur, stock=1)
        CartService.add_item(self.client_user.panier, produit.pk, quantite=1)
        # Vide le stock après l'ajout au panier
        produit.stock = 0
        produit.save()
        with self.assertRaises(ValidationError):
            OrderService.create_from_cart(utilisateur=self.client_user, adresse=self.adresse)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_remet_stock(self, mock_email):
        """Annuler une commande remet le stock des produits."""
        _, produit = preparer_panier(self.client_user, self.vendeur, quantite=3)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 7)  # 10 - 3

        OrderService.annuler_commande(commande, self.client_user)
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 10)  # 7 + 3

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_non_proprietaire(self, mock_email):
        """Un autre utilisateur ne peut pas annuler une commande qui ne lui appartient pas."""
        preparer_panier(self.client_user, self.vendeur)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        autre_user = creer_client(email='autre@hooyia.com', username='autre')
        with self.assertRaises(ValidationError):
            OrderService.annuler_commande(commande, autre_user)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_admin(self, mock_email):
        """Un admin peut annuler n'importe quelle commande."""
        preparer_panier(self.client_user, self.vendeur)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        admin = creer_admin()
        commande_annulee = OrderService.annuler_commande(commande, admin)
        self.assertEqual(commande_annulee.statut, Commande.ANNULEE)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Commandes
# ═══════════════════════════════════════════════════════════════

class CommandeAPITest(APITestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.admin       = creer_admin()
        self.adresse     = creer_adresse(self.client_user)

        resp = self.client.post(reverse('token_obtain'), {
            'email': 'client@hooyia.com', 'password': 'Client123!'
        }, format='json')
        self.token_client = resp.data.get('access', '')

        resp_admin = self.client.post(reverse('token_obtain'), {
            'email': 'admin@hooyia.com', 'password': 'Admin123!'
        }, format='json')
        self.token_admin = resp_admin.data.get('access', '')

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_creer_commande(self, mock_email):
        """POST /api/commandes/creer/ crée une commande depuis le panier → 201."""
        preparer_panier(self.client_user, self.vendeur, quantite=2)
        self._auth(self.token_client)
        response = self.client.post(reverse('api_commande_creer'), {
            'adresse_id': self.adresse.pk, 'mode_paiement': 'livraison',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['statut'], Commande.CONFIRMEE)

    def test_creer_commande_panier_vide(self):
        """Créer une commande avec un panier vide → 400."""
        self._auth(self.token_client)
        response = self.client.post(reverse('api_commande_creer'), {
            'adresse_id': self.adresse.pk, 'mode_paiement': 'livraison',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_commande_non_authentifie(self):
        """Créer une commande sans token → 401."""
        response = self.client.post(reverse('api_commande_creer'), {
            'adresse_id': self.adresse.pk,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_lister_commandes_client(self, mock_email):
        """GET /api/commandes/ retourne uniquement les commandes du client connecté."""
        preparer_panier(self.client_user, self.vendeur, quantite=1)
        OrderService.create_from_cart(utilisateur=self.client_user, adresse=self.adresse)
        self._auth(self.token_client)
        response = self.client.get(reverse('api_commandes'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultats = response.data.get('results', response.data)
        self.assertEqual(len(resultats), 1)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_detail_commande(self, mock_email):
        """GET /api/commandes/<id>/ retourne lignes et paiement."""
        preparer_panier(self.client_user, self.vendeur, quantite=1)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        self._auth(self.token_client)
        response = self.client.get(reverse('api_commande_detail', kwargs={'pk': commande.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('lignes',   response.data)
        self.assertIn('paiement', response.data)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_client(self, mock_email):
        """POST /api/commandes/<id>/annuler/ annule la commande du client → 200."""
        preparer_panier(self.client_user, self.vendeur, quantite=1)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        self._auth(self.token_client)
        response = self.client.post(
            reverse('api_commande_annuler', kwargs={'pk': commande.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['commande']['statut'], Commande.ANNULEE)

    def test_commandes_non_authentifie(self):
        """GET /api/commandes/ sans token → 401."""
        self.client.credentials()
        response = self.client.get(reverse('api_commandes'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_client_ne_voit_pas_commandes_autres(self, mock_email):
        """Un client ne voit pas les commandes d'autres clients."""
        autre_client = creer_client(email='autre@hooyia.com', username='autre')
        adresse_autre = creer_adresse(autre_client)
        preparer_panier(autre_client, self.vendeur, quantite=1)
        # On doit créer manuellement le panier de l'autre client pour ce test
        # La commande de l'autre client
        OrderService.create_from_cart(utilisateur=autre_client, adresse=adresse_autre)

        self._auth(self.token_client)
        response = self.client.get(reverse('api_commandes'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultats = response.data.get('results', response.data)
        # Notre client n'a passé aucune commande → liste vide
        self.assertEqual(len(resultats), 0)