"""
Tests pour l'app reviews.

Couverture :
  - Modèle Avis (création, unicité, __str__, commentaire facultatif)
  - Signal post_save/post_delete (recalcul note_moyenne du produit)
  - API Avis (liste publique, créer sans achat refusé, créer après achat,
    double avis refusé, valider admin, supprimer propriétaire/autre)

Note sur creer_commande_livree :
  On crée directement en DB (sans OrderService) pour éviter de dépendre
  des tâches Celery dans les tests reviews.
"""
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.reviews.models import Avis
from apps.products.models import Produit, Categorie
from apps.orders.models import Commande, LigneCommande, Paiement

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_user(username='testuser', email='test@test.com', password='testpass123', **kwargs):
    """Crée un utilisateur actif. is_active=True obligatoire pour JWT."""
    return User.objects.create_user(
        username=username, email=email, password=password,
        is_active=True, **kwargs
    )

def creer_produit(nom='Produit Test', prix=10000):
    """Crée un produit actif avec un vendeur dédié."""
    vendeur, _ = User.objects.get_or_create(
        username='vendeur_reviews',
        defaults={'email': 'vendeur_reviews@test.com', 'is_active': True}
    )
    categorie, _ = Categorie.objects.get_or_create(nom='Catégorie Test')
    return Produit.objects.create(
        nom=nom, description='Description',
        prix=Decimal(str(prix)), stock=10,
        categorie=categorie, statut='actif', vendeur=vendeur,
    )

def creer_commande_livree(client, produit):
    """
    Crée une commande LIVREE contenant le produit.
    Création directe en DB (sans OrderService) pour éviter les dépendances Celery.
    On utilise les transitions FSM légitimes pour atteindre LIVREE.
    """
    commande = Commande.objects.create(
        client=client,
        adresse_livraison_nom='Test',
        adresse_livraison_telephone='0600000000',
        adresse_livraison_adresse='1 rue test',
        adresse_livraison_ville='Yaoundé',
        adresse_livraison_region='Centre',
        montant_total=Decimal(str(produit.prix)),
    )
    LigneCommande.objects.create(
        commande=commande, produit=produit,
        produit_nom=produit.nom, quantite=1,
        prix_unitaire=produit.prix,
    )
    Paiement.objects.create(
        commande=commande, mode='livraison', montant=commande.montant_total,
    )
    commande.confirmer()
    commande.mettre_en_preparation()
    commande.expedier()
    commande.livrer()
    commande.save()
    return commande

def get_auth_header(user):
    """Retourne le header Authorization JWT."""
    refresh = RefreshToken.for_user(user)
    return f'Bearer {refresh.access_token}'


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Avis
# ═══════════════════════════════════════════════════════════════

class AvisModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user    = creer_user()
        self.produit = creer_produit()

    def test_creation_avis(self):
        """Un avis est créé avec les valeurs par défaut correctes."""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit,
            note=4, commentaire='Très bon produit'
        )
        self.assertEqual(avis.note, 4)
        self.assertEqual(avis.commentaire, 'Très bon produit')
        self.assertFalse(avis.is_validated)   # Non validé par défaut

    def test_str_avis(self):
        """__str__ contient username, nom produit et note/5."""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=5
        )
        self.assertIn(self.user.username, str(avis))
        self.assertIn('5/5', str(avis))

    def test_commentaire_facultatif(self):
        """Un avis sans commentaire est valide (commentaire='' par défaut)."""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=3
        )
        self.assertEqual(avis.commentaire, '')

    def test_unicite_utilisateur_produit(self):
        """Un utilisateur ne peut pas laisser deux avis sur le même produit."""
        from django.db import IntegrityError
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=3)
        with self.assertRaises(IntegrityError):
            Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4)

    def test_deux_users_peuvent_noter_meme_produit(self):
        """Deux utilisateurs différents peuvent noter le même produit."""
        user2 = creer_user('user2', 'u2@test.com')
        Avis.objects.create(utilisateur=self.user,  produit=self.produit, note=4)
        Avis.objects.create(utilisateur=user2, produit=self.produit, note=5)
        self.assertEqual(Avis.objects.filter(produit=self.produit).count(), 2)

    def test_meme_user_peut_noter_deux_produits(self):
        """Un utilisateur peut noter deux produits différents."""
        produit2 = creer_produit(nom='Autre Produit')
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4)
        Avis.objects.create(utilisateur=self.user, produit=produit2,     note=3)
        self.assertEqual(Avis.objects.filter(utilisateur=self.user).count(), 2)


# ═══════════════════════════════════════════════════════════════
# TESTS — Signal : recalcul note_moyenne du produit
# ═══════════════════════════════════════════════════════════════

class AvisSignalTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user1   = creer_user('user1', 'u1@test.com')
        self.user2   = creer_user('user2', 'u2@test.com')
        self.produit = creer_produit()

    def test_avis_non_valide_ne_change_pas_note(self):
        """Un avis non validé ne doit pas modifier note_moyenne."""
        Avis.objects.create(utilisateur=self.user1, produit=self.produit, note=5)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('0.00'))

    def test_validation_avis_recalcule_note(self):
        """Valider un avis recalcule note_moyenne du produit."""
        avis = Avis.objects.create(utilisateur=self.user1, produit=self.produit, note=4)
        avis.is_validated = True
        avis.save(update_fields=['is_validated'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('4.00'))
        self.assertEqual(self.produit.nombre_avis,  1)

    def test_note_moyenne_plusieurs_avis(self):
        """La note_moyenne est la moyenne de tous les avis validés."""
        Avis.objects.create(utilisateur=self.user1, produit=self.produit, note=4, is_validated=True)
        Avis.objects.create(utilisateur=self.user2, produit=self.produit, note=2, is_validated=True)
        self.produit.refresh_from_db()
        # (4 + 2) / 2 = 3.00
        self.assertEqual(self.produit.note_moyenne, Decimal('3.00'))
        self.assertEqual(self.produit.nombre_avis,  2)

    def test_suppression_avis_recalcule_note(self):
        """Supprimer un avis validé recalcule note_moyenne."""
        avis1 = Avis.objects.create(utilisateur=self.user1, produit=self.produit, note=5, is_validated=True)
        Avis.objects.create(utilisateur=self.user2, produit=self.produit, note=3, is_validated=True)
        avis1.delete()
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('3.00'))
        self.assertEqual(self.produit.nombre_avis,  1)

    def test_invalidation_avis_recalcule_note(self):
        """Invalider un avis validé retire sa contribution à la note."""
        avis = Avis.objects.create(utilisateur=self.user1, produit=self.produit, note=5, is_validated=True)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('5.00'))

        avis.is_validated = False
        avis.save(update_fields=['is_validated'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('0.00'))
        self.assertEqual(self.produit.nombre_avis,  0)

    def test_note_zero_si_aucun_avis_valide(self):
        """note_moyenne est 0 si aucun avis validé."""
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('0.00'))


# ═══════════════════════════════════════════════════════════════
# TESTS — API Avis
# ═══════════════════════════════════════════════════════════════

class AvisAPITest(APITestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user    = creer_user()
        self.admin   = User.objects.create_superuser(
            username='admin', email='admin@test.com', password='admin123'
        )
        self.produit = creer_produit()
        self.client.credentials(HTTP_AUTHORIZATION=get_auth_header(self.user))

    def _auth_admin(self):
        self.client.credentials(HTTP_AUTHORIZATION=get_auth_header(self.admin))

    # ── Lecture ───────────────────────────────────────────────

    def test_liste_avis_accessible_sans_auth(self):
        """GET /api/avis/ est accessible sans authentification."""
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4, is_validated=True)
        self.client.credentials()
        response = self.client.get('/api/avis/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_liste_avis_filtre_par_produit(self):
        """GET /api/avis/?produit=<id> retourne seulement les avis de ce produit."""
        vendeur2, _ = User.objects.get_or_create(
            username='vendeur2', defaults={'email': 'v2@test.com', 'is_active': True}
        )
        categorie, _ = Categorie.objects.get_or_create(nom='Catégorie Test')
        autre_produit = Produit.objects.create(
            nom='Autre', description='desc', prix=Decimal('5000'),
            stock=5, categorie=categorie, statut='actif', vendeur=vendeur2
        )
        autre_user = creer_user('autre', 'autre@test.com')

        Avis.objects.create(utilisateur=self.user,  produit=self.produit,  note=4, is_validated=True)
        Avis.objects.create(utilisateur=autre_user, produit=autre_produit, note=5, is_validated=True)

        response = self.client.get(f'/api/avis/?produit={self.produit.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    # ── Création ──────────────────────────────────────────────

    def test_creer_avis_sans_achat_refuse(self):
        """POST /api/avis/ est refusé si l'utilisateur n'a pas acheté le produit → 400."""
        response = self.client.post('/api/avis/', {
            'produit': self.produit.id, 'note': 5, 'commentaire': 'Super'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_avis_apres_achat_accepte(self):
        """POST /api/avis/ est accepté si l'utilisateur a une commande LIVREE."""
        creer_commande_livree(self.user, self.produit)
        response = self.client.post('/api/avis/', {
            'produit': self.produit.id, 'note': 5, 'commentaire': 'Excellent !'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_double_avis_refuse(self):
        """POST /api/avis/ est refusé si l'utilisateur a déjà noté le produit → 400."""
        creer_commande_livree(self.user, self.produit)
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=3)
        response = self.client.post('/api/avis/', {
            'produit': self.produit.id, 'note': 5
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_avis_non_authentifie_refuse(self):
        """POST /api/avis/ sans token → 401."""
        self.client.credentials()
        response = self.client.post('/api/avis/', {
            'produit': self.produit.id, 'note': 4
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Actions admin ─────────────────────────────────────────

    def test_valider_avis_admin(self):
        """POST /api/avis/<id>/valider/ fonctionne pour un admin → 200."""
        avis = Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4)
        self._auth_admin()
        response = self.client.post(f'/api/avis/{avis.id}/valider/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        avis.refresh_from_db()
        self.assertTrue(avis.is_validated)

    def test_valider_avis_non_admin_refuse(self):
        """POST /api/avis/<id>/valider/ refusé pour un utilisateur normal → 403."""
        avis = Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4)
        response = self.client.post(f'/api/avis/{avis.id}/valider/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Suppression ───────────────────────────────────────────

    def test_supprimer_son_avis(self):
        """DELETE /api/avis/<id>/ fonctionne pour le propriétaire → 204."""
        avis = Avis.objects.create(utilisateur=self.user, produit=self.produit, note=3)
        response = self.client.delete(f'/api/avis/{avis.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Avis.objects.filter(id=avis.id).exists())

    def test_supprimer_avis_autre_refuse(self):
        """DELETE /api/avis/<id>/ refusé si l'avis appartient à un autre → 403."""
        autre_user = creer_user('autre2', 'autre2@test.com')
        avis = Avis.objects.create(
            utilisateur=autre_user, produit=self.produit, note=5, is_validated=True
        )
        response = self.client.delete(f'/api/avis/{avis.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)