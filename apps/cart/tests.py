"""
HooYia Market — cart/tests.py
Tests pour l'app cart :
- Modèles (Panier, PanierItem)
- CartService (add_item, remove_item, update_quantity)
- API (voir panier, ajouter, modifier, supprimer, vider)
- Signal (création automatique du panier à l'inscription)
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal

from .models import Panier, PanierItem
from .services import CartService
from apps.users.models import CustomUser
from apps.products.models import Produit, Categorie


# ═══════════════════════════════════════════════════════════════
# HELPERS — Fonctions utilitaires réutilisables dans tous les tests
# ═══════════════════════════════════════════════════════════════

def creer_client(email='client@hooyia.com', username='client'):
    """Crée un utilisateur client actif"""
    return CustomUser.objects.create_user(
        email     = email,
        username  = username,
        password  = 'Client123!',
        is_active = True,
    )

def creer_vendeur():
    """Crée un utilisateur vendeur actif"""
    return CustomUser.objects.create_user(
        email      = 'vendeur@hooyia.com',
        username   = 'vendeur',
        password   = 'Vendeur123!',
        is_active  = True,
        is_vendeur = True,
    )

def creer_produit(vendeur, prix=Decimal('50000.00'), stock=10, **kwargs):
    """Crée un produit actif de test"""
    categorie, _ = Categorie.objects.get_or_create(nom='Électronique')
    defaults = {
        'nom'        : 'Produit Test',
        'description': 'Description test',
        'prix'       : prix,
        'stock'      : stock,
        'statut'     : 'actif',
        'categorie'  : categorie,
        'vendeur'    : vendeur,
    }
    defaults.update(kwargs)
    return Produit.objects.create(**defaults)


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèles Panier et PanierItem
# ═══════════════════════════════════════════════════════════════

class PanierModelTest(TestCase):

    def setUp(self):
        self.vendeur = creer_vendeur()
        # Le signal creer_panier_utilisateur crée automatiquement un panier
        self.client_user = creer_client()
        self.panier = self.client_user.panier

    def test_signal_cree_panier_a_linscription(self):
        """Un panier doit être créé automatiquement lors de la création d'un utilisateur"""
        self.assertIsNotNone(self.panier)
        self.assertEqual(self.panier.utilisateur, self.client_user)

    def test_panier_vide_par_defaut(self):
        """Un nouveau panier doit être vide"""
        self.assertTrue(self.panier.est_vide)
        self.assertEqual(self.panier.nombre_articles, 0)
        self.assertEqual(self.panier.total, 0)

    def test_str_panier(self):
        """__str__ doit retourner le nom de l'utilisateur"""
        self.assertIn('client', str(self.panier))

    def test_panier_item_sous_total(self):
        """Le sous-total d'une ligne doit être quantite × prix_snapshot"""
        produit = creer_produit(self.vendeur, prix=Decimal('30000.00'), stock=10)
        item = PanierItem.objects.create(
            panier        = self.panier,
            produit       = produit,
            quantite      = 3,
            prix_snapshot = Decimal('30000.00'),
        )
        self.assertEqual(item.sous_total, Decimal('90000.00'))

    def test_total_panier(self):
        """Le total du panier doit être la somme des sous-totaux"""
        produit1 = creer_produit(self.vendeur, nom='Prod1', prix=Decimal('10000.00'), stock=10)
        produit2 = creer_produit(self.vendeur, nom='Prod2', prix=Decimal('20000.00'), stock=10)
        PanierItem.objects.create(
            panier=self.panier, produit=produit1,
            quantite=2, prix_snapshot=Decimal('10000.00')
        )
        PanierItem.objects.create(
            panier=self.panier, produit=produit2,
            quantite=1, prix_snapshot=Decimal('20000.00')
        )
        # 2×10000 + 1×20000 = 40000
        self.assertEqual(self.panier.total, Decimal('40000.00'))

    def test_nombre_articles(self):
        """nombre_articles doit sommer les quantités, pas les lignes"""
        produit1 = creer_produit(self.vendeur, nom='Prod1', stock=10)
        produit2 = creer_produit(self.vendeur, nom='Prod2', stock=10)
        PanierItem.objects.create(
            panier=self.panier, produit=produit1,
            quantite=3, prix_snapshot=Decimal('10000.00')
        )
        PanierItem.objects.create(
            panier=self.panier, produit=produit2,
            quantite=2, prix_snapshot=Decimal('20000.00')
        )
        # 3 + 2 = 5 articles (pas 2 lignes)
        self.assertEqual(self.panier.nombre_articles, 5)

    def test_vider_panier(self):
        """vider() doit supprimer tous les articles mais conserver le panier"""
        produit = creer_produit(self.vendeur, stock=10)
        PanierItem.objects.create(
            panier=self.panier, produit=produit,
            quantite=2, prix_snapshot=Decimal('50000.00')
        )
        self.panier.vider()
        self.assertTrue(self.panier.est_vide)
        # Le panier lui-même existe toujours
        self.assertIsNotNone(Panier.objects.get(pk=self.panier.pk))

    def test_unique_together_panier_produit(self):
        """Un même produit ne peut apparaître qu'une seule fois par panier"""
        from django.db import IntegrityError
        produit = creer_produit(self.vendeur, stock=10)
        PanierItem.objects.create(
            panier=self.panier, produit=produit,
            quantite=1, prix_snapshot=Decimal('50000.00')
        )
        with self.assertRaises(IntegrityError):
            PanierItem.objects.create(
                panier=self.panier, produit=produit,
                quantite=2, prix_snapshot=Decimal('50000.00')
            )


