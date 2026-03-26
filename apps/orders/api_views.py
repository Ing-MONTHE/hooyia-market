"""
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
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _l
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

        Paramètres GET supportés :
          ?statut=confirmee  → filtrer par statut FSM
          ?search=xxx        → recherche par référence ou nom client
        """
        user   = self.request.user
        statut = self.request.query_params.get('statut', '')
        search = self.request.query_params.get('search', '')

        if user.is_admin:
            qs = Commande.objects.all().select_related('client').prefetch_related('lignes', 'paiement')
        else:
            qs = Commande.objects.filter(client=user).prefetch_related('lignes', 'paiement')

        if statut:
            qs = qs.filter(statut=statut)

        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(reference__icontains=search) |
                Q(client__nom__icontains=search) |
                Q(client__prenom__icontains=search) |
                Q(client__username__icontains=search)
            )

        return qs.order_by('-date_creation')


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
                    {'erreur': _("Adresse de livraison introuvable.")},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Format 2 : adresse inline → on la sauvegarde en DB pour réutilisation future
            # Si une adresse identique existe déjà pour cet utilisateur, on la réutilise
            adresse, created = AdresseLivraison.objects.get_or_create(
                utilisateur = request.user,
                adresse     = data.get('adresse_livraison_adresse', ''),
                ville       = data.get('adresse_livraison_ville', ''),
                region      = data.get('adresse_livraison_region', ''),
                pays        = data.get('adresse_livraison_pays', 'Cameroun'),
                defaults={
                    'nom_complet': data.get('adresse_livraison_nom', ''),
                    'telephone'  : data.get('adresse_livraison_telephone', ''),
                }
            )

        # ── Création de la commande ──────────────────────────────────────────
        try:
            commande = OrderService.create_from_cart(
                utilisateur        = request.user,
                adresse            = adresse,
                mode_paiement      = data.get('mode_paiement'),
                telephone_paiement = data.get('telephone_paiement', ''),
                note_client        = data.get('note_client', ''),
            )
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            return Response({'erreur': msg}, status=status.HTTP_400_BAD_REQUEST)

        # ── Initialisation du paiement PayUnit ───────────────────────────────
        try:
            from .payment_service import PayUnitService, PayUnitError
            result = PayUnitService.initialize(commande.paiement, request)
            authorization_url = result['authorization_url']
        except PayUnitError as e:
            OrderService.annuler_commande(commande, request.user)
            return Response({'erreur': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'commande':          CommandeDetailSerializer(commande).data,
            'authorization_url': authorization_url,
        }, status=status.HTTP_201_CREATED)


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
                {'erreur': _('Commande introuvable.')},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            commande = OrderService.annuler_commande(commande, request.user)
        except ValidationError as e:
            return Response({'erreur': e.message}, status=status.HTTP_400_BAD_REQUEST)
        except TransitionNotAllowed:
            return Response(
                {'erreur': _('Cette commande ne peut pas être annulée dans son état actuel.')},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'message': _('Commande annulée avec succès.'),
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
    message_succes    = _l('Statut mis à jour.')

    def post(self, request, pk):
        try:
            commande = Commande.objects.get(pk=pk)
        except Commande.DoesNotExist:
            return Response(
                {'erreur': _('Commande introuvable.')},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            methode = getattr(commande, self.transition_method)
            methode()
            commande.save()
        except TransitionNotAllowed:
            return Response(
                {'erreur': _("Transition '%(t)s' non autorisée depuis le statut actuel.") % {'t': self.transition_method}},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            'message' : self.message_succes,
            'commande': CommandeDetailSerializer(commande).data,
        })


class ConfirmerCommandeAPIView(TransitionCommandeAPIView):
    transition_method = 'confirmer'
    message_succes    = _l('Commande confirmée.')


class MettreEnPreparationAPIView(TransitionCommandeAPIView):
    transition_method = 'mettre_en_preparation'
    message_succes    = _l('Commande en cours de préparation.')


class ExpedierCommandeAPIView(TransitionCommandeAPIView):
    transition_method = 'expedier'
    message_succes    = _l('Commande expédiée.')


class LivrerCommandeAPIView(TransitionCommandeAPIView):
    transition_method = 'livrer'
    message_succes    = _l('Commande livrée.')

# ═══════════════════════════════════════════════════════════════
# VUE API — Statut du paiement d'une commande
# GET /api/commandes/<ref>/paiement-statut/
# ═══════════════════════════════════════════════════════════════

class PaiementStatutAPIView(APIView):
    """
    Retourne le statut actuel du paiement d'une commande.

    Utilisé par le frontend pour poller le statut après redirection
    depuis PayUnit (le client revient sur le site après avoir payé).

    Le frontend appelle cet endpoint toutes les 3 secondes jusqu'à
    obtenir 'reussi' ou 'echoue'.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, ref):
        """GET /api/commandes/<ref>/paiement-statut/"""
        import uuid
        try:
            uuid.UUID(str(ref))
            commande = Commande.objects.get(reference=ref, client=request.user)
        except (Commande.DoesNotExist, ValueError):
            return Response({'erreur': 'Commande introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            paiement = commande.paiement
        except Exception:
            return Response({'erreur': 'Paiement introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'statut':           paiement.statut,
            'statut_commande':  commande.statut,
            'reference':        str(commande.reference),
        })