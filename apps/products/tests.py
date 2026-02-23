"""
Tests pour l'app products.

Couverture :
  - Modèle Categorie (création, slug auto, hiérarchie MPTT)
  - Modèle Produit (création, slug auto/unique, statuts, propriétés)
  - Modèle MouvementStock + signal mise à jour stock
  - Managers personnalisés (actifs, vedette, stock_bas)
  - API Produits (liste publique, détail, filtres, pagination, CRUD, permissions)
"""
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from decimal import Decimal

from apps.products.models import Produit, Categorie, MouvementStock
from apps.users.models import CustomUser


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def creer_vendeur(email='vendeur@hooyia.com', username='vendeur'):
    return CustomUser.objects.create_user(
        email=email, username=username, password='Vendeur123!',
        is_active=True, is_vendeur=True,
    )

def creer_admin():
    return CustomUser.objects.create_user(
        email='admin@hooyia.com', username='admin', password='Admin123!',
        is_active=True, is_admin=True, is_staff=True,
    )

def creer_client(email='client@hooyia.com', username='client'):
    return CustomUser.objects.create_user(
        email=email, username=username, password='Client123!', is_active=True,
    )

def creer_categorie(nom='Électronique'):
    return Categorie.objects.create(nom=nom)

def creer_produit(vendeur, categorie=None, **kwargs):
    """Crée un produit actif avec des valeurs par défaut."""
    if categorie is None:
        categorie, _ = Categorie.objects.get_or_create(nom='Électronique')
    defaults = {
        'nom'        : 'Smartphone Test',
        'description': 'Description du produit test',
        'prix'       : Decimal('150000.00'),
        'stock'      : 10,
        'statut'     : Produit.Statut.ACTIF,
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
        """Une catégorie doit être créée avec un slug auto généré."""
        cat = Categorie.objects.create(nom='Téléphones')
        self.assertEqual(cat.nom, 'Telephones')       # slugify retire les accents
        self.assertIsNotNone(cat.slug)
        self.assertGreater(len(cat.slug), 0)

    def test_slug_auto_depuis_nom(self):
        """Le slug est généré depuis le nom sans accent."""
        cat = Categorie.objects.create(nom='Informatique')
        self.assertEqual(cat.slug, 'informatique')

    def test_slug_non_ecrase_si_existant(self):
        """Un slug fourni explicitement ne doit pas être écrasé."""
        cat = Categorie.objects.create(nom='Test', slug='mon-slug-perso')
        self.assertEqual(cat.slug, 'mon-slug-perso')

    def test_categorie_racine_sans_parent(self):
        """Une catégorie sans parent est une catégorie racine."""
        cat = Categorie.objects.create(nom='Racine')
        self.assertIsNone(cat.parent)

    def test_sous_categorie_avec_parent(self):
        """Une sous-catégorie doit référencer son parent."""
        parent = Categorie.objects.create(nom='Électronique')
        enfant = Categorie.objects.create(nom='Téléphones', parent=parent)
        self.assertEqual(enfant.parent, parent)
        self.assertIn(enfant, parent.sous_categories.all())

    def test_str_categorie(self):
        """__str__ retourne le nom."""
        cat = Categorie.objects.create(nom='Informatique')
        self.assertEqual(str(cat), 'Informatique')

    def test_est_active_par_defaut(self):
        """Une catégorie est active par défaut."""
        cat = Categorie.objects.create(nom='Active')
        self.assertTrue(cat.est_active)


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Produit
# ═══════════════════════════════════════════════════════════════

class ProduitModelTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()

    def test_creation_produit(self):
        """Un produit doit être créé avec les bons attributs."""
        p = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(p.nom,    'Smartphone Test')
        self.assertEqual(p.prix,   Decimal('150000.00'))
        self.assertEqual(p.stock,  10)
        self.assertEqual(p.statut, Produit.Statut.ACTIF)

    def test_slug_genere_automatiquement(self):
        """Le slug est généré depuis le nom si non fourni."""
        p = creer_produit(self.vendeur, self.categorie, nom='iPhone 15 Pro')
        self.assertEqual(p.slug, 'iphone-15-pro')

    def test_slug_unique_avec_suffixe(self):
        """Deux produits avec le même nom ont des slugs différents (suffixe -1, -2...)."""
        p1 = creer_produit(self.vendeur, self.categorie, nom='Samsung Galaxy')
        p2 = creer_produit(self.vendeur, self.categorie, nom='Samsung Galaxy')
        self.assertNotEqual(p1.slug, p2.slug)
        self.assertEqual(p2.slug, 'samsung-galaxy-1')

    def test_statut_epuise_si_stock_zero(self):
        """Un produit créé avec stock=0 passe automatiquement en 'epuise'."""
        p = creer_produit(self.vendeur, self.categorie, stock=0)
        self.assertEqual(p.statut, Produit.Statut.EPUISE)

    def test_prix_actuel_sans_promo(self):
        """prix_actuel retourne le prix normal si pas de promo."""
        p = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(p.prix_actuel, Decimal('150000.00'))

    def test_prix_actuel_avec_promo(self):
        """prix_actuel retourne le prix promo si défini."""
        p = creer_produit(self.vendeur, self.categorie, prix_promo=Decimal('120000.00'))
        self.assertEqual(p.prix_actuel, Decimal('120000.00'))

    def test_est_en_stock_true(self):
        """est_en_stock est True quand le stock > 0."""
        p = creer_produit(self.vendeur, self.categorie, stock=5)
        self.assertTrue(p.est_en_stock)

    def test_est_en_stock_false(self):
        """est_en_stock est False quand le stock = 0."""
        p = creer_produit(self.vendeur, self.categorie, stock=0, statut='epuise')
        self.assertFalse(p.est_en_stock)

    def test_pourcentage_remise(self):
        """Le pourcentage de remise est calculé correctement."""
        p = creer_produit(
            self.vendeur, self.categorie,
            prix=Decimal('100000.00'), prix_promo=Decimal('80000.00')
        )
        self.assertEqual(p.pourcentage_remise, 20)

    def test_pourcentage_remise_sans_promo(self):
        """Sans promotion, le pourcentage de remise est 0."""
        p = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(p.pourcentage_remise, 0)

    def test_stock_faible(self):
        """stock_faible est True si stock <= stock_minimum."""
        p = creer_produit(self.vendeur, self.categorie, stock=3, stock_minimum=5)
        self.assertTrue(p.stock_faible)

    def test_stock_suffisant(self):
        """stock_faible est False si stock > stock_minimum."""
        p = creer_produit(self.vendeur, self.categorie, stock=20, stock_minimum=5)
        self.assertFalse(p.stock_faible)

    def test_str_produit(self):
        """__str__ retourne le nom du produit."""
        p = creer_produit(self.vendeur, self.categorie)
        self.assertEqual(str(p), 'Smartphone Test')


# ═══════════════════════════════════════════════════════════════
# TESTS — Managers personnalisés
# ═══════════════════════════════════════════════════════════════

class ProduitManagerTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()

    def test_manager_actifs_exclut_inactif(self):
        """Produit.actifs ne retourne que les produits actifs."""
        p_actif   = creer_produit(self.vendeur, self.categorie, statut='actif')
        p_inactif = creer_produit(self.vendeur, self.categorie, nom='Inactif', statut='inactif')
        actifs = list(Produit.actifs.all())
        self.assertIn(p_actif,    actifs)
        self.assertNotIn(p_inactif, actifs)

    def test_manager_actifs_exclut_archive(self):
        """Produit.actifs exclut aussi les produits archivés."""
        p_archive = creer_produit(self.vendeur, self.categorie, nom='Archivé', statut='archive')
        self.assertNotIn(p_archive, Produit.actifs.all())

    def test_manager_vedette(self):
        """Produit.vedette retourne uniquement les produits en vedette."""
        p_vedette    = creer_produit(self.vendeur, self.categorie, en_vedette=True)
        p_non_vedette = creer_produit(self.vendeur, self.categorie, nom='Non vedette', en_vedette=False)
        vedette = list(Produit.vedette.all())
        self.assertIn(p_vedette,      vedette)
        self.assertNotIn(p_non_vedette, vedette)

    def test_manager_stock_bas(self):
        """Produit.stock_bas retourne les produits sous le seuil d'alerte."""
        p_bas = creer_produit(self.vendeur, self.categorie, stock=2, stock_minimum=5)
        p_ok  = creer_produit(self.vendeur, self.categorie, nom='Stock OK', stock=20, stock_minimum=5)
        stock_bas = list(Produit.stock_bas.all())
        self.assertIn(p_bas,  stock_bas)
        self.assertNotIn(p_ok, stock_bas)


# ═══════════════════════════════════════════════════════════════
# TESTS — MouvementStock + signal
# ═══════════════════════════════════════════════════════════════

class MouvementStockTest(TestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.categorie = creer_categorie()
        self.produit   = creer_produit(self.vendeur, self.categorie, stock=10)

    def test_creation_mouvement(self):
        """Un mouvement de stock est créé avec les bons attributs."""
        mouvement = MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'entree',
            quantite       = 20,
            stock_avant    = 10,
            stock_apres    = 30,
            effectue_par   = self.vendeur,
        )
        self.assertEqual(mouvement.quantite,    20)
        self.assertEqual(mouvement.stock_avant, 10)
        self.assertEqual(mouvement.stock_apres, 30)

    def test_signal_mise_a_jour_stock_entree(self):
        """Le signal met à jour le stock du produit après un mouvement d'entrée."""
        MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'entree',
            quantite       = 20,
            stock_avant    = 10,
            stock_apres    = 30,
            effectue_par   = self.vendeur,
        )
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.stock, 30)

    def test_signal_statut_epuise_si_stock_zero(self):
        """Le signal passe le produit en 'epuise' si stock tombe à 0."""
        MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'sortie',
            quantite       = 10,
            stock_avant    = 10,
            stock_apres    = 0,
            effectue_par   = self.vendeur,
        )
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.stock,  0)
        self.assertEqual(self.produit.statut, 'epuise')

    def test_signal_statut_actif_si_stock_remonte(self):
        """Le signal repasse le produit en 'actif' si le stock remonte > 0."""
        # Mettre d'abord en épuisé
        self.produit.stock  = 0
        self.produit.statut = 'epuise'
        self.produit.save()

        MouvementStock.objects.create(
            produit        = self.produit,
            type_mouvement = 'entree',
            quantite       = 5,
            stock_avant    = 0,
            stock_apres    = 5,
            effectue_par   = self.vendeur,
        )
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.stock,  5)
        self.assertEqual(self.produit.statut, 'actif')

    def test_str_mouvement(self):
        """__str__ contient le type et le nom du produit."""
        m = MouvementStock.objects.create(
            produit=self.produit, type_mouvement='entree',
            quantite=5, stock_avant=10, stock_apres=15, effectue_par=self.vendeur,
        )
        self.assertIn('entree', str(m))
        self.assertIn(self.produit.nom, str(m))


