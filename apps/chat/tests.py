"""
HooYia Market — chat/tests.py
Tests pour l'app chat.

Couverture :
  - Tests modèles : Conversation (unicité, normalisation ordre, get_or_create_between)
  - Tests modèles : MessageChat (création, is_read, __str__)
  - Tests API     : liste conversations, créer conversation, détail, envoyer message, marquer lu
  - Tests WebSocket : connexion, réception message, déconnexion (via WebsocketCommunicator)
"""
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model

from .models import Conversation, MessageChat

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

def get_jwt_header(user):
    """Retourne le header Authorization JWT pour un utilisateur."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return f'Bearer {refresh.access_token}'


# ═══════════════════════════════════════════════════════════════
# TESTS MODÈLE — Conversation
# ═══════════════════════════════════════════════════════════════

class ConversationModelTest(TestCase):
    """Tests du modèle Conversation."""

    def setUp(self):
        self.user1 = creer_user('alice', 'alice@test.com')
        self.user2 = creer_user('bob',   'bob@test.com')
        self.user3 = creer_user('carol', 'carol@test.com')

    def test_creation_conversation(self):
        """Une conversation est créée correctement entre deux utilisateurs."""
        conv = Conversation.objects.create(
            participant1=self.user1,
            participant2=self.user2
        )
        self.assertIsNotNone(conv.id)
        self.assertIsNotNone(conv.date_creation)

    def test_normalisation_ordre_participants(self):
        """
        save() normalise l'ordre : participant1.id < participant2.id.
        Peu importe l'ordre de création, la conv est toujours identique.
        """
        # Créer avec user2 en participant1 et user1 en participant2
        conv = Conversation(participant1=self.user2, participant2=self.user1)
        conv.save()

        # Après save(), l'ordre doit être normalisé (petit ID en premier)
        self.assertLessEqual(conv.participant1.id, conv.participant2.id)

    def test_get_or_create_between(self):
        """get_or_create_between retourne la même conversation quel que soit l'ordre."""
        conv1, created1 = Conversation.get_or_create_between(self.user1, self.user2)
        conv2, created2 = Conversation.get_or_create_between(self.user2, self.user1)

        # Même conversation dans les deux cas
        self.assertEqual(conv1.id, conv2.id)
        self.assertTrue(created1)
        self.assertFalse(created2)   # La 2e fois, elle existe déjà

    def test_unicite_conversation(self):
        """Impossible de créer deux conversations entre les mêmes utilisateurs."""
        from django.db import IntegrityError
        Conversation.objects.create(participant1=self.user1, participant2=self.user2)
        with self.assertRaises(IntegrityError):
            Conversation.objects.create(participant1=self.user1, participant2=self.user2)

    def test_get_autre_participant(self):
        """get_autre_participant retourne le bon interlocuteur."""
        conv = Conversation.objects.create(participant1=self.user1, participant2=self.user2)
        self.assertEqual(conv.get_autre_participant(self.user1), self.user2)
        self.assertEqual(conv.get_autre_participant(self.user2), self.user1)

    def test_str_conversation(self):
        """__str__ affiche les deux participants."""
        conv = Conversation.objects.create(participant1=self.user1, participant2=self.user2)
        self.assertIn('alice', str(conv))
        self.assertIn('bob', str(conv))


# ═══════════════════════════════════════════════════════════════
# TESTS MODÈLE — MessageChat
# ═══════════════════════════════════════════════════════════════

