"""
Tests pour l'app products :
- Modèles (Produit, Categorie, ImageProduit)
- Managers personnalisés
- Signals (cache, resize)
- API (CRUD, filtres, permissions, pagination)
"""
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal

from .models import Produit, Categorie, MouvementStock
from apps.users.models import CustomUser


# ═══════════════════════════════════════════════════════════════
# HELPER — Crée les objets de base réutilisables dans les tests
# ═══════════════════════════════════════════════════════════════

def creer_vendeur():
    """Crée un utilisateur vendeur actif"""
    return CustomUser.objects.create_user(
        email     = 'vendeur@hooyia.com',
        username  = 'vendeur',
        password  = 'Vendeur123!',
        is_active = True,
        is_vendeur= True
    )

def creer_admin():
    """Crée un administrateur actif"""
    return CustomUser.objects.create_user(
        email     = 'admin@hooyia.com',
        username  = 'admin',
        password  = 'Admin123!',
        is_active = True,
        is_admin  = True,
        is_staff  = True
    )

def creer_categorie(nom='Électronique'):
    """Crée une catégorie de test"""
    return Categorie.objects.create(nom=nom)

def creer_produit(vendeur, categorie, **kwargs):
    """Crée un produit de test avec des valeurs par défaut"""
    defaults = {
        'nom'        : 'Smartphone Test',
        'description': 'Description du produit test',
        'prix'       : Decimal('150000.00'),
        'stock'      : 10,
        'statut'     : 'actif',
        'categorie'  : categorie,
        'vendeur'    : vendeur,
    }
    defaults.update(kwargs)
    return Produit.objects.create(**defaults)


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Catégorie
# ═══════════════════════════════════════════════════════════════

class CategorieModelTest(TestCase):

    def test_creation_categorie(self):
        """Une catégorie doit être créée avec un slug automatique"""
        cat = Categorie.objects.create(nom='Téléphones')
        self.assertEqual(cat.nom, 'Téléphones')
        self.assertEqual(cat.slug, 'telephones')  # slugify retire les accents

    def test_categorie_parent(self):
        """Une sous-catégorie doit avoir un parent"""
        parent = Categorie.objects.create(nom='Électronique')
        enfant = Categorie.objects.create(nom='Téléphones', parent=parent)
        self.assertEqual(enfant.parent, parent)
        self.assertIn(enfant, parent.sous_categories.all())

    def test_str_categorie(self):
        """__str__ doit retourner le nom"""
        cat = Categorie.objects.create(nom='Informatique')
        self.assertEqual(str(cat), 'Informatique')


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Produit
# ═══════════════════════════════════════════════════════════════

class ProduitModelTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()

    def test_creation_produit(self):
        """Un produit doit être créé avec les bons attributs"""
        produit = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(produit.nom, 'Smartphone Test')
        self.assertEqual(produit.prix, Decimal('150000.00'))
        self.assertEqual(produit.stock, 10)
        self.assertEqual(produit.statut, 'actif')

    def test_slug_auto(self):
        """Le slug doit être généré automatiquement depuis le nom"""
        produit = creer_produit(self.vendeur, self.categorie, nom='iPhone 15 Pro')
        self.assertEqual(produit.slug, 'iphone-15-pro')

    def test_slug_unique(self):
        """Deux produits avec le même nom doivent avoir des slugs différents"""
        p1 = creer_produit(self.vendeur, self.categorie, nom='Samsung Galaxy')
        p2 = creer_produit(self.vendeur, self.categorie, nom='Samsung Galaxy')
        self.assertNotEqual(p1.slug, p2.slug)
        self.assertEqual(p2.slug, 'samsung-galaxy-1')

    def test_statut_epuise_si_stock_zero(self):
        """Un produit avec stock=0 doit passer en épuisé"""
        produit = creer_produit(self.vendeur, self.categorie, stock=0)
        self.assertEqual(produit.statut, 'epuise')

    def test_prix_actuel_sans_promo(self):
        """prix_actuel doit retourner le prix normal sans promo"""
        produit = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(produit.prix_actuel, Decimal('150000.00'))

    def test_prix_actuel_avec_promo(self):
        """prix_actuel doit retourner le prix promo s'il existe"""
        produit = creer_produit(
            self.vendeur, self.categorie,
            prix_promo=Decimal('120000.00')
        )
        self.assertEqual(produit.prix_actuel, Decimal('120000.00'))

    def test_est_en_stock(self):
        """est_en_stock doit retourner True si stock > 0"""
        produit = creer_produit(self.vendeur, self.categorie, stock=5)
        self.assertTrue(produit.est_en_stock)

    def test_pas_en_stock(self):
        """est_en_stock doit retourner False si stock = 0"""
        produit = creer_produit(
            self.vendeur, self.categorie,
            stock=0, statut='epuise'
        )
        self.assertFalse(produit.est_en_stock)

    def test_pourcentage_remise(self):
        """Le pourcentage de remise doit être calculé correctement"""
        produit = creer_produit(
            self.vendeur, self.categorie,
            prix=Decimal('100000.00'),
            prix_promo=Decimal('80000.00')
        )
        self.assertEqual(produit.pourcentage_remise, 20)

    def test_stock_faible(self):
        """stock_faible doit être True si stock <= stock_minimum"""
        produit = creer_produit(
            self.vendeur, self.categorie,
            stock=3, stock_minimum=5
        )
        self.assertTrue(produit.stock_faible)

    def test_str_produit(self):
        """__str__ doit retourner le nom du produit"""
        produit = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(str(produit), 'Smartphone Test')


# ═══════════════════════════════════════════════════════════════
# TESTS — Managers personnalisés
# ═══════════════════════════════════════════════════════════════

class ProduitManagerTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()

    def test_manager_actifs(self):
        """Produit.actifs doit retourner uniquement les produits actifs"""
        p_actif   = creer_produit(self.vendeur, self.categorie, statut='actif')
        p_inactif = creer_produit(
            self.vendeur, self.categorie,
            nom='Inactif', statut='inactif'
        )
        actifs = Produit.actifs.all()
        self.assertIn(p_actif, actifs)
        self.assertNotIn(p_inactif, actifs)

    def test_manager_vedette(self):
        """Produit.vedette doit retourner uniquement les produits en vedette"""
        p_vedette    = creer_produit(
            self.vendeur, self.categorie,
            en_vedette=True
        )
        p_non_vedette = creer_produit(
            self.vendeur, self.categorie,
            nom='Non vedette', en_vedette=False
        )
        vedette = Produit.vedette.all()
        self.assertIn(p_vedette, vedette)
        self.assertNotIn(p_non_vedette, vedette)

    def test_manager_stock_bas(self):
        """Produit.stock_bas doit retourner les produits sous le seuil"""
        p_bas   = creer_produit(
            self.vendeur, self.categorie,
            stock=2, stock_minimum=5
        )
        p_ok    = creer_produit(
            self.vendeur, self.categorie,
            nom='Stock OK', stock=20, stock_minimum=5
        )
        stock_bas = Produit.stock_bas.all()
        self.assertIn(p_bas, stock_bas)
        self.assertNotIn(p_ok, stock_bas)


# ═══════════════════════════════════════════════════════════════
# TESTS — Mouvement de stock
# ═══════════════════════════════════════════════════════════════

class MouvementStockTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()
        self.produit   = creer_produit(
            self.vendeur, self.categorie, stock=10
        )

    def test_creation_mouvement(self):
        """Un mouvement de stock doit être créé correctement"""
        mouvement = MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'entree',
            quantite       = 20,
            stock_avant    = 10,
            stock_apres    = 30,
            effectue_par   = self.vendeur
        )
        self.assertEqual(mouvement.quantite, 20)
        self.assertEqual(mouvement.stock_avant, 10)
        self.assertEqual(mouvement.stock_apres, 30)

    def test_signal_mise_a_jour_stock(self):
        """Le signal doit mettre à jour le stock du produit"""
        MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'entree',
            quantite       = 20,
            stock_avant    = 10,
            stock_apres    = 30,
            effectue_par   = self.vendeur
        )
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.stock, 30)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Produits
# ═══════════════════════════════════════════════════════════════

