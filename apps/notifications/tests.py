"""
Tests pour l'app notifications.

Couverture :
  - Modèle Notification (création, is_read, types)
  - Modèle EmailAsynchrone (création, statuts)
  - API Notifications (liste, filtre non lues, marquer lue, tout lire)
  - Tâches Celery (appelées directement, sans worker — email backend locmem)
  - WebSocket NotificationConsumer (connexion, rejet non authentifié)

Note sur les tâches Celery :
  On appelle les tâches directement (sans .delay()) pour les tester en synchrone.
  On mock _diffuser_notification_ws pour ne pas déclencher le WebSocket en test.
  On override EMAIL_BACKEND → locmem pour capturer les emails sans SMTP.
"""
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification, EmailAsynchrone

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_user(username='user1', email='user1@test.com'):
    return User.objects.create_user(
        username=username, email=email, password='testpass123', is_active=True,
    )

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_admin(username='admin', email='admin@test.com'):
    return User.objects.create_user(
        username=username, email=email, password='admin123',
        is_active=True, is_staff=True, is_admin=True,
    )

def get_jwt_header(user):
    refresh = RefreshToken.for_user(user)
    return f'Bearer {refresh.access_token}'

def creer_notification(user, titre='Notif Test', is_read=False, type_notif='systeme'):
    return Notification.objects.create(
        utilisateur=user, titre=titre,
        message='Message de test', type_notif=type_notif, is_read=is_read,
    )


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Notification
# ═══════════════════════════════════════════════════════════════

class NotificationModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user = creer_user()

    def test_creation_notification(self):
        """Une notification est créée avec is_read=False par défaut."""
        notif = Notification.objects.create(
            utilisateur=self.user,
            titre='Commande confirmée',
            message='Votre commande est confirmée',
            type_notif='commande',
        )
        self.assertFalse(notif.is_read)
        self.assertEqual(notif.type_notif, 'commande')
        self.assertIsNotNone(notif.date_creation)

    def test_tous_les_types_valides(self):
        """Chaque type de notification valide peut être créé."""
        for type_notif in ('commande', 'avis', 'stock', 'systeme'):
            notif = Notification.objects.create(
                utilisateur=self.user,
                titre=f'Notif {type_notif}',
                message='Test',
                type_notif=type_notif,
            )
            self.assertEqual(notif.type_notif, type_notif)

    def test_marquer_comme_lue(self):
        """On peut marquer une notification comme lue."""
        notif = creer_notification(self.user)
        notif.is_read = True
        notif.save()
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_str_notification(self):
        """__str__ est non vide et lisible."""
        notif = creer_notification(self.user, titre='Test Titre')
        self.assertGreater(len(str(notif)), 0)

    def test_plusieurs_notifications_par_user(self):
        """Un utilisateur peut avoir plusieurs notifications."""
        creer_notification(self.user, titre='Notif 1')
        creer_notification(self.user, titre='Notif 2')
        creer_notification(self.user, titre='Notif 3')
        count = Notification.objects.filter(utilisateur=self.user).count()
        self.assertEqual(count, 3)


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle EmailAsynchrone
# ═══════════════════════════════════════════════════════════════

class EmailAsynchroneModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user = creer_user()

    def test_creation_email_log(self):
        """Un log d'email est créé avec statut EN_ATTENTE par défaut."""
        log = EmailAsynchrone.objects.create(
            destinataire=self.user,
            sujet='Test email',
            corps='Corps du message test',
        )
        self.assertEqual(log.sujet, 'Test email')
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_EN_ATTENTE)

    def test_statut_envoye(self):
        """Le statut peut être mis à ENVOYE."""
        log = EmailAsynchrone.objects.create(
            destinataire=self.user,
            sujet='Test', corps='Corps',
        )
        log.statut = EmailAsynchrone.STATUT_ENVOYE
        log.save()
        log.refresh_from_db()
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)

    def test_statut_echec(self):
        """Le statut peut être mis à ECHEC."""
        log = EmailAsynchrone.objects.create(
            destinataire=self.user,
            sujet='Test', corps='Corps',
        )
        log.statut = EmailAsynchrone.STATUT_ECHEC
        log.save()
        log.refresh_from_db()
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ECHEC)


