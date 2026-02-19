"""
HooYia Market — reviews/tests.py
Tests unitaires et d'intégration pour l'app reviews.

Couverture :
  - Tests modèle Avis (création, unicité, __str__)
  - Tests signal (recalcul note_moyenne après create/update/delete)
  - Tests serializer (validation achat obligatoire, double avis interdit)
  - Tests API (liste, créer, supprimer, actions admin valider/invalider)
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from apps.reviews.models import Avis
from apps.products.models import Produit, Categorie
from apps.orders.models import Commande, LigneCommande, Paiement

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# UTILITAIRES — Création d'objets de test
# ═══════════════════════════════════════════════════════════════

def creer_utilisateur(username='testuser', email='test@test.com', password='testpass123'):
    """Crée un utilisateur de test standard"""
    return User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

def creer_produit(nom='Produit Test', prix=10000):
    """Crée un produit de test actif avec un vendeur"""
    vendeur   = creer_utilisateur('vendeur@test.com', 'vendeur')
    categorie, _ = Categorie.objects.get_or_create(nom='Catégorie Test')
    return Produit.objects.create(
        nom=nom,
        description='Description test',
        prix=Decimal(str(prix)),
        stock=10,
        categorie=categorie,
        statut='actif',
        vendeur=vendeur    # ← champ manquant
    )

def creer_commande_livree(client, produit):
    """
    Crée une commande LIVREE contenant le produit donné.
    Simule qu'un client a acheté et reçu le produit.
    On utilise django-fsm pour parcourir les transitions légitimes.
    """
    commande = Commande.objects.create(
        client=client,
        adresse_livraison_nom='Test',
        adresse_livraison_telephone='0600000000',
        adresse_livraison_adresse='1 rue test',
        adresse_livraison_ville='Yaoundé',
        adresse_livraison_region='Centre',
        montant_total=Decimal(str(produit.prix))
    )
    LigneCommande.objects.create(
        commande=commande,
        produit=produit,
        produit_nom=produit.nom,
        quantite=1,
        prix_unitaire=produit.prix
    )
    Paiement.objects.create(
        commande=commande,
        mode='livraison',
        montant=commande.montant_total
    )
    # Parcourir les transitions FSM pour atteindre LIVREE
    commande.confirmer()
    commande.mettre_en_preparation()
    commande.expedier()
    commande.livrer()
    commande.save()
    return commande


# ═══════════════════════════════════════════════════════════════
# TESTS MODÈLE
# ═══════════════════════════════════════════════════════════════

class AvisModelTest(TestCase):
    """Tests du modèle Avis : champs, contraintes, propriétés"""

    def setUp(self):
        self.user    = creer_utilisateur()
        self.produit = creer_produit()

    def test_creation_avis(self):
        """Un avis est créé correctement avec les valeurs par défaut"""
        avis = Avis.objects.create(
            utilisateur=self.user,
            produit=self.produit,
            note=4,
            commentaire="Très bon produit"
        )
        self.assertEqual(avis.note, 4)
        self.assertEqual(avis.commentaire, "Très bon produit")
        self.assertFalse(avis.is_validated)  # False par défaut

    def test_str_avis(self):
        """__str__ affiche le bon format"""
        avis = Avis.objects.create(
            utilisateur=self.user,
            produit=self.produit,
            note=5
        )
        self.assertIn(self.user.username, str(avis))
        self.assertIn('5/5', str(avis))

    def test_unicite_utilisateur_produit(self):
        """Un utilisateur ne peut pas laisser deux avis sur le même produit"""
        from django.db import IntegrityError
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=3)
        with self.assertRaises(IntegrityError):
            Avis.objects.create(utilisateur=self.user, produit=self.produit, note=4)

    def test_commentaire_facultatif(self):
        """Un avis sans commentaire est valide"""
        avis = Avis.objects.create(
            utilisateur=self.user,
            produit=self.produit,
            note=3
            # commentaire absent → vide par défaut
        )
        self.assertEqual(avis.commentaire, '')


# ═══════════════════════════════════════════════════════════════
# TESTS SIGNAL — Recalcul note_moyenne
# ═══════════════════════════════════════════════════════════════

class AvisSignalTest(TestCase):
    """Tests du signal post_save/post_delete qui recalcule note_moyenne"""

    def setUp(self):
        self.user1   = creer_utilisateur('user1', 'u1@test.com')
        self.user2   = creer_utilisateur('user2', 'u2@test.com')
        self.produit = creer_produit()

    def test_note_moyenne_apres_creation_avis_validated(self):
        """La note_moyenne du produit est recalculée après validation d'un avis"""
        avis = Avis.objects.create(
            utilisateur=self.user1, produit=self.produit, note=4
        )
        # Pas encore validé → note_moyenne reste 0
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('0.00'))

        # Validation → le signal recalcule
        avis.is_validated = True
        avis.save(update_fields=['is_validated'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('4.00'))
        self.assertEqual(self.produit.nombre_avis, 1)

    def test_note_moyenne_plusieurs_avis(self):
        """La moyenne est correcte avec plusieurs avis validés"""
        avis1 = Avis.objects.create(
            utilisateur=self.user1, produit=self.produit, note=4, is_validated=True
        )
        avis2 = Avis.objects.create(
            utilisateur=self.user2, produit=self.produit, note=2, is_validated=True
        )
        self.produit.refresh_from_db()
        # (4 + 2) / 2 = 3.00
        self.assertEqual(self.produit.note_moyenne, Decimal('3.00'))
        self.assertEqual(self.produit.nombre_avis, 2)

    def test_note_moyenne_apres_suppression(self):
        """La note_moyenne est mise à jour après suppression d'un avis"""
        avis1 = Avis.objects.create(
            utilisateur=self.user1, produit=self.produit, note=5, is_validated=True
        )
        avis2 = Avis.objects.create(
            utilisateur=self.user2, produit=self.produit, note=3, is_validated=True
        )
        # Suppression du premier avis
        avis1.delete()
        self.produit.refresh_from_db()
        # Ne reste que la note 3
        self.assertEqual(self.produit.note_moyenne, Decimal('3.00'))
        self.assertEqual(self.produit.nombre_avis, 1)

    def test_note_moyenne_zero_si_aucun_avis_validated(self):
        """note_moyenne revient à 0 si tous les avis sont invalidés"""
        avis = Avis.objects.create(
            utilisateur=self.user1, produit=self.produit, note=5, is_validated=True
        )
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('5.00'))

        # Invalidation → note_moyenne revient à 0
        avis.is_validated = False
        avis.save(update_fields=['is_validated'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.note_moyenne, Decimal('0.00'))


# ═══════════════════════════════════════════════════════════════
# TESTS API
# ═══════════════════════════════════════════════════════════════

class AvisAPITest(APITestCase):
    """Tests des endpoints API des avis"""

    def setUp(self):
        self.user    = creer_utilisateur()
        self.admin   = User.objects.create_superuser('admin', 'admin@test.com', 'admin123')
        self.produit = creer_produit()

        # Authentification JWT
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def _auth_admin(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_liste_avis_publique(self):
        """GET /api/avis/ est accessible sans authentification"""
        Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=4, is_validated=True
        )
        self.client.credentials()  # Supprime l'auth
        response = self.client.get('/api/avis/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_liste_avis_filtre_par_produit(self):
        """GET /api/avis/?produit=<id> filtre les avis d'un produit"""
        autre_produit = creer_produit('Autre produit')
        Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=4, is_validated=True
        )
        Avis.objects.create(
            utilisateur=self.user, produit=autre_produit, note=5, is_validated=True
        )
        response = self.client.get(f'/api/avis/?produit={self.produit.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Seul l'avis du produit cible doit apparaître
        self.assertEqual(response.data['count'], 1)

    def test_creer_avis_sans_achat_refuse(self):
        """POST /api/avis/ est refusé si l'utilisateur n'a pas acheté le produit"""
        data = {'produit': self.produit.id, 'note': 5, 'commentaire': 'Super'}
        response = self.client.post('/api/avis/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_avis_apres_achat(self):
        """POST /api/avis/ est accepté si l'utilisateur a une commande LIVREE"""
        creer_commande_livree(self.user, self.produit)
        data = {'produit': self.produit.id, 'note': 5, 'commentaire': 'Excellent !'}
        response = self.client.post('/api/avis/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_double_avis_refuse(self):
        """POST /api/avis/ est refusé si l'utilisateur a déjà noté le produit"""
        creer_commande_livree(self.user, self.produit)
        Avis.objects.create(utilisateur=self.user, produit=self.produit, note=3)
        data = {'produit': self.produit.id, 'note': 5}
        response = self.client.post('/api/avis/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valider_avis_admin(self):
        """POST /api/avis/<id>/valider/ fonctionne pour un admin"""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=4
        )
        self._auth_admin()
        response = self.client.post(f'/api/avis/{avis.id}/valider/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        avis.refresh_from_db()
        self.assertTrue(avis.is_validated)

    def test_valider_avis_non_admin_refuse(self):
        """POST /api/avis/<id>/valider/ est refusé pour un utilisateur normal"""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=4
        )
        response = self.client.post(f'/api/avis/{avis.id}/valider/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_supprimer_son_avis(self):
        """DELETE /api/avis/<id>/ fonctionne pour le propriétaire de l'avis"""
        avis = Avis.objects.create(
            utilisateur=self.user, produit=self.produit, note=3
        )
        response = self.client.delete(f'/api/avis/{avis.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Avis.objects.filter(id=avis.id).exists())

    def test_supprimer_avis_autre_utilisateur_refuse(self):
        """DELETE /api/avis/<id>/ est refusé si l'avis appartient à un autre utilisateur"""
        autre_user = creer_utilisateur('autre', 'autre@test.com')
        avis = Avis.objects.create(
            utilisateur=autre_user, produit=self.produit, note=5
        )
        response = self.client.delete(f'/api/avis/{avis.id}/')
        # L'avis validé n'est pas visible par défaut si non validé, mais testons le cas
        # où l'avis est validé et appartient à un autre user
        avis.is_validated = True
        avis.save()
        response = self.client.delete(f'/api/avis/{avis.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)