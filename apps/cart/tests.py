"""
Tests pour l'app cart.

Couverture :
  - Signal : création automatique du panier à l'inscription
  - Modèles Panier et PanierItem (propriétés, contraintes)
  - CartService (add_item, remove_item, update_quantity, calculate_total)
  - API Panier (voir, ajouter, modifier, supprimer, vider)
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal

from apps.cart.models import Panier, PanierItem
from apps.cart.services import CartService
from apps.users.models import CustomUser
from apps.products.models import Produit, Categorie


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_client(email='client@hooyia.com', username='client'):
    return CustomUser.objects.create_user(
        email=email, username=username, password='Client123!', is_active=True,
    )

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_vendeur(email='vendeur@hooyia.com', username='vendeur'):
    return CustomUser.objects.create_user(
        email=email, username=username, password='Vendeur123!',
        is_active=True, is_vendeur=True,
    )

def creer_produit(vendeur, nom='Produit Test', prix=Decimal('50000.00'), stock=10, **kwargs):
    """Crée un produit actif de test."""
    categorie, _ = Categorie.objects.get_or_create(nom='Électronique')
    defaults = {
        'nom': nom, 'description': 'Description',
        'prix': prix, 'stock': stock,
        'statut': 'actif', 'categorie': categorie, 'vendeur': vendeur,
    }
    defaults.update(kwargs)
    return Produit.objects.create(**defaults)


# ═══════════════════════════════════════════════════════════════
# TESTS — Signal et Modèle Panier
# ═══════════════════════════════════════════════════════════════

class PanierModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.vendeur = creer_vendeur()
        self.client_user = creer_client()
        self.panier = self.client_user.panier  # créé par signal

    def test_signal_cree_panier_a_linscription(self):
        """Un panier est créé automatiquement à la création d'un utilisateur."""
        self.assertIsNotNone(self.panier)
        self.assertEqual(self.panier.utilisateur, self.client_user)

    def test_panier_vide_par_defaut(self):
        """Un nouveau panier est vide."""
        self.assertTrue(self.panier.est_vide)
        self.assertEqual(self.panier.nombre_articles, 0)
        self.assertEqual(self.panier.total, 0)

    def test_str_panier(self):
        """__str__ mentionne le username."""
        self.assertIn(self.client_user.username, str(self.panier))

    def test_sous_total_panier_item(self):
        """Le sous-total d'une ligne est quantite × prix_snapshot."""
        produit = creer_produit(self.vendeur, prix=Decimal('30000.00'))
        item = PanierItem.objects.create(
            panier=self.panier, produit=produit,
            quantite=3, prix_snapshot=Decimal('30000.00'),
        )
        self.assertEqual(item.sous_total, Decimal('90000.00'))

    def test_total_panier_multi_lignes(self):
        """Le total est la somme des sous-totaux de toutes les lignes."""
        p1 = creer_produit(self.vendeur, nom='P1', prix=Decimal('10000.00'))
        p2 = creer_produit(self.vendeur, nom='P2', prix=Decimal('20000.00'))
        PanierItem.objects.create(
            panier=self.panier, produit=p1, quantite=2, prix_snapshot=Decimal('10000.00')
        )
        PanierItem.objects.create(
            panier=self.panier, produit=p2, quantite=1, prix_snapshot=Decimal('20000.00')
        )
        # 2×10000 + 1×20000 = 40000
        self.assertEqual(self.panier.total, Decimal('40000.00'))

    def test_nombre_articles_somme_quantites(self):
        """nombre_articles additionne les quantités (pas le nombre de lignes)."""
        p1 = creer_produit(self.vendeur, nom='P1')
        p2 = creer_produit(self.vendeur, nom='P2')
        PanierItem.objects.create(
            panier=self.panier, produit=p1, quantite=3, prix_snapshot=Decimal('10000.00')
        )
        PanierItem.objects.create(
            panier=self.panier, produit=p2, quantite=2, prix_snapshot=Decimal('20000.00')
        )
        self.assertEqual(self.panier.nombre_articles, 5)  # 3 + 2

    def test_vider_panier_supprime_items(self):
        """vider() supprime les articles mais conserve le panier."""
        produit = creer_produit(self.vendeur)
        PanierItem.objects.create(
            panier=self.panier, produit=produit,
            quantite=2, prix_snapshot=Decimal('50000.00')
        )
        self.panier.vider()
        self.assertTrue(self.panier.est_vide)
        self.assertIsNotNone(Panier.objects.filter(pk=self.panier.pk).first())

    def test_unique_together_panier_produit(self):
        """Un produit ne peut apparaître qu'une seule fois par panier."""
        from django.db import IntegrityError
        produit = creer_produit(self.vendeur)
        PanierItem.objects.create(
            panier=self.panier, produit=produit, quantite=1, prix_snapshot=Decimal('50000.00')
        )
        with self.assertRaises(IntegrityError):
            PanierItem.objects.create(
                panier=self.panier, produit=produit, quantite=2, prix_snapshot=Decimal('50000.00')
            )


# ═══════════════════════════════════════════════════════════════
# TESTS — CartService
# ═══════════════════════════════════════════════════════════════

class CartServiceTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.panier      = self.client_user.panier
        self.produit     = creer_produit(self.vendeur, prix=Decimal('50000.00'), stock=10)

    def test_add_item_nouveau(self):
        """Ajouter un produit crée un PanierItem avec le bon prix snapshot."""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        self.assertEqual(item.quantite, 2)
        self.assertEqual(item.prix_snapshot, self.produit.prix_actuel)
        self.assertEqual(self.panier.nombre_articles, 2)

    def test_add_item_existant_incremente(self):
        """Ajouter un produit déjà présent incrémente la quantité."""
        CartService.add_item(self.panier, self.produit.pk, quantite=2)
        CartService.add_item(self.panier, self.produit.pk, quantite=3)
        item = PanierItem.objects.get(panier=self.panier, produit=self.produit)
        self.assertEqual(item.quantite, 5)

    def test_add_item_stock_insuffisant(self):
        """Ajouter plus que le stock lève ValidationError."""
        with self.assertRaises(ValidationError):
            CartService.add_item(self.panier, self.produit.pk, quantite=999)

    def test_add_item_quantite_zero(self):
        """Ajouter une quantité <= 0 lève ValidationError."""
        with self.assertRaises(ValidationError):
            CartService.add_item(self.panier, self.produit.pk, quantite=0)

    def test_add_item_produit_inexistant(self):
        """Ajouter un produit inexistant lève ValidationError."""
        with self.assertRaises(ValidationError):
            CartService.add_item(self.panier, produit_id=99999, quantite=1)

    def test_add_item_capture_prix_promo(self):
        """Ajouter un produit en promo capture le prix promo dans le snapshot."""
        produit_promo = creer_produit(
            self.vendeur, nom='Promo',
            prix=Decimal('100000.00'), prix_promo=Decimal('75000.00'), stock=5
        )
        item = CartService.add_item(self.panier, produit_promo.pk, quantite=1)
        self.assertEqual(item.prix_snapshot, Decimal('75000.00'))

    def test_remove_item(self):
        """Supprimer un article retire la ligne du panier."""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        CartService.remove_item(self.panier, item.pk)
        self.assertTrue(self.panier.est_vide)

    def test_remove_item_inexistant(self):
        """Supprimer un article inexistant lève ValidationError."""
        with self.assertRaises(ValidationError):
            CartService.remove_item(self.panier, item_id=99999)

    def test_update_quantity(self):
        """Modifier la quantité met à jour le PanierItem."""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        item_maj = CartService.update_quantity(self.panier, item.pk, nouvelle_quantite=5)
        self.assertEqual(item_maj.quantite, 5)

    def test_update_quantity_zero_supprime(self):
        """Mettre la quantité à 0 supprime la ligne."""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        result = CartService.update_quantity(self.panier, item.pk, nouvelle_quantite=0)
        self.assertIsNone(result)
        self.assertTrue(self.panier.est_vide)

    def test_update_quantity_stock_insuffisant(self):
        """Mettre une quantité supérieure au stock lève ValidationError."""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=1)
        with self.assertRaises(ValidationError):
            CartService.update_quantity(self.panier, item.pk, nouvelle_quantite=999)

    def test_calculate_total(self):
        """calculate_total retourne le détail complet du panier."""
        CartService.add_item(self.panier, self.produit.pk, quantite=2)
        result = CartService.calculate_total(self.panier)
        self.assertIn('items',           result)
        self.assertIn('total',           result)
        self.assertIn('nombre_articles', result)
        self.assertEqual(result['nombre_articles'], 2)
        self.assertEqual(result['total'], Decimal('100000.00'))  # 2 × 50000


# ═══════════════════════════════════════════════════════════════
# TESTS — API Panier
# ═══════════════════════════════════════════════════════════════

class PanierAPITest(APITestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.produit     = creer_produit(self.vendeur, prix=Decimal('50000.00'), stock=10)

        # Authentifie le client
        token_resp = self.client.post(reverse('token_obtain'), {
            'email': 'client@hooyia.com', 'password': 'Client123!',
        }, format='json')
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token_resp.data["access"]}'
        )

    def test_voir_panier(self):
        """GET /api/panier/ retourne le panier avec items et total."""
        response = self.client.get(reverse('api_panier'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('items', response.data)
        self.assertIn('total', response.data)

    def test_voir_panier_non_authentifie(self):
        """Un visiteur non connecté ne peut pas voir de panier → 401."""
        self.client.credentials()
        response = self.client.get(reverse('api_panier'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ajouter_item(self):
        """POST /api/panier/ajouter/ ajoute un article → 201."""
        response = self.client.post(reverse('api_panier_ajouter'), {
            'produit_id': self.produit.pk, 'quantite': 2,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre_articles'], 2)

    def test_ajouter_item_stock_insuffisant(self):
        """Ajouter plus que le stock → 400."""
        response = self.client.post(reverse('api_panier_ajouter'), {
            'produit_id': self.produit.pk, 'quantite': 999,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modifier_quantite(self):
        """PATCH /api/panier/items/<id>/ modifie la quantité."""
        panier = self.client_user.panier
        item   = CartService.add_item(panier, self.produit.pk, quantite=2)
        response = self.client.patch(
            reverse('api_panier_item', kwargs={'pk': item.pk}),
            {'quantite': 5}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_articles'], 5)

    def test_supprimer_item(self):
        """DELETE /api/panier/items/<id>/ supprime la ligne."""
        panier = self.client_user.panier
        item   = CartService.add_item(panier, self.produit.pk, quantite=2)
        response = self.client.delete(
            reverse('api_panier_item', kwargs={'pk': item.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_articles'], 0)

    def test_vider_panier(self):
        """DELETE /api/panier/vider/ vide tout le panier → 200."""
        panier = self.client_user.panier
        CartService.add_item(panier, self.produit.pk, quantite=2)
        response = self.client.delete(reverse('api_panier_vider'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Vérifie le panier vide
        response_check = self.client.get(reverse('api_panier'))
        self.assertEqual(response_check.data['nombre_articles'], 0)