"""
HooYia Market — users/tests.py

Tests unitaires et d'intégration pour l'app users.
On teste :
  - La création des modèles
  - Les signals
  - Les endpoints API
  - Les permissions
"""
from django.test import TestCase
from django.urls import reverse
from django.core import mail
from rest_framework.test import APITestCase
from rest_framework import status
from .models import CustomUser, AdresseLivraison, TokenVerificationEmail


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle CustomUser
# ═══════════════════════════════════════════════════════════════

class CustomUserModelTest(TestCase):

    def setUp(self):
        """
        setUp est exécuté avant chaque test.
        On crée un utilisateur de base réutilisable.
        """
        self.user = CustomUser.objects.create_user(
            email    = 'test@hooyia.com',
            username = 'testuser',
            password = 'TestPassword123!',
            nom      = 'Dupont',
            prenom   = 'Jean'
        )

    def test_creation_utilisateur(self):
        """Un utilisateur créé doit avoir les bons attributs"""
        self.assertEqual(self.user.email, 'test@hooyia.com')
        self.assertEqual(self.user.username, 'testuser')
        # Le compte doit être inactif par défaut (vérification email requise)
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.is_admin)
        self.assertFalse(self.user.is_vendeur)

    def test_mot_de_passe_hache(self):
        """Le mot de passe ne doit jamais être stocké en clair"""
        self.assertNotEqual(self.user.password, 'TestPassword123!')
        self.assertTrue(self.user.check_password('TestPassword123!'))

    def test_get_full_name(self):
        """get_full_name() doit retourner 'Prénom Nom'"""
        self.assertEqual(self.user.get_full_name(), 'Jean Dupont')

    def test_get_short_name(self):
        """get_short_name() doit retourner le prénom"""
        self.assertEqual(self.user.get_short_name(), 'Jean')

    def test_creation_superuser(self):
        """Un superuser doit avoir is_staff et is_superuser à True"""
        admin = CustomUser.objects.create_superuser(
            email    = 'admin@hooyia.com',
            username = 'admin',
            password = 'AdminPass123!'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.is_active)

    def test_email_obligatoire(self):
        """La création sans email doit lever une erreur"""
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(
                email    = '',
                username = 'nomail',
                password = 'Test123!'
            )

    def test_str(self):
        """__str__ doit retourner username (email)"""
        self.assertEqual(
            str(self.user),
            'testuser (test@hooyia.com)'
        )


# ═══════════════════════════════════════════════════════════════
# TESTS — Signal : création token + email de vérification
# ═══════════════════════════════════════════════════════════════

class SignalUserTest(TestCase):

    def test_token_cree_apres_inscription(self):
        """Un token de vérification doit être créé automatiquement"""
        user = CustomUser.objects.create_user(
            email    = 'signal@hooyia.com',
            username = 'signaluser',
            password = 'Signal123!'
        )
        # Le signal doit avoir créé un token
        self.assertTrue(
            TokenVerificationEmail.objects.filter(utilisateur=user).exists()
        )

    def test_email_envoye_apres_inscription(self):
        """Un email de vérification doit être envoyé après inscription"""
        CustomUser.objects.create_user(
            email    = 'email@hooyia.com',
            username = 'emailuser',
            password = 'Email123!'
        )
        # En mode test, les emails sont capturés dans mail.outbox
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Activez votre compte', mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ['email@hooyia.com'])

    # def test_panier_cree_apres_inscription(self):
    #     """Un panier vide doit être créé automatiquement"""
    #     from apps.cart.models import Panier
    #     user = CustomUser.objects.create_user(
    #         email    = 'panier@hooyia.com',
    #         username = 'panieruser',
    #         password = 'Panier123!'
    #     )
    #     self.assertTrue(
    #         Panier.objects.filter(utilisateur=user).exists()
    #     )


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle AdresseLivraison
# ═══════════════════════════════════════════════════════════════

class AdresseLivraisonTest(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email    = 'adresse@hooyia.com',
            username = 'adresseuser',
            password = 'Adresse123!'
        )

    def test_creation_adresse(self):
        """Une adresse doit être correctement créée"""
        adresse = AdresseLivraison.objects.create(
            utilisateur = self.user,
            nom_complet = 'Jean Dupont',
            telephone   = '+237 612345678',
            adresse     = 'Rue de la Paix',
            ville       = 'Yaoundé',
            region      = 'Centre',
            pays        = 'Cameroun'
        )
        self.assertEqual(adresse.ville, 'Yaoundé')
        self.assertEqual(adresse.utilisateur, self.user)

    def test_une_seule_adresse_par_defaut(self):
        """
        Si on marque une adresse comme défaut,
        les autres doivent perdre ce statut.
        """
        adresse1 = AdresseLivraison.objects.create(
            utilisateur = self.user,
            nom_complet = 'Jean Dupont',
            telephone   = '+237 612345678',
            adresse     = 'Rue 1',
            ville       = 'Yaoundé',
            region      = 'Centre',
            is_default  = True
        )
        adresse2 = AdresseLivraison.objects.create(
            utilisateur = self.user,
            nom_complet = 'Jean Dupont',
            telephone   = '+237 612345678',
            adresse     = 'Rue 2',
            ville       = 'Douala',
            region      = 'Littoral',
            is_default  = True  # On marque la 2ème comme défaut
        )
        # Recharge adresse1 depuis la DB
        adresse1.refresh_from_db()
        # adresse1 ne doit plus être le défaut
        self.assertFalse(adresse1.is_default)
        self.assertTrue(adresse2.is_default)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Inscription
