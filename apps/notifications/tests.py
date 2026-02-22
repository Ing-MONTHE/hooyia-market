"""
HooYia Market — notifications/tests.py
Tests pour l'app notifications.

Couverture :
  - Tests modèles : Notification, EmailAsynchrone
  - Tests API     : liste, filtre non lues, marquer lue, tout lire
  - Tests Celery  : tâches mockées (send_order_confirmation_email, send_review_reminder,
                    send_status_update_email, alert_low_stock, cleanup_old_carts)
  - Tests WebSocket : connexion, réception notification, rejet non authentifié
"""
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Notification, EmailAsynchrone

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def creer_user(username='user1', email='user1@test.com'):
    """Crée un utilisateur actif pour les tests."""
    return User.objects.create_user(
        username=username, email=email,
        password='testpass123', is_active=True,
    )

def creer_admin(username='admin', email='admin@test.com'):
    """Crée un administrateur actif pour les tests."""
    return User.objects.create_user(
        username=username, email=email,
        password='admin123', is_active=True,
        is_staff=True, is_admin=True,
    )

def get_jwt_header(user):
    """Retourne le header Authorization JWT pour un utilisateur."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return f'Bearer {refresh.access_token}'

def creer_notification(user, titre='Test', is_read=False, type_notif='systeme'):
    """Crée une notification de test."""
    return Notification.objects.create(
        utilisateur=user,
        titre=titre,
        message='Message de test',
        type_notif=type_notif,
        is_read=is_read,
    )


# ═══════════════════════════════════════════════════════════════
# TESTS MODÈLE — Notification
# ═══════════════════════════════════════════════════════════════

class NotificationModelTest(TestCase):
    """Tests du modèle Notification."""

    def setUp(self):
        self.user = creer_user()

    def test_creation_notification(self):
        """Une notification est créée avec is_read=False par défaut."""
        notif = Notification.objects.create(
            utilisateur=self.user,
            titre="Commande confirmée",
            message="Votre commande est confirmée",
            type_notif='commande',
        )
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.type_notif, 'commande')
        self.assertIsNotNone(notif.date_creation)

    def test_str_notification(self):
        """__str__ affiche le type et le titre."""
        notif = creer_notification(self.user, titre="Test notif")
        self.assertIn('Test notif', str(notif))
        self.assertIn(self.user.username, str(notif))

    def test_type_choices(self):
        """Tous les types de notification sont valides."""
        for type_code, _ in Notification.TYPE_CHOICES:
            notif = Notification.objects.create(
                utilisateur=self.user,
                titre="Test",
                message="Test",
                type_notif=type_code,
            )
            self.assertEqual(notif.type_notif, type_code)


# ═══════════════════════════════════════════════════════════════
# TESTS MODÈLE — EmailAsynchrone
# ═══════════════════════════════════════════════════════════════

class EmailAsynchroneModelTest(TestCase):
    """Tests du modèle EmailAsynchrone."""

    def setUp(self):
        self.user = creer_user()

    def test_creation_email_log(self):
        """Un EmailAsynchrone est créé avec statut 'en_attente' par défaut."""
        log = EmailAsynchrone.objects.create(
            destinataire=self.user,
            sujet="Test email",
            corps="Corps du test",
            email_destinataire=self.user.email,
        )
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_EN_ATTENTE)
        self.assertIsNone(log.date_envoi)

    def test_str_email_log(self):
        """__str__ affiche le statut et le destinataire."""
        log = EmailAsynchrone.objects.create(
            destinataire=self.user,
            sujet="Bienvenue",
            corps="Corps",
            email_destinataire=self.user.email,
            statut=EmailAsynchrone.STATUT_ENVOYE,
        )
        self.assertIn(self.user.username, str(log))
        self.assertIn('Envoyé', str(log))


# ═══════════════════════════════════════════════════════════════
# TESTS API
# ═══════════════════════════════════════════════════════════════

class NotificationAPITest(APITestCase):
    """Tests des endpoints API des notifications."""

    def setUp(self):
        self.user  = creer_user()
        self.user2 = creer_user('user2', 'user2@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(self.user))

    def test_liste_notifications_vide(self):
        """GET /api/notifications/ retourne une liste vide."""
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_liste_notifications(self):
        """GET /api/notifications/ retourne uniquement les notifications de l'utilisateur."""
        creer_notification(self.user, 'Notif 1')
        creer_notification(self.user, 'Notif 2')
        creer_notification(self.user2, 'Notif user2')  # Ne doit pas apparaître

        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)

    def test_filtre_non_lues(self):
        """GET /api/notifications/?is_read=false retourne uniquement les non lues."""
        creer_notification(self.user, 'Non lue',  is_read=False)
        creer_notification(self.user, 'Déjà lue', is_read=True)

        response = self.client.get('/api/notifications/?is_read=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['titre'], 'Non lue')

    def test_marquer_lue(self):
        """PATCH /api/notifications/<id>/lire/ marque la notification comme lue."""
        notif = creer_notification(self.user, 'A lire')
        self.assertFalse(notif.is_read)

        response = self.client.patch(f'/api/notifications/{notif.id}/lire/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
        self.assertIn('unread_count', response.data)

    def test_marquer_lue_autre_utilisateur_refuse(self):
        """PATCH /api/notifications/<id>/lire/ est refusé pour une notif d'un autre user."""
        notif = creer_notification(self.user2, 'Notif user2')
        response = self.client.patch(f'/api/notifications/{notif.id}/lire/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tout_lire(self):
        """POST /api/notifications/tout_lire/ marque toutes les notifications comme lues."""
        creer_notification(self.user, 'Notif 1')
        creer_notification(self.user, 'Notif 2')
        creer_notification(self.user, 'Notif 3')

        response = self.client.post('/api/notifications/tout_lire/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['unread_count'], 0)

        # Vérification en DB
        non_lues = Notification.objects.filter(utilisateur=self.user, is_read=False).count()
        self.assertEqual(non_lues, 0)

    def test_acces_non_authentifie_refuse(self):
        """GET /api/notifications/ est refusé sans authentification."""
        self.client.credentials()  # Supprime l'auth
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ═══════════════════════════════════════════════════════════════
# TESTS CELERY — Tâches (mockées)
# ═══════════════════════════════════════════════════════════════

class NotificationTasksTest(TestCase):
    """
    Tests des tâches Celery en mode synchrone (CELERY_TASK_ALWAYS_EAGER).
    Les emails sont envoyés via console backend (pas de vrai SMTP).
    Les appels WebSocket sont mockés (pas de Redis en test).
    """

    def setUp(self):
        self.user  = creer_user()
        self.admin = creer_admin()

        # Crée une commande LIVREE pour les tests
        from apps.products.models import Produit, Categorie
        from apps.orders.models import Commande, LigneCommande

        categorie, _ = Categorie.objects.get_or_create(nom='Test')
        self.produit = Produit.objects.create(
            nom='Produit Test', description='desc',
            prix=Decimal('10000'), stock=10,
            statut='actif', categorie=categorie, vendeur=self.admin
        )
        self.commande = Commande.objects.create(
            client=self.user,
            adresse_livraison_nom='Test',
            adresse_livraison_telephone='0600000000',
            adresse_livraison_adresse='1 rue test',
            adresse_livraison_ville='Yaoundé',
            adresse_livraison_region='Centre',
            montant_total=Decimal('10000'),
            statut='confirmee',
        )
        LigneCommande.objects.create(
            commande=self.commande,
            produit=self.produit,
            produit_nom=self.produit.nom,
            quantite=1,
            prix_unitaire=self.produit.prix,
        )

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_send_order_confirmation_email(self, mock_ws):
        """send_order_confirmation_email crée un EmailAsynchrone et une Notification."""
        from apps.notifications.tasks import send_order_confirmation_email

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            send_order_confirmation_email(self.commande.pk)

        # Un email loggué en DB
        self.assertEqual(EmailAsynchrone.objects.filter(destinataire=self.user).count(), 1)
        log = EmailAsynchrone.objects.get(destinataire=self.user)
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)

        # Notification WebSocket diffusée
        mock_ws.assert_called_once()
        args = mock_ws.call_args[1]
        self.assertEqual(args['type_notif'], 'commande')

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_send_review_reminder(self, mock_ws):
        """send_review_reminder envoie un email de rappel avis."""
        from apps.notifications.tasks import send_review_reminder

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            send_review_reminder(self.commande.pk)

        log = EmailAsynchrone.objects.filter(destinataire=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)

        mock_ws.assert_called_once()
        args = mock_ws.call_args[1]
        self.assertEqual(args['type_notif'], 'avis')

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_send_status_update_email(self, mock_ws):
        """send_status_update_email envoie un email de mise à jour statut."""
        from apps.notifications.tasks import send_status_update_email

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            send_status_update_email(self.commande.pk)

        log = EmailAsynchrone.objects.filter(destinataire=self.user).first()
        self.assertIsNotNone(log)
        mock_ws.assert_called_once()

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_alert_low_stock(self, mock_ws):
        """alert_low_stock envoie une alerte aux admins si stock faible."""
        from apps.notifications.tasks import alert_low_stock

        # Mettre le produit en stock faible : stock <= stock_minimum + statut='actif'
        # ProduitStockFaibleManager filtre sur statut='actif' ET stock <= stock_minimum
        # Les valeurs valides pour statut sont : 'actif', 'inactif', 'epuise' (max_length=10)
        self.produit.stock = 2
        self.produit.stock_minimum = 5
        self.produit.statut = 'actif'
        self.produit.save()

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            alert_low_stock()

        # Un email envoyé à l'admin
        self.assertTrue(EmailAsynchrone.objects.filter(destinataire=self.admin).exists())

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_cleanup_old_carts(self, mock_ws):
        """cleanup_old_carts supprime les articles des paniers inactifs."""
        from apps.cart.models import Panier, PanierItem
        from django.utils import timezone
        from datetime import timedelta

        # Panier inactif depuis > 30j
        panier = Panier.objects.get(utilisateur=self.user)
        PanierItem.objects.create(
            panier=panier, produit=self.produit, quantite=1,
            prix_snapshot=self.produit.prix
        )
        # Simuler une date ancienne
        Panier.objects.filter(pk=panier.pk).update(
            date_modification=timezone.now() - timedelta(days=31)
        )

        from apps.notifications.tasks import cleanup_old_carts
        cleanup_old_carts()

        # Les articles doivent avoir été supprimés
        self.assertEqual(PanierItem.objects.filter(panier=panier).count(), 0)


# ═══════════════════════════════════════════════════════════════
# TESTS WEBSOCKET — NotificationConsumer
# ═══════════════════════════════════════════════════════════════

class NotificationWebSocketTest(TransactionTestCase):
    """
    Tests du NotificationConsumer WebSocket.
    Utilise TransactionTestCase pour éviter les problèmes de connexion DB
    en contexte async (même raison que ChatWebSocketTest).
    """

    def setUp(self):
        self.user = creer_user()

    def test_connexion_acceptee(self):
        """Un utilisateur authentifié peut se connecter au canal notifications."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from config.asgi import application

            communicator = WebsocketCommunicator(application, "/ws/notifications/")
            communicator.scope['user'] = self.user

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Doit recevoir le message 'init' avec unread_count
            response = await communicator.receive_json_from(timeout=3)
            self.assertEqual(response['type'], 'init')
            self.assertIn('unread_count', response)

            await communicator.disconnect()

        async_to_sync(_run)()

    def test_connexion_refusee_non_authentifie(self):
        """Un utilisateur non authentifié ne peut pas se connecter."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from django.contrib.auth.models import AnonymousUser
            from config.asgi import application

            communicator = WebsocketCommunicator(application, "/ws/notifications/")
            communicator.scope['user'] = AnonymousUser()

            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)

        async_to_sync(_run)()