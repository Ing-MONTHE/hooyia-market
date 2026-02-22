"""
HooYia Market — orders/api_views.py
Vues API REST pour les commandes.
Retournent du JSON consommé par JavaScript.

Endpoints gérés :
  GET    /api/commandes/          → historique des commandes du client
  POST   /api/commandes/          → créer une commande depuis le panier
  GET    /api/commandes/<id>/     → détail d'une commande
  POST   /api/commandes/<id>/annuler/ → annuler une commande

Endpoints réservés aux admins :
  POST   /api/commandes/<id>/confirmer/        → confirmer manuellement
  POST   /api/commandes/<id>/mettre_en_preparation/ → passer en préparation
  POST   /api/commandes/<id>/expedier/         → marquer comme expédiée
  POST   /api/commandes/<id>/livrer/           → marquer comme livrée

Toutes les routes nécessitent d'être authentifié.
Un client ne voit QUE ses propres commandes.
"""
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from .models import Commande
from .serializers import (
    CommandeListSerializer,
    CommandeDetailSerializer,
    CreerCommandeSerializer,
)
from .services import OrderService
from apps.users.models import AdresseLivraison
from apps.users.permissions import EstAdminOuLectureSeule, EstClient


# ═══════════════════════════════════════════════════════════════
# VUE API — Liste et création des commandes
# GET  /api/commandes/ → historique du client
# POST /api/commandes/ → créer une commande depuis le panier
# ═══════════════════════════════════════════════════════════════