# ═══════════════════════════════════════════════════════════════

class InscriptionAPITest(APITestCase):

    def setUp(self):
        self.url = reverse('api_inscription')
        self.data_valide = {
            'username'  : 'newuser',
            'email'     : 'new@hooyia.com',
            'nom'       : 'Kamga',
            'prenom'    : 'Paul',
            'telephone' : '+237 699887766',
            'password'  : 'SecurePass123!',
            'password2' : 'SecurePass123!'
        }

    def test_inscription_valide(self):
        """Une inscription avec des données valides doit réussir"""
        response = self.client.post(self.url, self.data_valide, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        # L'utilisateur doit exister en DB
        self.assertTrue(CustomUser.objects.filter(email='new@hooyia.com').exists())

    def test_inscription_email_duplique(self):
        """Deux inscriptions avec le même email doivent échouer"""
        self.client.post(self.url, self.data_valide, format='json')
        response = self.client.post(self.url, self.data_valide, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_passwords_differents(self):
        """Des mots de passe différents doivent échouer"""
        data = self.data_valide.copy()
        data['password2'] = 'AutrePassword123!'
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_sans_email(self):
        """Une inscription sans email doit échouer"""
        data = self.data_valide.copy()
        data['email'] = ''
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_compte_inactif_apres_inscription(self):
        """Le compte doit être inactif après inscription (vérif email requise)"""
        self.client.post(self.url, self.data_valide, format='json')
        user = CustomUser.objects.get(email='new@hooyia.com')
        self.assertFalse(user.is_active)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Connexion JWT
# ═══════════════════════════════════════════════════════════════

class ConnexionAPITest(APITestCase):

    def setUp(self):
        self.url = reverse('token_obtain')
        # Crée un utilisateur actif pour les tests
        self.user = CustomUser.objects.create_user(
            email    = 'login@hooyia.com',
            username = 'loginuser',
            password = 'Login123!'
        )
        # Active le compte manuellement (normalement fait via email)
        self.user.is_active = True
        self.user.save()

    def test_connexion_valide(self):
        """Une connexion valide doit retourner access et refresh tokens"""
        response = self.client.post(self.url, {
            'email'   : 'login@hooyia.com',
            'password': 'Login123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_connexion_mauvais_password(self):
        """Un mauvais mot de passe doit retourner 401"""
        response = self.client.post(self.url, {
            'email'   : 'login@hooyia.com',
            'password': 'MauvaisPass!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_connexion_compte_inactif(self):
        """Un compte inactif ne doit pas pouvoir se connecter"""
        user_inactif = CustomUser.objects.create_user(
            email    = 'inactif@hooyia.com',
            username = 'inactif',
            password = 'Inactif123!'
            # is_active=False par défaut
        )
        response = self.client.post(self.url, {
            'email'   : 'inactif@hooyia.com',
            'password': 'Inactif123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Profil
# ═══════════════════════════════════════════════════════════════

class ProfilAPITest(APITestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email    = 'profil@hooyia.com',
            username = 'profiluser',
            password = 'Profil123!',
            is_active = True
        )
        self.url = reverse('api_profil')

        # Obtient un token JWT pour authentifier les requêtes
        token_response = self.client.post(reverse('token_obtain'), {
            'email'   : 'profil@hooyia.com',
            'password': 'Profil123!'
        }, format='json')
        self.access_token = token_response.data['access']

        # Configure le client pour envoyer le token à chaque requête
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.access_token}'
        )

    def test_voir_profil(self):
        """GET /api/auth/profil/ doit retourner les infos de l'utilisateur"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'profil@hooyia.com')
        self.assertEqual(response.data['username'], 'profiluser')

    def test_modifier_profil(self):
        """PATCH /api/auth/profil/ doit mettre à jour les infos"""
        response = self.client.patch(self.url, {
            'nom'   : 'Mbarga',
            'prenom': 'Alain'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nom, 'Mbarga')
        self.assertEqual(self.user.prenom, 'Alain')

    def test_profil_sans_token(self):
        """Accéder au profil sans token doit retourner 401"""
        self.client.credentials()  # Supprime le token
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)