# ═══════════════════════════════════════════════════════════════
# TESTS — API Produits
# ═══════════════════════════════════════════════════════════════

class ProduitAPITest(APITestCase):

    def setUp(self):
        self.vendeur   = creer_vendeur()
        self.admin     = creer_admin()
        self.categorie = creer_categorie()
        self.produit   = creer_produit(self.vendeur, self.categorie)
        self.url_liste  = reverse('produit-list')
        self.url_detail = reverse('produit-detail', kwargs={'pk': self.produit.pk})

    def tearDown(self):
        """Vide le cache après chaque test pour éviter les interférences."""
        cache.clear()

    def _get_token(self, user, password):
        """Obtient un token JWT pour un utilisateur."""
        resp = self.client.post(reverse('token_obtain'), {
            'email': user.email, 'password': password
        }, format='json')
        return resp.data.get('access', '')

    def _auth(self, user, password):
        token = self._get_token(user, password)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # ── Lecture publique ──────────────────────────────────────

    def test_liste_produits_accessible_sans_auth(self):
        """La liste des produits est accessible sans authentification."""
        response = self.client.get(self.url_liste)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_detail_produit_accessible_sans_auth(self):
        """Le détail d'un produit est accessible sans authentification."""
        response = self.client.get(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nom'], 'Smartphone Test')

    def test_pagination_standard(self):
        """La réponse de liste est paginée avec count/next/previous/results."""
        response = self.client.get(self.url_liste)
        for key in ('count', 'next', 'previous', 'results'):
            self.assertIn(key, response.data)

    # ── Création ──────────────────────────────────────────────

    def test_creer_produit_vendeur(self):
        """Un vendeur peut créer un produit → 201."""
        self._auth(self.vendeur, 'Vendeur123!')
        data = {
            'nom'        : 'Nouveau Produit',
            'description': 'Description test',
            'prix'       : '75000.00',
            'stock'      : 5,
            'categorie'  : self.categorie.pk,
        }
        response = self.client.post(self.url_liste, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_creer_produit_sans_auth(self):
        """Un visiteur ne peut pas créer un produit → 401."""
        response = self.client.post(self.url_liste, {'nom': 'Test'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_creer_produit_client_normal(self):
        """Un client normal (non vendeur) ne peut pas créer un produit → 403."""
        client_user = creer_client()
        self._auth(client_user, 'Client123!')
        response = self.client.post(self.url_liste, {
            'nom': 'Produit client', 'prix': '10000', 'stock': 1
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Suppression ───────────────────────────────────────────

    def test_supprimer_produit_admin(self):
        """Un admin peut supprimer un produit → 204."""
        self._auth(self.admin, 'Admin123!')
        response = self.client.delete(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_supprimer_produit_client_refuse(self):
        """Un client normal ne peut pas supprimer un produit → 403."""
        client_user = creer_client()
        self._auth(client_user, 'Client123!')
        response = self.client.delete(self.url_detail)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Filtres ───────────────────────────────────────────────

    def test_filtre_prix_min(self):
        """Le filtre prix_min exclut les produits sous le seuil."""
        creer_produit(self.vendeur, self.categorie, nom='Cher', prix=Decimal('500000.00'))
        response = self.client.get(self.url_liste, {'prix_min': '200000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for p in response.data['results']:
            self.assertGreaterEqual(Decimal(p['prix']), Decimal('200000'))

    def test_filtre_prix_max(self):
        """Le filtre prix_max exclut les produits au-dessus du seuil."""
        creer_produit(self.vendeur, self.categorie, nom='Très Cher', prix=Decimal('999999.00'))
        response = self.client.get(self.url_liste, {'prix_max': '200000'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for p in response.data['results']:
            self.assertLessEqual(Decimal(p['prix']), Decimal('200000'))

    def test_filtre_en_stock(self):
        """Le filtre en_stock exclut les produits épuisés."""
        creer_produit(self.vendeur, self.categorie, nom='Épuisé', stock=0, statut='epuise')
        response = self.client.get(self.url_liste, {'en_stock': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for p in response.data['results']:
            self.assertGreater(p['stock'], 0)

    def test_filtre_categorie_slug(self):
        """Le filtre categorie_slug retourne les produits de cette catégorie."""
        autre_cat = Categorie.objects.create(nom='Autre Catégorie')
        creer_produit(self.vendeur, autre_cat, nom='Produit Autre Cat')

        response = self.client.get(self.url_liste, {'categorie_slug': self.categorie.slug})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        noms = [p['nom'] for p in response.data['results']]
        self.assertIn('Smartphone Test', noms)
        self.assertNotIn('Produit Autre Cat', noms)

    def test_recherche_par_nom(self):
        """Le paramètre search filtre par nom."""
        response = self.client.get(self.url_liste, {'search': 'Smartphone'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['count'], 0)

    def test_tri_par_prix(self):
        """Le paramètre ordering=prix trie les résultats."""
        creer_produit(self.vendeur, self.categorie, nom='Peu Cher', prix=Decimal('10000.00'))
        response = self.client.get(self.url_liste, {'ordering': 'prix'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        prix = [Decimal(p['prix']) for p in response.data['results']]
        self.assertEqual(prix, sorted(prix))

    # ── Action en vedette ─────────────────────────────────────

    def test_endpoint_en_vedette(self):
        """GET /api/produits/en_vedette/ retourne les produits en vedette."""
        creer_produit(self.vendeur, self.categorie, nom='Vedette', en_vedette=True)
        response = self.client.get('/api/produits/en_vedette/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)