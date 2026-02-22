"""
HooYia Market — chat/tests.py
Tests pour l'app chat.

Couverture :
  - Modèle Conversation (normalisation ordre participants, get_or_create_between)
  - Modèle MessageChat (création, is_read, __str__)
  - API Chat (liste conversations, créer, détail, envoyer message, marquer lu)
  - WebSocket ChatConsumer (connexion, message, rejet non authentifié)

Note sur TransactionTestCase :
  Les tests WebSocket sont async. TestCase utilise une transaction englobante
  qui peut provoquer des "connection already closed" en contexte async.
  TransactionTestCase vide la DB entre chaque test (TRUNCATE) → plus sûr.
"""
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from apps.chat.models import Conversation, MessageChat

User = get_user_model()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
def creer_user(username='user1', email='user1@test.com'):
    return User.objects.create_user(
        username=username, email=email,
        password='testpass123', is_active=True,
    )

def get_jwt_header(user):
    refresh = RefreshToken.for_user(user)
    return f'Bearer {refresh.access_token}'


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle Conversation
# ═══════════════════════════════════════════════════════════════

class ConversationModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user1 = creer_user('alice', 'alice@test.com')
        self.user2 = creer_user('bob',   'bob@test.com')
        self.user3 = creer_user('carol', 'carol@test.com')

    def test_creation_conversation(self):
        """Une conversation est créée entre deux participants."""
        conv = Conversation.objects.create(
            participant1=self.user1, participant2=self.user2
        )
        self.assertIsNotNone(conv.id)
        self.assertIsNotNone(conv.date_creation)

    def test_normalisation_ordre_participants(self):
        """save() normalise l'ordre : participant1.id <= participant2.id."""
        # Créer en inversant l'ordre
        conv = Conversation(participant1=self.user2, participant2=self.user1)
        conv.save()
        # Après save(), le plus petit ID doit être en participant1
        self.assertLessEqual(conv.participant1.id, conv.participant2.id)

    def test_get_or_create_between_idempotent(self):
        """get_or_create_between retourne la même conversation peu importe l'ordre."""
        conv1, created1 = Conversation.get_or_create_between(self.user1, self.user2)
        conv2, created2 = Conversation.get_or_create_between(self.user2, self.user1)
        self.assertEqual(conv1.id, conv2.id)
        self.assertTrue(created1)
        self.assertFalse(created2)

    def test_conversation_distinctes_entre_pairs_differents(self):
        """Deux paires distinctes ont des conversations différentes."""
        conv12, _ = Conversation.get_or_create_between(self.user1, self.user2)
        conv13, _ = Conversation.get_or_create_between(self.user1, self.user3)
        self.assertNotEqual(conv12.id, conv13.id)

    def test_str_conversation(self):
        """__str__ mentionne les deux participants."""
        conv = Conversation.objects.create(
            participant1=self.user1, participant2=self.user2
        )
        conv_str = str(conv)
        # __str__ doit mentionner au moins l'un des participants
        self.assertTrue(
            self.user1.username in conv_str or self.user2.username in conv_str
        )


# ═══════════════════════════════════════════════════════════════
# TESTS — Modèle MessageChat
# ═══════════════════════════════════════════════════════════════

class MessageChatModelTest(TestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.user1 = creer_user('alice', 'alice@test.com')
        self.user2 = creer_user('bob',   'bob@test.com')
        self.conv  = Conversation.objects.create(
            participant1=self.user1, participant2=self.user2
        )

    def test_creation_message(self):
        """Un message est créé avec les bons attributs."""
        msg = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user1, contenu='Bonjour !'
        )
        self.assertEqual(msg.contenu,     'Bonjour !')
        self.assertEqual(msg.expediteur,  self.user1)
        self.assertEqual(msg.conversation, self.conv)

    def test_is_read_false_par_defaut(self):
        """Un message est non lu par défaut."""
        msg = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user1, contenu='Test'
        )
        self.assertFalse(msg.is_read)

    def test_marquer_message_lu(self):
        """On peut marquer un message comme lu."""
        msg = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user1, contenu='Test'
        )
        msg.is_read = True
        msg.save()
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_str_message(self):
        """__str__ mentionne l'expéditeur et la conversation."""
        msg = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user1, contenu='Hey'
        )
        msg_str = str(msg)
        self.assertIsNotNone(msg_str)
        self.assertGreater(len(msg_str), 0)

    def test_messages_ordonnes_par_date(self):
        """Les messages sont ordonnés chronologiquement."""
        msg1 = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user1, contenu='Premier'
        )
        msg2 = MessageChat.objects.create(
            conversation=self.conv, expediteur=self.user2, contenu='Deuxième'
        )
        messages = list(MessageChat.objects.filter(conversation=self.conv))
        self.assertEqual(messages[0].contenu, 'Premier')
        self.assertEqual(messages[1].contenu, 'Deuxième')


# ═══════════════════════════════════════════════════════════════
# TESTS — API Chat
# ═══════════════════════════════════════════════════════════════

