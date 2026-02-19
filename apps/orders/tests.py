"""
HooYia Market — orders/tests.py
Tests pour l'app orders :
- Modèles (Commande FSM, LigneCommande, Paiement)
- OrderService (create_from_cart, annuler_commande)
- Transitions FSM (cycle de vie complet)
- API (créer, lister, détail, annuler)
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from unittest.mock import patch

from .models import Commande, LigneCommande, Paiement
from .services import OrderService
from apps.users.models import CustomUser, AdresseLivraison
from apps.products.models import Produit, Categorie
from apps.cart.models import Panier, PanierItem
from apps.cart.services import CartService


# ═══════════════════════════════════════════════════════════════
# HELPERS — Fonctions utilitaires réutilisables
# ═══════════════════════════════════════════════════════════════

def creer_client(email='client@hooyia.com', username='client'):
    """Crée un client actif avec panier (via signal)"""
    return CustomUser.objects.create_user(
        email=email, username=username,
        password='Client123!', is_active=True,
    )

def creer_vendeur():
    """Crée un vendeur actif"""
    return CustomUser.objects.create_user(
        email='vendeur@hooyia.com', username='vendeur',
        password='Vendeur123!', is_active=True, is_vendeur=True,
    )

def creer_admin():
    """Crée un admin actif"""
    return CustomUser.objects.create_user(
        email='admin@hooyia.com', username='admin',
        password='Admin123!', is_active=True, is_admin=True, is_staff=True,
    )

def creer_produit(vendeur, prix=Decimal('50000.00'), stock=10, **kwargs):
    """Crée un produit actif de test"""
    categorie, _ = Categorie.objects.get_or_create(nom='Électronique')
    defaults = {
        'nom': 'Produit Test', 'description': 'Desc',
        'prix': prix, 'stock': stock, 'statut': 'actif',
        'categorie': categorie, 'vendeur': vendeur,
    }
    defaults.update(kwargs)
    return Produit.objects.create(**defaults)

def creer_adresse(utilisateur):
    """Crée une adresse de livraison pour un utilisateur"""
    return AdresseLivraison.objects.create(
        utilisateur=utilisateur,
        nom_complet='Jean Dupont',
        telephone='699000000',
        adresse='123 Rue Test',
        ville='Yaoundé',
        region='Centre',
        pays='Cameroun',
        is_default=True,
    )

def preparer_panier_avec_produit(utilisateur, vendeur, quantite=2):
    """
    Prépare un panier avec un produit prêt pour commander.
    Retourne (panier, produit).
    """
    produit = creer_produit(vendeur, prix=Decimal('50000.00'), stock=10)
    CartService.add_item(utilisateur.panier, produit.pk, quantite=quantite)
    return utilisateur.panier, produit


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Commande et FSM
# ═══════════════════════════════════════════════════════════════

class CommandeModelTest(TestCase):

    def setUp(self):
        self.client_user = creer_client()
        self.adresse     = creer_adresse(self.client_user)

    def _creer_commande(self):
        """Crée une commande minimale en EN_ATTENTE pour les tests FSM"""
        return Commande.objects.create(
            client                      = self.client_user,
            montant_total               = Decimal('100000.00'),
            adresse_livraison_nom       = 'Jean Dupont',
            adresse_livraison_telephone = '699000000',
            adresse_livraison_adresse   = '123 Rue Test',
            adresse_livraison_ville     = 'Yaoundé',
            adresse_livraison_region    = 'Centre',
            adresse_livraison_pays      = 'Cameroun',
        )

    def test_statut_initial_en_attente(self):
        """Une nouvelle commande doit être en EN_ATTENTE"""
        commande = self._creer_commande()
        self.assertEqual(commande.statut, Commande.EN_ATTENTE)

    def test_reference_courte(self):
        """La référence courte doit avoir 8 caractères"""
        commande = self._creer_commande()
        self.assertEqual(len(commande.reference_courte), 8)

    def test_transition_confirmer(self):
        """La commande doit passer de EN_ATTENTE à CONFIRMEE"""
        commande = self._creer_commande()
        commande.confirmer()
        commande.save()
        self.assertEqual(commande.statut, Commande.CONFIRMEE)

    def test_transition_cycle_complet(self):
        """Le cycle complet EN_ATTENTE → CONFIRMEE → EN_PREPARATION → EXPEDIEE → LIVREE"""
        commande = self._creer_commande()
        commande.confirmer()
        commande.save()
        commande.mettre_en_preparation()
        commande.save()
        commande.expedier()
        commande.save()
        commande.livrer()
        commande.save()
        self.assertEqual(commande.statut, Commande.LIVREE)

    def test_transition_interdite(self):
        """Sauter une étape du cycle FSM doit lever TransitionNotAllowed"""
        commande = self._creer_commande()
        # On ne peut pas passer directement à EXPEDIEE depuis EN_ATTENTE
        with self.assertRaises(TransitionNotAllowed):
            commande.expedier()

    def test_annulation_depuis_en_attente(self):
        """Une commande EN_ATTENTE peut être annulée"""
        commande = self._creer_commande()
        commande.annuler()
        commande.save()
        self.assertEqual(commande.statut, Commande.ANNULEE)

    def test_annulation_impossible_si_livree(self):
        """Une commande LIVREE ne peut pas être annulée"""
        commande = self._creer_commande()
        commande.confirmer()
        commande.save()
        commande.mettre_en_preparation()
        commande.save()
        commande.expedier()
        commande.save()
        commande.livrer()
        commande.save()
        with self.assertRaises(TransitionNotAllowed):
            commande.annuler()

    def test_peut_etre_annulee(self):
        """peut_etre_annulee doit retourner True si pas LIVREE ni ANNULEE"""
        commande = self._creer_commande()
        self.assertTrue(commande.peut_etre_annulee)


# ═══════════════════════════════════════════════════════════════
# TESTS — OrderService
# ═══════════════════════════════════════════════════════════════

class OrderServiceTest(TestCase):

    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.adresse     = creer_adresse(self.client_user)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart(self, mock_email):
        """OrderService.create_from_cart() doit créer une commande complète"""
        panier, produit = preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=2)

        commande = OrderService.create_from_cart(
            utilisateur=self.client_user,
            adresse=self.adresse,
        )

        # Vérifie la commande
        self.assertEqual(commande.client, self.client_user)
        self.assertEqual(commande.statut, Commande.CONFIRMEE)
        self.assertEqual(commande.montant_total, Decimal('100000.00'))  # 2 × 50000

        # Vérifie les lignes
        self.assertEqual(commande.lignes.count(), 1)
        ligne = commande.lignes.first()
        self.assertEqual(ligne.quantite, 2)
        self.assertEqual(ligne.produit_nom, produit.nom)

        # Vérifie que le panier est vidé
        self.assertTrue(panier.est_vide)

        # Vérifie que le stock a été décrémenté
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 8)  # 10 - 2

        # Vérifie que le paiement a été créé
        self.assertTrue(hasattr(commande, 'paiement'))

    def test_create_from_cart_panier_vide(self):
        """Créer une commande avec un panier vide doit lever une ValidationError"""
        with self.assertRaises(ValidationError):
            OrderService.create_from_cart(
                utilisateur=self.client_user,
                adresse=self.adresse,
            )

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_create_from_cart_stock_insuffisant(self, mock_email):
        """Créer une commande avec plus que le stock doit lever une ValidationError"""
        produit = creer_produit(self.vendeur, stock=1)
        # Ajoute 1 article au panier (stock = 1, ok)
        CartService.add_item(self.client_user.panier, produit.pk, quantite=1)
        # Réduit le stock manuellement à 0 pour simuler une rupture
        produit.stock = 0
        produit.save()

        with self.assertRaises(ValidationError):
            OrderService.create_from_cart(
                utilisateur=self.client_user,
                adresse=self.adresse,
            )

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_remet_stock(self, mock_email):
        """Annuler une commande doit remettre le stock des produits"""
        panier, produit = preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=3)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        # Stock après commande : 10 - 3 = 7
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 7)

        OrderService.annuler_commande(commande, self.client_user)

        # Stock après annulation : 7 + 3 = 10
        produit.refresh_from_db()
        self.assertEqual(produit.stock, 10)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_non_proprietaire(self, mock_email):
        """Un autre utilisateur ne peut pas annuler une commande qui ne lui appartient pas"""
        panier, _ = preparer_panier_avec_produit(self.client_user, self.vendeur)
        commande  = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        autre_user = creer_client(email='autre@hooyia.com', username='autre')
        with self.assertRaises(ValidationError):
            OrderService.annuler_commande(commande, autre_user)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Commandes
# ═══════════════════════════════════════════════════════════════

class CommandeAPITest(APITestCase):

    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.admin       = creer_admin()
        self.adresse     = creer_adresse(self.client_user)

        # Authentifie le client
        resp = self.client.post(reverse('token_obtain'), {
            'email': 'client@hooyia.com', 'password': 'Client123!'
        }, format='json')
        self.token_client = resp.data.get('access', '')

    def _auth(self, token):
        """Applique le token JWT aux en-têtes"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_creer_commande(self, mock_email):
        """POST /api/commandes/creer/ doit créer une commande depuis le panier"""
        preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=2)
        self._auth(self.token_client)

        response = self.client.post(reverse('api_commande_creer'), {
            'adresse_id'   : self.adresse.pk,
            'mode_paiement': 'livraison',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['statut'], Commande.CONFIRMEE)

    def test_creer_commande_panier_vide(self):
        """Créer une commande avec un panier vide doit retourner 400"""
        self._auth(self.token_client)

        response = self.client.post(reverse('api_commande_creer'), {
            'adresse_id'   : self.adresse.pk,
            'mode_paiement': 'livraison',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_lister_commandes(self, mock_email):
        """GET /api/commandes/ doit retourner uniquement les commandes du client"""
        preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=1)
        OrderService.create_from_cart(utilisateur=self.client_user, adresse=self.adresse)
        self._auth(self.token_client)

        response = self.client.get(reverse('api_commandes'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # La réponse est paginée → les commandes sont dans 'results'
        resultats = response.data.get('results', response.data)
        self.assertEqual(len(resultats), 1)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_detail_commande(self, mock_email):
        """GET /api/commandes/<id>/ doit retourner le détail de la commande"""
        preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=1)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        self._auth(self.token_client)

        response = self.client.get(reverse('api_commande_detail', kwargs={'pk': commande.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('lignes', response.data)
        self.assertIn('paiement', response.data)

    @patch('apps.notifications.tasks.send_order_confirmation_email.delay')
    def test_annuler_commande_client(self, mock_email):
        """POST /api/commandes/<id>/annuler/ doit annuler la commande du client"""
        preparer_panier_avec_produit(self.client_user, self.vendeur, quantite=1)
        commande = OrderService.create_from_cart(
            utilisateur=self.client_user, adresse=self.adresse
        )
        self._auth(self.token_client)

        response = self.client.post(
            reverse('api_commande_annuler', kwargs={'pk': commande.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['commande']['statut'], Commande.ANNULEE)

    def test_commande_non_authentifie(self):
        """Un visiteur non connecté ne peut pas accéder aux commandes"""
        self.client.credentials()
        response = self.client.get(reverse('api_commandes'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)