class ProduitAPITest(APITestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.admin     = creer_admin()
        self.categorie = creer_categorie()
        self.produit   = creer_produit(self.vendeur, self.categorie)
        self.url_liste = reverse('produit-list')
        self.url_detail = reverse('produit-detail', kwargs={'pk': self.produit.pk})

    def get_token(self, user, password):
        """Obtient un token JWT pour un utilisateur"""
        response = self.client.post(reverse('token_obtain'), {
            'email'   : user.email,
            'password': password
        }, format='json')
        return response.data.get('access', '')

    def test_liste_produits_publique(self):
        """La liste des produits est accessible sans authentification"""
        response = self.client.get(self.url_liste)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_detail_produit_public(self):
        """Le détail d'un produit est accessible sans authentification"""
        response = self.client.get(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nom'], 'Smartphone Test')

    def test_creer_produit_vendeur(self):
        """Un vendeur peut créer un produit"""
        token = self.get_token(self.vendeur, 'Vendeur123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        data = {
            'nom'        : 'Nouveau Produit',
            'description': 'Description test',
            'prix'       : '75000.00',
            'stock'      : 5,
            'categorie'  : self.categorie.pk
        }
        response = self.client.post(self.url_liste, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creer_produit_sans_auth(self):
        """Un visiteur ne peut pas créer un produit"""
        data = {
            'nom'  : 'Produit sans auth',
            'prix' : '50000.00',
            'stock': 5
        }
        response = self.client.post(self.url_liste, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_filtre_prix_min(self):
        """Le filtre prix_min doit fonctionner"""
        creer_produit(
            self.vendeur, self.categorie,
            nom='Produit Cher', prix=Decimal('500000.00')
        )
        response = self.client.get(
            self.url_liste, {'prix_min': '200000'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Seul le produit cher doit apparaître
        for produit in response.data['results']:
            self.assertGreaterEqual(
                Decimal(produit['prix']),
                Decimal('200000')
            )

    def test_filtre_en_stock(self):
        """Le filtre en_stock doit exclure les produits épuisés"""
        creer_produit(
            self.vendeur, self.categorie,
            nom='Épuisé', stock=0, statut='epuise'
        )
        response = self.client.get(
            self.url_liste, {'en_stock': 'true'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for produit in response.data['results']:
            self.assertGreater(produit['stock'], 0)

    def test_recherche_produit(self):
        """La recherche par nom doit fonctionner"""
        response = self.client.get(
            self.url_liste, {'search': 'Smartphone'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['results']), 0)

    def test_pagination(self):
        """La réponse doit être paginée"""
        response = self.client.get(self.url_liste)
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('results', response.data)

    def test_supprimer_produit_admin(self):
        """Un admin peut supprimer un produit"""
        token = self.get_token(self.admin, 'Admin123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_supprimer_produit_non_admin(self):
        """Un client normal ne peut pas supprimer un produit"""
        client_user = CustomUser.objects.create_user(
            email    = 'client@hooyia.com',
            username = 'client',
            password = 'Client123!',
            is_active= True
        )
        token = self.get_token(client_user, 'Client123!')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.delete(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_produits_en_vedette(self):
        """L'endpoint en_vedette doit retourner les produits en vedette"""
        creer_produit(
            self.vendeur, self.categorie,
            nom='Vedette', en_vedette=True
        )
        response = self.client.get('/api/produits/en_vedette/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def tearDown(self):
        """Vide le cache Redis après chaque test"""
        cache.clear()