class MessageChatModelTest(TestCase):
    """Tests du modèle MessageChat."""

    def setUp(self):
        self.user1 = creer_user('alice', 'alice@test.com')
        self.user2 = creer_user('bob',   'bob@test.com')
        self.conv  = Conversation.objects.create(
            participant1=self.user1, participant2=self.user2
        )

    def test_creation_message(self):
        """Un message est créé avec is_read=False par défaut."""
        msg = MessageChat.objects.create(
            conversation=self.conv,
            expediteur=self.user1,
            contenu="Bonjour Bob !"
        )
        self.assertEqual(msg.contenu, "Bonjour Bob !")
        self.assertFalse(msg.is_read)
        self.assertIsNotNone(msg.date_envoi)

    def test_str_message(self):
        """__str__ affiche le nom de l'expéditeur et un aperçu du contenu."""
        msg = MessageChat.objects.create(
            conversation=self.conv,
            expediteur=self.user1,
            contenu="Salut !"
        )
        self.assertIn('alice', str(msg))
        self.assertIn('Salut', str(msg))

    def test_ordre_chronologique(self):
        """Les messages sont ordonnés par date_envoi (du plus ancien au plus récent)."""
        msg1 = MessageChat.objects.create(conversation=self.conv, expediteur=self.user1, contenu="1")
        msg2 = MessageChat.objects.create(conversation=self.conv, expediteur=self.user2, contenu="2")
        messages = list(self.conv.messages.all())
        self.assertEqual(messages[0].id, msg1.id)
        self.assertEqual(messages[1].id, msg2.id)


# ═══════════════════════════════════════════════════════════════
# TESTS API — Conversations
# ═══════════════════════════════════════════════════════════════