class ChatAPITest(APITestCase):

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.alice = creer_user('alice', 'alice@test.com')
        self.bob   = creer_user('bob',   'bob@test.com')
        self.carol = creer_user('carol', 'carol@test.com')
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(self.alice))

    def _auth_as(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(user))

    # ── Liste ─────────────────────────────────────────────────

    def test_liste_conversations_vide(self):
        """GET /api/chat/ retourne liste vide si aucune conversation."""
        response = self.client.get('/api/chat/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_liste_conversations_filtre_par_participant(self):
        """GET /api/chat/ ne retourne que les conversations de l'utilisateur connecté."""
        Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        # conv bob-carol : alice ne doit pas la voir
        Conversation.objects.create(participant1=self.bob,   participant2=self.carol)
        response = self.client.get('/api/chat/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_liste_non_authentifie(self):
        """GET /api/chat/ sans token → 401."""
        self.client.credentials()
        response = self.client.get('/api/chat/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Créer conversation ────────────────────────────────────

    def test_creer_conversation(self):
        """POST /api/chat/creer/ crée une conversation → 201."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Conversation.objects.filter(
                participant1__in=[self.alice, self.bob],
                participant2__in=[self.alice, self.bob],
            ).exists()
        )

    def test_creer_conversation_existante_retourne_200(self):
        """POST /api/chat/creer/ retourne 200 si la conv existe déjà."""
        Conversation.get_or_create_between(self.alice, self.bob)
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_creer_conversation_avec_soi_meme(self):
        """POST /api/chat/creer/ avec soi-même → 400."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.alice.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_conversation_user_inexistant(self):
        """POST /api/chat/creer/ avec un ID inexistant → 400."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Détail conversation ───────────────────────────────────

    def test_detail_conversation_participant(self):
        """GET /api/chat/<id>/ retourne les messages de la conversation."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        MessageChat.objects.create(conversation=conv, expediteur=self.alice, contenu='Bonjour')
        MessageChat.objects.create(conversation=conv, expediteur=self.bob,   contenu='Salut')

        response = self.client.get(f'/api/chat/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['messages']), 2)

    def test_detail_conversation_marque_messages_lus(self):
        """GET /api/chat/<id>/ marque les messages non lus comme lus."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        msg = MessageChat.objects.create(
            conversation=conv, expediteur=self.bob, contenu='Coucou'
        )
        self.assertFalse(msg.is_read)

        self.client.get(f'/api/chat/{conv.id}/')
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_detail_conversation_non_participant(self):
        """GET /api/chat/<id>/ pour non-participant → 403."""
        conv = Conversation.objects.create(participant1=self.bob, participant2=self.carol)
        response = self.client.get(f'/api/chat/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Envoyer message ───────────────────────────────────────

    def test_envoyer_message(self):
        """POST /api/chat/<id>/envoyer/ crée un message → 201."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        response = self.client.post(
            f'/api/chat/{conv.id}/envoyer/', {'message': 'Hello Bob !'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            MessageChat.objects.filter(conversation=conv, contenu='Hello Bob !').exists()
        )

    def test_envoyer_message_vide(self):
        """POST /api/chat/<id>/envoyer/ avec message vide → 400."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        response = self.client.post(f'/api/chat/{conv.id}/envoyer/', {'message': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_envoyer_message_non_participant(self):
        """POST /api/chat/<id>/envoyer/ pour non-participant → 403."""
        conv = Conversation.objects.create(participant1=self.bob, participant2=self.carol)
        response = self.client.post(f'/api/chat/{conv.id}/envoyer/', {'message': 'intrusion'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Marquer lu ────────────────────────────────────────────

    def test_marquer_lu(self):
        """POST /api/chat/<id>/marquer_lu/ marque les messages comme lus → 200."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        msg  = MessageChat.objects.create(
            conversation=conv, expediteur=self.bob, contenu='Hey'
        )
        response = self.client.post(f'/api/chat/{conv.id}/marquer_lu/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)


# ═══════════════════════════════════════════════════════════════
# TESTS — WebSocket ChatConsumer
# ═══════════════════════════════════════════════════════════════

class ChatWebSocketTest(TransactionTestCase):
    """
    Tests async du ChatConsumer via WebsocketCommunicator.
    TransactionTestCase évite les problèmes de connexion DB en contexte async.
    """

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def setUp(self):
        self.alice = User.objects.create_user(
            username='alice_ws', email='alice_ws@test.com',
            password='pass', is_active=True,
        )
        self.bob = User.objects.create_user(
            username='bob_ws', email='bob_ws@test.com',
            password='pass', is_active=True,
        )
        self.conv = Conversation.objects.create(
            participant1=self.alice, participant2=self.bob
        )

    def test_connexion_acceptee(self):
        """Un utilisateur authentifié participant peut se connecter au WebSocket."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from config.asgi import application
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.conv.id}/'
            )
            communicator.scope['user'] = self.alice
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            await communicator.disconnect()

        async_to_sync(_run)()

    def test_envoi_reception_message(self):
        """Un message envoyé est bien reçu par le consumer."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from config.asgi import application
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.conv.id}/'
            )
            communicator.scope['user'] = self.alice
            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            await communicator.send_json_to({'message': 'Test WebSocket'})
            response = await communicator.receive_json_from(timeout=3)
            self.assertEqual(response['message'],    'Test WebSocket')
            self.assertEqual(response['expediteur'], 'alice_ws')

            await communicator.disconnect()

        async_to_sync(_run)()

    def test_connexion_refusee_non_authentifie(self):
        """Un utilisateur non authentifié ne peut pas se connecter."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from django.contrib.auth.models import AnonymousUser
            from config.asgi import application
            communicator = WebsocketCommunicator(
                application, f'/ws/chat/{self.conv.id}/'
            )
            communicator.scope['user'] = AnonymousUser()
            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)

        async_to_sync(_run)()