class CommandeListeAPIView(generics.ListAPIView):
    """
    GET : retourne l'historique des commandes de l'utilisateur connecté.
         Un admin voit toutes les commandes.
    """
    serializer_class   = CommandeListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filtre les commandes selon le rôle :
        - Admin → toutes les commandes
        - Client → uniquement ses propres commandes
        """
        user = self.request.user

        if user.is_admin:
            # Admin voit tout, avec les relations préchargées (évite N+1)
            return Commande.objects.all().select_related('client').prefetch_related('lignes')

        # Client → seulement ses commandes, triées par date décroissante
        return Commande.objects.filter(
            client=user
        ).prefetch_related('lignes').order_by('-date_creation')


class CommandeCreerAPIView(APIView):
    """
    POST /api/commandes/
    Crée une commande depuis le panier de l'utilisateur connecté.
    Délègue toute la logique à OrderService.create_from_cart().
    """
    permission_classes = [EstClient]  # Seuls les clients peuvent passer commande

    def post(self, request):
        """
        Accepte deux formats :
          Format 1 : { "adresse_id": 1, "mode_paiement": "livraison" }
          Format 2 : { "adresse_livraison_nom": "...", "adresse_livraison_ville": "...", ... }
        """
        serializer = CreerCommandeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        # ── Résolution de l'adresse ──────────────────────────────────────────
        if data.get('adresse_id'):
            # Format 1 : adresse sauvegardée
            try:
                adresse = AdresseLivraison.objects.get(
                    pk=data['adresse_id'],
                    utilisateur=request.user
                )
            except AdresseLivraison.DoesNotExist:
                return Response(
                    {'erreur': "Adresse de livraison introuvable."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Format 2 : adresse inline → on crée un objet temporaire non sauvegardé
            # (la commande fait un snapshot des champs, pas besoin de persister)
            adresse = AdresseLivraison(
                utilisateur = request.user,
                nom_complet = data.get('adresse_livraison_nom', ''),
                telephone   = data.get('adresse_livraison_telephone', ''),
                adresse     = data.get('adresse_livraison_adresse', ''),
                ville       = data.get('adresse_livraison_ville', ''),
                region      = data.get('adresse_livraison_region', ''),
                pays        = data.get('adresse_livraison_pays', 'Cameroun'),
            )

        # ── Création de la commande ──────────────────────────────────────────
        try:
            commande = OrderService.create_from_cart(
                utilisateur   = request.user,
                adresse       = adresse,
                mode_paiement = data.get('mode_paiement', 'livraison'),
                note_client   = data.get('note_client', ''),
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'erreur': msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            CommandeDetailSerializer(commande).data,
            status=status.HTTP_201_CREATED
        )


# ═══════════════════════════════════════════════════════════════
# VUE API — Détail d'une commande
# GET /api/commandes/<id>/
# ═══════════════════════════════════════════════════════════════

class CommandeDetailAPIView(generics.RetrieveAPIView):
    """
    Retourne le détail complet d'une commande.
    Un client ne peut voir que ses propres commandes.
    Un admin peut voir toutes les commandes.
    """
    serializer_class   = CommandeDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Commande.objects.all().prefetch_related('lignes', 'paiement')
        # Sécurité : filtre pour n'exposer que les commandes du client connecté
        return Commande.objects.filter(
            client=user
        ).prefetch_related('lignes', 'paiement')


# ═══════════════════════════════════════════════════════════════
# VUE API — Annuler une commande
# POST /api/commandes/<id>/annuler/
# ═══════════════════════════════════════════════════════════════

class AnnulerCommandeAPIView(APIView):
    """
    Annule une commande si les conditions sont remplies.
    Accessible au propriétaire de la commande et aux admins.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        """POST /api/commandes/<id>/annuler/"""
        try:
            # Le client ne peut annuler que ses propres commandes
            # L'admin peut annuler n'importe quelle commande
            if request.user.is_admin:
                commande = Commande.objects.get(pk=pk)
            else:
                commande = Commande.objects.get(pk=pk, client=request.user)
        except Commande.DoesNotExist:
            return Response(
                {'erreur': 'Commande introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            commande = OrderService.annuler_commande(commande, request.user)
        except ValidationError as e:
            return Response({'erreur': e.message}, status=status.HTTP_400_BAD_REQUEST)
        except TransitionNotAllowed:
            return Response(
                {'erreur': 'Cette commande ne peut pas être annulée dans son état actuel.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'message': 'Commande annulée avec succès.',
            'commande': CommandeDetailSerializer(commande).data,
        })


# ═══════════════════════════════════════════════════════════════
# VUES API — Transitions FSM réservées aux admins
# Ces vues permettent aux admins de faire avancer le statut manuellement.
# POST /api/commandes/<id>/confirmer/
# POST /api/commandes/<id>/mettre_en_preparation/
# POST /api/commandes/<id>/expedier/
# POST /api/commandes/<id>/livrer/
# ═══════════════════════════════════════════════════════════════

class TransitionCommandeAPIView(APIView):
    """
    Vue générique pour les transitions FSM réservées aux admins.
    Héritée par chaque vue de transition spécifique.
    """
    permission_classes = [permissions.IsAuthenticated, EstAdminOuLectureSeule]

    # Défini dans chaque sous-classe : nom de la méthode FSM à appeler
    transition_method = None
    message_succes    = 'Statut mis à jour.'

    def post(self, request, pk):
        try:
            commande = Commande.objects.get(pk=pk)
        except Commande.DoesNotExist:
            return Response(
                {'erreur': 'Commande introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # Appelle dynamiquement la méthode FSM (confirmer, expedier, etc.)
            methode = getattr(commande, self.transition_method)
            methode()
            commande.save()
        except TransitionNotAllowed:
            return Response(
                {'erreur': f"Transition '{self.transition_method}' non autorisée depuis le statut actuel."},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'message' : self.message_succes,
            'commande': CommandeDetailSerializer(commande).data,
        })


class ConfirmerCommandeAPIView(TransitionCommandeAPIView):
    """POST /api/commandes/<id>/confirmer/"""
    transition_method = 'confirmer'
    message_succes    = 'Commande confirmée.'


class MettreEnPreparationAPIView(TransitionCommandeAPIView):
    """POST /api/commandes/<id>/mettre_en_preparation/"""
    transition_method = 'mettre_en_preparation'
    message_succes    = 'Commande en cours de préparation.'


class ExpedierCommandeAPIView(TransitionCommandeAPIView):
    """POST /api/commandes/<id>/expedier/"""
    transition_method = 'expedier'
    message_succes    = 'Commande expédiée.'


class LivrerCommandeAPIView(TransitionCommandeAPIView):
    """POST /api/commandes/<id>/livrer/"""
    transition_method = 'livrer'
    message_succes    = 'Commande livrée.'