class ChatAPITest(APITestCase):
    """Tests des endpoints API du chat."""

    def setUp(self):
        self.alice = creer_user('alice', 'alice@test.com')
        self.bob   = creer_user('bob',   'bob@test.com')
        self.carol = creer_user('carol', 'carol@test.com')

        # Auth JWT pour alice
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(self.alice))

    def _auth_as(self, user):
        """Change l'authentification pour un autre utilisateur."""
        self.client.credentials(HTTP_AUTHORIZATION=get_jwt_header(user))

    # ── Liste des conversations ────────────────────────────────

    def test_liste_conversations_vide(self):
        """GET /api/chat/ retourne une liste vide si aucune conversation."""
        response = self.client.get('/api/chat/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)

    def test_liste_conversations_avec_conv(self):
        """GET /api/chat/ retourne uniquement les conversations de l'utilisateur."""
        # Conversation entre alice et bob
        Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        # Conversation entre bob et carol (alice n'en fait pas partie)
        Conversation.objects.create(participant1=self.bob, participant2=self.carol)

        response = self.client.get('/api/chat/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # La pagination retourne un dict : count, next, previous, results
        # Alice ne voit que SA conversation (bob-carol ne la concerne pas)
        self.assertEqual(response.data['count'], 1)

    # ── Créer une conversation ─────────────────────────────────

    def test_creer_conversation(self):
        """POST /api/chat/creer/ crée une conversation avec un autre utilisateur."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Conversation.objects.filter(
            participant1__in=[self.alice, self.bob],
            participant2__in=[self.alice, self.bob]
        ).exists())

    def test_creer_conversation_existante(self):
        """POST /api/chat/creer/ retourne 200 si la conversation existe déjà."""
        Conversation.get_or_create_between(self.alice, self.bob)
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.bob.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_creer_conversation_avec_soi_meme_refuse(self):
        """POST /api/chat/creer/ est refusé si on tente de se parler à soi-même."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': self.alice.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_creer_conversation_utilisateur_inexistant(self):
        """POST /api/chat/creer/ échoue si l'utilisateur destinataire n'existe pas."""
        response = self.client.post('/api/chat/creer/', {'utilisateur_id': 99999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── Détail d'une conversation ──────────────────────────────

    def test_detail_conversation(self):
        """GET /api/chat/<id>/ retourne les messages d'une conversation."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        MessageChat.objects.create(conversation=conv, expediteur=self.alice, contenu="Bonjour")
        MessageChat.objects.create(conversation=conv, expediteur=self.bob,   contenu="Salut")

        response = self.client.get(f'/api/chat/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['messages']), 2)

    def test_detail_conversation_marque_lus(self):
        """GET /api/chat/<id>/ marque les messages non lus comme lus."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        # Bob envoie un message → non lu pour Alice
        msg = MessageChat.objects.create(
            conversation=conv, expediteur=self.bob, contenu="Coucou"
        )
        self.assertFalse(msg.is_read)

        # Alice ouvre la conversation
        self.client.get(f'/api/chat/{conv.id}/')
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_detail_conversation_non_participant_refuse(self):
        """GET /api/chat/<id>/ est refusé si l'utilisateur n'est pas participant."""
        # Conversation entre bob et carol (alice n'en est pas membre)
        conv = Conversation.objects.create(participant1=self.bob, participant2=self.carol)
        response = self.client.get(f'/api/chat/{conv.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Envoyer un message ─────────────────────────────────────

    def test_envoyer_message(self):
        """POST /api/chat/<id>/envoyer/ crée un message dans la conversation."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        response = self.client.post(
            f'/api/chat/{conv.id}/envoyer/',
            {'message': 'Hello Bob !'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(MessageChat.objects.filter(conversation=conv, contenu='Hello Bob !').exists())

    def test_envoyer_message_vide_refuse(self):
        """POST /api/chat/<id>/envoyer/ échoue avec un message vide."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        response = self.client.post(f'/api/chat/{conv.id}/envoyer/', {'message': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_envoyer_message_non_participant_refuse(self):
        """POST /api/chat/<id>/envoyer/ est refusé si l'user n'est pas participant."""
        conv = Conversation.objects.create(participant1=self.bob, participant2=self.carol)
        response = self.client.post(f'/api/chat/{conv.id}/envoyer/', {'message': 'intrusion'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Marquer comme lu ───────────────────────────────────────

    def test_marquer_lu(self):
        """POST /api/chat/<id>/marquer_lu/ marque les messages non lus comme lus."""
        conv = Conversation.objects.create(participant1=self.alice, participant2=self.bob)
        msg  = MessageChat.objects.create(conversation=conv, expediteur=self.bob, contenu="Hey")

        response = self.client.post(f'/api/chat/{conv.id}/marquer_lu/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)


# ═══════════════════════════════════════════════════════════════
# TESTS WEBSOCKET — ChatConsumer
# ═══════════════════════════════════════════════════════════════

class ChatWebSocketTest(TransactionTestCase):
    """
    Tests du ChatConsumer WebSocket via channels.testing.WebsocketCommunicator.

    Pourquoi TransactionTestCase et non TestCase ?
      Les tests WebSocket sont async. TestCase enveloppe chaque test dans une
      transaction qui reste ouverte pendant toute la durée du test. Quand le
      premier test async se termine, Django ferme la connexion DB de cette
      transaction. Le setUp() du test suivant tente alors d'utiliser cette
      connexion fermée → "connection already closed".
      TransactionTestCase vide la DB entre chaque test (TRUNCATE) au lieu
      d'utiliser des transactions → pas de connexion fermée entre les tests.

    Pourquoi async_to_sync(self._run_test)() ?
      On ne peut pas déclarer setUp() en async dans Django TestCase.
      On utilise async_to_sync pour exécuter les coroutines WebSocket
      depuis des méthodes de test synchrones.
    """

    def setUp(self):
        """setUp synchrone : crée les objets de test nécessaires."""
        self.alice = creer_user('alice', 'alice@test.com')
        self.bob   = creer_user('bob',   'bob@test.com')
        self.conv  = Conversation.objects.create(
            participant1=self.alice, participant2=self.bob
        )

    def test_connexion_acceptee(self):
        """Un utilisateur authentifié participant peut se connecter."""
        from asgiref.sync import async_to_sync

        async def _run():
            from channels.testing import WebsocketCommunicator
            from config.asgi import application

            communicator = WebsocketCommunicator(
                application,
                f"/ws/chat/{self.conv.id}/"
            )
            # Injection directe de l'user dans le scope (contourne AuthMiddleware)
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
                application,
                f"/ws/chat/{self.conv.id}/"
            )
            communicator.scope['user'] = self.alice

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            # Envoi du message JSON
            await communicator.send_json_to({'message': 'Test WebSocket'})

            # Réception du broadcast
            response = await communicator.receive_json_from(timeout=3)
            self.assertEqual(response['message'], 'Test WebSocket')
            self.assertEqual(response['expediteur'], 'alice')

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
                application,
                f"/ws/chat/{self.conv.id}/"
            )
            communicator.scope['user'] = AnonymousUser()

            connected, code = await communicator.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)

        async_to_sync(_run)()