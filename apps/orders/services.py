"""
HooYia Market — orders/services.py
Service métier pour la création et la gestion des commandes.

Même philosophie que cart/services.py :
  La logique métier complexe est isolée ici, hors des vues.
  Ainsi elle est réutilisable, testable indépendamment et lisible.

Flux de création d'une commande :
  1. Client clique "Passer la commande" dans le panier
  2. POST /api/commandes/ → OrderService.create_from_cart()
  3. Le service :
       a. Vérifie que le panier n'est pas vide
       b. Vérifie le stock de chaque produit (transaction.atomic)
       c. Crée la Commande avec l'adresse de livraison (snapshot)
       d. Crée une LigneCommande par article du panier
       e. Décrémente le stock de chaque produit
       f. Crée le Paiement associé
       g. Vide le panier
       h. Confirme la commande → déclenche le signal → email Celery
  4. Retourne la commande créée
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Commande, LigneCommande, Paiement
from apps.cart.models import Panier


# ═══════════════════════════════════════════════════════════════
# SERVICE — OrderService
# Point d'entrée unique pour la création et gestion des commandes.
# ═══════════════════════════════════════════════════════════════

class OrderService:
    """
    Gère toutes les opérations sur les commandes.

    Usage :
      commande = OrderService.create_from_cart(
          utilisateur=request.user,
          adresse=adresse,
          mode_paiement='livraison'
      )
    """

    @staticmethod
    @transaction.atomic
    def create_from_cart(utilisateur, adresse, mode_paiement='livraison', note_client=''):
        """
        Crée une commande complète depuis le panier de l'utilisateur.

        transaction.atomic() garantit que soit TOUT se passe bien
        (commande créée + stock décrémenté + panier vidé),
        soit RIEN n'est sauvegardé en cas d'erreur.
        C'est essentiel pour éviter les incohérences de données.

        Args:
            utilisateur   : instance CustomUser — le client qui commande
            adresse       : instance AdresseLivraison — adresse de livraison choisie
            mode_paiement : str — mode de paiement (défaut : 'livraison')
            note_client   : str — instructions de livraison optionnelles

        Returns:
            Commande : la commande créée et confirmée

        Raises:
            ValidationError : si le panier est vide ou si le stock est insuffisant
        """
        # ── Étape 1 : Récupère et vérifie le panier ──────────
        try:
            panier = utilisateur.panier
        except Panier.DoesNotExist:
            raise ValidationError("Vous n'avez pas de panier.")

        if panier.est_vide:
            raise ValidationError("Votre panier est vide.")

        # Charge tous les articles du panier avec leurs produits en une seule requête
        items = panier.items.select_related('produit').all()

        # ── Étape 2 : Vérifie le stock de chaque produit ─────
        # On vérifie AVANT de créer la commande pour éviter les commandes impossibles
        for item in items:
            if not item.produit:
                raise ValidationError(
                    "Un produit de votre panier n'est plus disponible. "
                    "Veuillez le retirer de votre panier."
                )
            if item.produit.stock < item.quantite:
                raise ValidationError(
                    f"Stock insuffisant pour « {item.produit.nom} ». "
                    f"Disponible : {item.produit.stock} — Demandé : {item.quantite}."
                )

        # ── Étape 3 : Crée la Commande ────────────────────────
        # On copie les champs de l'adresse (snapshot) pour figer l'adresse au moment t
        commande = Commande.objects.create(
            client                     = utilisateur,
            montant_total              = panier.total,
            note_client                = note_client,
            # ── Snapshot de l'adresse de livraison ────────────
            adresse_livraison_nom      = adresse.nom_complet,
            adresse_livraison_telephone = adresse.telephone,
            adresse_livraison_adresse  = adresse.adresse,
            adresse_livraison_ville    = adresse.ville,
            adresse_livraison_region   = adresse.region,
            adresse_livraison_pays     = adresse.pays,
        )

        # ── Étape 4 : Crée les lignes de commande ────────────
        # bulk_create() insère toutes les lignes en une seule requête SQL (performances)
        lignes = []
        for item in items:
            lignes.append(LigneCommande(
                commande      = commande,
                produit       = item.produit,
                produit_nom   = item.produit.nom,       # Snapshot du nom
                quantite      = item.quantite,
                prix_unitaire = item.prix_snapshot,     # Snapshot du prix
            ))
        LigneCommande.objects.bulk_create(lignes)

        # ── Étape 5 : Décrémente le stock des produits ────────
        for item in items:
            item.produit.stock -= item.quantite
            # update_fields = ne met à jour que ces champs (évite les effets de bord)
            item.produit.save(update_fields=['stock', 'statut'])

        # ── Étape 6 : Crée le Paiement ───────────────────────
        Paiement.objects.create(
            commande = commande,
            mode     = mode_paiement,
            montant  = commande.montant_total,
            # Statut en attente → sera mis à jour quand le paiement est confirmé
        )

        # ── Étape 7 : Vide le panier ─────────────────────────
        panier.vider()

        # ── Étape 8 : Confirme la commande ───────────────────
        # La transition FSM confirmer() déclenche le signal post_save
        # → orders/signals.py → Celery → email de confirmation
        commande.confirmer()
        commande.save()

        return commande

    @staticmethod
    @transaction.atomic
    def annuler_commande(commande, utilisateur):
        """
        Annule une commande si les conditions sont remplies.

        Vérifie que :
          - L'utilisateur est le propriétaire de la commande ou un admin
          - La commande n'est pas déjà livrée ou annulée (vérifié par FSM)

        Args:
            commande    : instance Commande à annuler
            utilisateur : instance CustomUser qui demande l'annulation

        Returns:
            Commande : la commande annulée

        Raises:
            ValidationError : si l'utilisateur n'est pas autorisé
                              ou si la commande ne peut pas être annulée
        """
        # Vérifie que l'utilisateur est propriétaire ou admin
        if commande.client != utilisateur and not utilisateur.is_admin:
            raise ValidationError("Vous n'êtes pas autorisé à annuler cette commande.")

        if not commande.peut_etre_annulee:
            raise ValidationError(
                "Cette commande ne peut plus être annulée "
                "(déjà livrée ou déjà annulée)."
            )

        # La transition FSM annuler() gère la remise en stock automatiquement
        commande.annuler()
        commande.save()

        return commande