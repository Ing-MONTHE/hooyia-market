"""
HooYia Market — users/tests.py
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase
from rest_framework import status

from apps.users.models import CustomUser, AdresseLivraison, TokenVerificationEmail

LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def creer_user_actif(email='actif@hooyia.com', username='actif', password='Pass123!', **kwargs):
    return CustomUser.objects.create_user(
        email=email, username=username, password=password, is_active=True, **kwargs
    )


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle CustomUser
# ═══════════════════════════════════════════════════════════════

class CustomUserModelTest(TestCase):

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='test@hooyia.com', username='testuser', password='TestPassword123!',
            nom='Dupont', prenom='Jean',
        )

    def test_creation_utilisateur(self):
        self.assertEqual(self.user.email, 'test@hooyia.com')
        self.assertFalse(self.user.is_active)
        self.assertFalse(self.user.is_admin)

    def test_mot_de_passe_hache(self):
        self.assertNotEqual(self.user.password, 'TestPassword123!')
        self.assertTrue(self.user.check_password('TestPassword123!'))

    def test_str(self):
        self.assertEqual(str(self.user), 'testuser (test@hooyia.com)')

    def test_get_full_name(self):
        self.assertEqual(self.user.get_full_name(), 'Jean Dupont')

    def test_get_full_name_sans_nom(self):
        user = creer_user_actif(email='noname@test.com', username='noname')
        self.assertEqual(user.get_full_name(), 'noname')

    def test_get_short_name(self):
        self.assertEqual(self.user.get_short_name(), 'Jean')

    def test_get_short_name_sans_prenom(self):
        user = creer_user_actif(email='nofirst@test.com', username='nofirst')
        self.assertEqual(user.get_short_name(), 'nofirst')

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_creation_superuser(self):
        admin = CustomUser.objects.create_superuser(
            email='admin@hooyia.com', username='admin', password='AdminPass123!'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_admin)
        self.assertTrue(admin.is_active)

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_email_obligatoire(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(email='', username='nomail', password='Pass!')

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_username_obligatoire(self):
        with self.assertRaises(ValueError):
            CustomUser.objects.create_user(email='x@x.com', username='', password='Pass!')

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_email_unique(self):
        with self.assertRaises(Exception):
            CustomUser.objects.create_user(
                email='test@hooyia.com', username='autre', password='Pass!'
            )


# ═══════════════════════════════════════════════════════════════
# TESTS — Token de vérification email
# ═══════════════════════════════════════════════════════════════

class TokenVerificationEmailTest(TestCase):

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='token@hooyia.com', username='tokenuser', password='Token123!'
        )
        # Le signal crée le token automatiquement
        self.token = TokenVerificationEmail.objects.get(utilisateur=self.user)

    def test_token_non_expire(self):
        self.assertFalse(self.token.est_expire())

    def test_token_expire(self):
        TokenVerificationEmail.objects.filter(pk=self.token.pk).update(
            date_creation=timezone.now() - timedelta(hours=25)
        )
        self.token.refresh_from_db()
        self.assertTrue(self.token.est_expire())

    def test_str_token(self):
        self.assertIn('token@hooyia.com', str(self.token))


# ═══════════════════════════════════════════════════════════════
# TESTS — Signals
# ═══════════════════════════════════════════════════════════════

class SignalUserTest(TestCase):

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_token_cree_apres_inscription(self):
        user = CustomUser.objects.create_user(
            email='signal@hooyia.com', username='signaluser', password='Signal123!'
        )
        self.assertTrue(TokenVerificationEmail.objects.filter(utilisateur=user).exists())

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_email_envoye_apres_inscription(self):
        CustomUser.objects.create_user(
            email='email@hooyia.com', username='emailuser', password='Email123!'
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Activez', mail.outbox[0].subject)
        self.assertIn('email@hooyia.com', mail.outbox[0].to)

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_panier_cree_apres_inscription(self):
        from apps.cart.models import Panier
        user = CustomUser.objects.create_user(
            email='panier@hooyia.com', username='panieruser', password='Panier123!'
        )
        self.assertTrue(Panier.objects.filter(utilisateur=user).exists())

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_token_unique_par_user(self):
        user = CustomUser.objects.create_user(
            email='unique@hooyia.com', username='uniqueuser', password='Unique123!'
        )
        count = TokenVerificationEmail.objects.filter(utilisateur=user).count()
        self.assertEqual(count, 1)


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle AdresseLivraison
# ═══════════════════════════════════════════════════════════════

class AdresseLivraisonTest(TestCase):

    def setUp(self):
        self.user = creer_user_actif(email='adresse@hooyia.com', username='adresseuser')

    def _creer_adresse(self, ville='Yaoundé', region='Centre', is_default=False):
        return AdresseLivraison.objects.create(
            utilisateur=self.user, nom_complet='Jean Dupont',
            telephone='+237 612345678', adresse='Rue de la Paix',
            ville=ville, region=region, pays='Cameroun', is_default=is_default,
        )

    def test_creation_adresse(self):
        adresse = self._creer_adresse()
        self.assertEqual(adresse.ville, 'Yaoundé')
        self.assertEqual(adresse.utilisateur, self.user)

    def test_str_adresse(self):
        adresse = self._creer_adresse()
        self.assertIn('Jean Dupont', str(adresse))

    def test_une_seule_adresse_par_defaut(self):
        adresse1 = self._creer_adresse(is_default=True)
        adresse2 = self._creer_adresse(ville='Douala', region='Littoral', is_default=True)
        adresse1.refresh_from_db()
        self.assertFalse(adresse1.is_default)
        self.assertTrue(adresse2.is_default)

    def test_adresses_differents_users_independantes(self):
        other_user = creer_user_actif(email='other@hooyia.com', username='otheruser')
        adresse_user1 = self._creer_adresse(is_default=True)
        adresse_user2 = AdresseLivraison.objects.create(
            utilisateur=other_user, nom_complet='Alice', telephone='000',
            adresse='Rue B', ville='Douala', region='Littoral', is_default=True,
        )
        adresse_user1.refresh_from_db()
        self.assertTrue(adresse_user1.is_default)
        self.assertTrue(adresse_user2.is_default)

    def test_plusieurs_adresses_non_defaut(self):
        a1 = self._creer_adresse(ville='Yaoundé')
        a2 = self._creer_adresse(ville='Douala', region='Littoral')
        self.assertFalse(a1.is_default)
        self.assertFalse(a2.is_default)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Inscription
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND=LOCMEM)
class InscriptionAPITest(APITestCase):

    def setUp(self):
        self.url = reverse('api_inscription')
        self.data_valide = {
            'username': 'newuser', 'email': 'new@hooyia.com',
            'nom': 'Kamga', 'prenom': 'Paul', 'telephone': '+237 699887766',
            'password': 'SecurePass123!', 'password2': 'SecurePass123!',
        }

    def test_inscription_valide(self):
        response = self.client.post(self.url, self.data_valide, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomUser.objects.filter(email='new@hooyia.com').exists())

    def test_compte_inactif_apres_inscription(self):
        self.client.post(self.url, self.data_valide, format='json')
        user = CustomUser.objects.get(email='new@hooyia.com')
        self.assertFalse(user.is_active)

    def test_inscription_email_duplique(self):
        self.client.post(self.url, self.data_valide, format='json')
        response = self.client.post(self.url, self.data_valide, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_passwords_differents(self):
        data = {**self.data_valide, 'password2': 'AutrePassword123!'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_sans_email(self):
        data = {**self.data_valide, 'email': ''}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscription_email_invalide(self):
        data = {**self.data_valide, 'email': 'pasunemail'}
        response = self.client.post(self.url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Connexion JWT
# ═══════════════════════════════════════════════════════════════

class ConnexionAPITest(APITestCase):

    def setUp(self):
        self.url = reverse('token_obtain')
        self.user = creer_user_actif(
            email='login@hooyia.com', username='loginuser', password='Login123!'
        )

    def test_connexion_valide(self):
        response = self.client.post(self.url, {
            'email': 'login@hooyia.com', 'password': 'Login123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access',  response.data)
        self.assertIn('refresh', response.data)

    def test_connexion_mauvais_password(self):
        response = self.client.post(self.url, {
            'email': 'login@hooyia.com', 'password': 'MauvaisPass!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_connexion_email_inexistant(self):
        response = self.client.post(self.url, {
            'email': 'inconnu@hooyia.com', 'password': 'Login123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMAIL_BACKEND=LOCMEM)
    def test_connexion_compte_inactif(self):
        CustomUser.objects.create_user(
            email='inactif@hooyia.com', username='inactif', password='Inactif123!'
        )
        response = self.client.post(self.url, {
            'email': 'inactif@hooyia.com', 'password': 'Inactif123!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Profil
# ═══════════════════════════════════════════════════════════════

class ProfilAPITest(APITestCase):

    def setUp(self):
        self.user = creer_user_actif(
            email='profil@hooyia.com', username='profiluser', password='Profil123!'
        )
        self.url = reverse('api_profil')
        token_resp = self.client.post(reverse('token_obtain'), {
            'email': 'profil@hooyia.com', 'password': 'Profil123!'
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token_resp.data["access"]}')

    def test_voir_profil(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'],    'profil@hooyia.com')
        self.assertEqual(response.data['username'], 'profiluser')

    def test_modifier_profil_patch(self):
        response = self.client.patch(self.url, {'nom': 'Mbarga', 'prenom': 'Alain'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nom,    'Mbarga')
        self.assertEqual(self.user.prenom, 'Alain')

    def test_profil_sans_token(self):
        self.client.credentials()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profil_token_invalide(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer tokenbidon')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)