# ═══════════════════════════════════════════════════════════════
# TESTS — API Notifications
# ═══════════════════════════════════════════════════════════════

class NotificationAPITest(APITestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user = creer_user()
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(self.user))

    def test_liste_notifications(self):
        """GET /api/notifications/ retourne les notifications de l'utilisateur."""
        creer_notification(self.user, titre='Notif 1')
        creer_notification(self.user, titre='Notif 2')
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultats = response.data.get('results', response.data)
        self.assertGreaterEqual(len(resultats), 2)

    def test_liste_notifications_non_authentifie(self):
        """GET /api/notifications/ sans token → 401."""
        self.client.credentials()
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_liste_notifications_filtre_non_lues(self):
        """GET /api/notifications/?non_lues=true ne retourne que les non lues."""
        creer_notification(self.user, titre='Non lue',  is_read=False)
        creer_notification(self.user, titre='Déjà lue', is_read=True)
        response = self.client.get('/api/notifications/?non_lues=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultats = response.data.get('results', response.data)
        for notif in resultats:
            self.assertFalse(notif['is_read'])

    def test_marquer_notification_lue(self):
        """PATCH /api/notifications/<id>/lire/ marque la notification comme lue."""
        notif = creer_notification(self.user)
        response = self.client.patch(f'/api/notifications/{notif.id}/lire/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_marquer_notification_autre_user_refuse(self):
        """PATCH /api/notifications/<id>/lire/ d'un autre user → 403 ou 404."""
        autre_user = creer_user('autre', 'autre@test.com')
        notif_autre = creer_notification(autre_user)
        response = self.client.patch(f'/api/notifications/{notif_autre.id}/lire/')
        self.assertIn(response.status_code, [
            status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND
        ])

    def test_tout_lire(self):
        """POST /api/notifications/tout_lire/ marque toutes les notifs comme lues."""
        creer_notification(self.user, titre='Notif 1', is_read=False)
        creer_notification(self.user, titre='Notif 2', is_read=False)
        creer_notification(self.user, titre='Notif 3', is_read=False)
        response = self.client.post('/api/notifications/tout_lire/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        non_lues = Notification.objects.filter(utilisateur=self.user, is_read=False).count()
        self.assertEqual(non_lues, 0)

    def test_user_ne_voit_pas_notifs_autres(self):
        """Un utilisateur ne voit que ses propres notifications."""
        autre_user = creer_user('autre2', 'autre2@test.com')
        creer_notification(autre_user, titre='Notif autre')
        creer_notification(self.user,  titre='Ma notif')
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        resultats = response.data.get('results', response.data)
        for notif in resultats:
            self.assertEqual(notif['utilisateur'], self.user.id)


# ═══════════════════════════════════════════════════════════════
# TESTS — Tâches Celery (appelées directement en synchrone)
# ═══════════════════════════════════════════════════════════════

class CeleryTasksTest(TestCase):
    """
    Teste les tâches Celery en les appelant directement (sans worker).
    On mock _diffuser_notification_ws pour éviter le WebSocket en test.
    On override EMAIL_BACKEND → locmem pour ne pas avoir besoin de SMTP.
    """

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user  = creer_user()
        self.admin = creer_admin()

        # Prépare une commande LIVREE pour les tests de tâches
        from apps.products.models import Produit, Categorie
        from apps.orders.models import Commande, LigneCommande, Paiement

        self.vendeur, _ = User.objects.get_or_create(
            username='vendeur_tasks',
            defaults={'email': 'vendeur_tasks@test.com', 'is_active': True}
        )
        categorie, _ = Categorie.objects.get_or_create(nom='Test')
        self.produit = Produit.objects.create(
            nom='Produit Task', description='desc',
            prix=Decimal('50000'), stock=10,
            categorie=categorie, statut='actif', vendeur=self.vendeur,
        )
        self.commande = Commande.objects.create(
            client=self.user,
            montant_total=Decimal('50000'),
            adresse_livraison_nom='Test',
            adresse_livraison_telephone='000',
            adresse_livraison_adresse='Rue',
            adresse_livraison_ville='Yaoundé',
            adresse_livraison_region='Centre',
        )
        LigneCommande.objects.create(
            commande=self.commande, produit=self.produit,
            produit_nom=self.produit.nom, quantite=1,
            prix_unitaire=self.produit.prix,
        )
        Paiement.objects.create(
            commande=self.commande, mode='livraison', montant=self.commande.montant_total,
        )

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_order_confirmation_email(self, mock_ws):
        """send_order_confirmation_email crée un log email et une notification."""
        from apps.notifications.tasks import send_order_confirmation_email
        send_order_confirmation_email(self.commande.pk)

        log = EmailAsynchrone.objects.filter(destinataire=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)
        mock_ws.assert_called_once()
        # Vérifie que la notification est de type 'commande'
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs.get('type_notif'), 'commande')

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_review_reminder(self, mock_ws):
        """send_review_reminder crée un log email de type 'avis'."""
        from apps.notifications.tasks import send_review_reminder
        send_review_reminder(self.commande.pk)

        log = EmailAsynchrone.objects.filter(destinataire=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)
        mock_ws.assert_called_once()
        call_kwargs = mock_ws.call_args[1]
        self.assertEqual(call_kwargs.get('type_notif'), 'avis')

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_status_update_email(self, mock_ws):
        """send_status_update_email crée un log email de mise à jour statut."""
        from apps.notifications.tasks import send_status_update_email
        send_status_update_email(self.commande.pk)

        log = EmailAsynchrone.objects.filter(destinataire=self.user).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.statut, EmailAsynchrone.STATUT_ENVOYE)
        mock_ws.assert_called_once()

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_alert_low_stock(self, mock_ws):
        """alert_low_stock envoie une alerte aux admins si stock faible."""
        from apps.notifications.tasks import alert_low_stock
        # Met le produit en stock faible
        self.produit.stock        = 2
        self.produit.stock_minimum = 5
        self.produit.statut       = 'actif'
        self.produit.save()

        alert_low_stock()
        # Un email envoyé à l'admin
        self.assertTrue(
            EmailAsynchrone.objects.filter(destinataire=self.admin).exists()
        )

    @patch('apps.notifications.tasks._diffuser_notification_ws')
    def test_cleanup_old_carts(self, mock_ws):
        """cleanup_old_carts supprime les articles des paniers inactifs (>30j)."""
        from apps.cart.models import Panier, PanierItem
        from django.utils import timezone
        from datetime import timedelta

        panier = Panier.objects.get(utilisateur=self.user)
        PanierItem.objects.create(
            panier=panier, produit=self.produit,
            quantite=1, prix_snapshot=self.produit.prix,
        )
        # Simule une inactivité > 30 jours
        Panier.objects.filter(pk=panier.pk).update(
            date_modification=timezone.now() - timedelta(days=31)
        )
        from apps.notifications.tasks import cleanup_old_carts
        cleanup_old_carts()

        self.assertEqual(
            PanierItem.objects.filter(panier=panier).count(), 0
        )


# ═══════════════════════════════════════════════════════════════
# TESTS — WebSocket NotificationConsumer
# ═══════════════════════════════════════════════════════════════

class NotificationWebSocketTest(TransactionTestCase):
    """
    Tests async du NotificationConsumer.
    TransactionTestCase pour éviter les problèmes de connexion DB en async.
    """

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user = User.objects.create_user(
            username='user_ws_notif', email='ws_notif@test.com',
            password='pass', is_active=True,
        )

    def test_connexion_acceptee(self):
        """Un utilisateur authentifié peut se connecter au canal notifications."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from config.asgi import application
            communicator = WebsocketCommunicator(application, '/ws/notifications/')
            communicator.scope['user'] = self.user
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            # Le consumer envoie un message 'init' à la connexion
            response = await communicator.receive_json_from(timeout=3)
            self.assertEqual(response['type'], 'init')
            self.assertIn('unread_count', response)
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_connexion_refusee_non_authentifie(self):
        """Un utilisateur non authentifié est rejeté (code 4001)."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from django.contrib.auth.models import AnonymousUser
            from config.asgi import application
            communicator = WebsocketCommunicator(application, '/ws/notifications/')
            communicator.scope['user'] = AnonymousUser()
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)

        async_to_sync(_run)()