# ═══════════════════════════════════════════════════════════════
# TESTS — CartService
# ═══════════════════════════════════════════════════════════════

class CartServiceTest(TestCase):

    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.panier      = self.client_user.panier
        self.produit     = creer_produit(self.vendeur, prix=Decimal('50000.00'), stock=10)

    def test_add_item_nouveau(self):
        """Ajouter un nouveau produit doit créer une ligne PanierItem"""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        self.assertEqual(item.quantite, 2)
        self.assertEqual(item.prix_snapshot, self.produit.prix_actuel)
        self.assertEqual(self.panier.nombre_articles, 2)

    def test_add_item_existant_incremente(self):
        """Ajouter un produit déjà présent doit incrémenter la quantité"""
        CartService.add_item(self.panier, self.produit.pk, quantite=2)
        CartService.add_item(self.panier, self.produit.pk, quantite=3)
        item = PanierItem.objects.get(panier=self.panier, produit=self.produit)
        self.assertEqual(item.quantite, 5)

    def test_add_item_stock_insuffisant(self):
        """Ajouter plus que le stock disponible doit lever une ValidationError"""
        with self.assertRaises(ValidationError):
            CartService.add_item(self.panier, self.produit.pk, quantite=999)

    def test_add_item_produit_inexistant(self):
        """Ajouter un produit inexistant doit lever une ValidationError"""
        with self.assertRaises(ValidationError):
            CartService.add_item(self.panier, produit_id=99999, quantite=1)

    def test_remove_item(self):
        """Supprimer un article doit retirer la ligne du panier"""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        CartService.remove_item(self.panier, item.pk)
        self.assertTrue(self.panier.est_vide)

    def test_remove_item_inexistant(self):
        """Supprimer un article qui n'existe pas doit lever une ValidationError"""
        with self.assertRaises(ValidationError):
            CartService.remove_item(self.panier, item_id=99999)

    def test_update_quantity(self):
        """Mettre à jour la quantité doit modifier la ligne correctement"""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        item_mis_a_jour = CartService.update_quantity(self.panier, item.pk, nouvelle_quantite=5)
        self.assertEqual(item_mis_a_jour.quantite, 5)

    def test_update_quantity_zero_supprime(self):
        """Mettre la quantité à 0 doit supprimer la ligne"""
        item = CartService.add_item(self.panier, self.produit.pk, quantite=2)
        result = CartService.update_quantity(self.panier, item.pk, nouvelle_quantite=0)
        self.assertIsNone(result)
        self.assertTrue(self.panier.est_vide)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Panier
# ═══════════════════════════════════════════════════════════════

class PanierAPITest(APITestCase):

    def setUp(self):
        self.vendeur     = creer_vendeur()
        self.client_user = creer_client()
        self.produit     = creer_produit(self.vendeur, prix=Decimal('50000.00'), stock=10)

        # Authentifie le client pour tous les tests
        token_response = self.client.post(reverse('token_obtain'), {
            'email'   : 'client@hooyia.com',
            'password': 'Client123!',
        }, format='json')
        token = token_response.data.get('access', '')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_voir_panier(self):
        """GET /api/panier/ doit retourner le panier de l'utilisateur connecté"""
        response = self.client.get(reverse('api_panier'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('items', response.data)
        self.assertIn('total', response.data)

    def test_voir_panier_non_authentifie(self):
        """Un visiteur non connecté ne peut pas voir de panier"""
        self.client.credentials()  # Retire le token
        response = self.client.get(reverse('api_panier'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ajouter_item(self):
        """POST /api/panier/ajouter/ doit ajouter un article au panier"""
        response = self.client.post(reverse('api_panier_ajouter'), {
            'produit_id': self.produit.pk,
            'quantite'  : 2,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nombre_articles'], 2)

    def test_ajouter_item_stock_insuffisant(self):
        """Ajouter plus que le stock doit retourner une erreur 400"""
        response = self.client.post(reverse('api_panier_ajouter'), {
            'produit_id': self.produit.pk,
            'quantite'  : 999,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_modifier_quantite(self):
        """PATCH /api/panier/items/<id>/ doit modifier la quantité"""
        # D'abord, ajouter un article
        panier = self.client_user.panier
        item   = CartService.add_item(panier, self.produit.pk, quantite=2)

        response = self.client.patch(
            reverse('api_panier_item', kwargs={'pk': item.pk}),
            {'quantite': 5},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_articles'], 5)

    def test_supprimer_item(self):
        """DELETE /api/panier/items/<id>/ doit supprimer la ligne"""
        panier = self.client_user.panier
        item   = CartService.add_item(panier, self.produit.pk, quantite=2)

        response = self.client.delete(
            reverse('api_panier_item', kwargs={'pk': item.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nombre_articles'], 0)

    def test_vider_panier(self):
        """DELETE /api/panier/vider/ doit vider tout le panier"""
        panier = self.client_user.panier
        CartService.add_item(panier, self.produit.pk, quantite=2)

        response = self.client.delete(reverse('api_panier_vider'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Vérifie que le panier est bien vide
        response_panier = self.client.get(reverse('api_panier'))
        self.assertEqual(response_panier.data['nombre_articles'], 0)