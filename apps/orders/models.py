"""
Gestion des commandes, lignes de commande et paiements.

Architecture :
  - Commande    : la commande principale avec machine à états (FSM)
  - LigneCommande : une ligne de la commande (produit + quantité + prix snapshot)
  - Paiement    : le paiement associé à la commande

Machine à états (FSM) via django-fsm :
  La commande suit un cycle de vie strict avec des transitions autorisées.
  On ne peut pas passer directement de EN_ATTENTE à LIVREE par exemple.
  Django-fsm vérifie ces règles automatiquement et lève une exception si
  on tente une transition interdite.

  Cycle de vie complet :
  ┌─────────────┐
  │  EN_ATTENTE │ ← état initial à la création
  └──────┬──────┘
         │ confirmer()
  ┌──────▼──────┐
  │  CONFIRMEE  │ ← signal → email de confirmation Celery
  └──────┬──────┘
         │ mettre_en_preparation()
  ┌──────▼──────────┐
  │ EN_PREPARATION  │
  └──────┬──────────┘
         │ expedier()
  ┌──────▼──────┐
  │   EXPEDIEE  │
  └──────┬──────┘
         │ livrer()
  ┌──────▼──────┐
  │   LIVREE    │ ← signal → rappel avis Celery (3j après)
  └─────────────┘

  À tout moment (sauf LIVREE) :
         │ annuler()
  ┌──────▼──────┐
  │   ANNULEE   │ → remet le stock des produits
  └─────────────┘

Notion clé — Prix snapshot :
  Comme dans le panier, les prix sont capturés au moment de la commande.
  Si le vendeur modifie les prix après, la commande garde les prix d'origine.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django_fsm import FSMField, transition
from decimal import Decimal
import uuid


# ═══════════════════════════════════════════════════════════════
# COMMANDE
# Représente une commande passée par un client.
# Son statut évolue via des transitions FSM contrôlées.
# ═══════════════════════════════════════════════════════════════

class Commande(models.Model):
    """
    La commande principale.
    Créée depuis le panier via OrderService.create_from_cart().
    Son statut est géré par django-fsm (machine à états finis).
    """

    # ── Statuts possibles ─────────────────────────────────────
    # Définis ici comme constantes pour éviter les fautes de frappe
    EN_ATTENTE      = 'en_attente'
    CONFIRMEE       = 'confirmee'
    EN_PREPARATION  = 'en_preparation'
    EXPEDIEE        = 'expediee'
    LIVREE          = 'livree'
    ANNULEE         = 'annulee'

    STATUT_CHOICES = [
        (EN_ATTENTE,     'En attente'),
        (CONFIRMEE,      'Confirmée'),
        (EN_PREPARATION, 'En préparation'),
        (EXPEDIEE,       'Expédiée'),
        (LIVREE,         'Livrée'),
        (ANNULEE,        'Annulée'),
    ]

    # ── Référence unique de la commande ───────────────────────
    # UUID généré automatiquement — affiché au client comme numéro de commande
    # Ex : "CMD-550e8400-e29b" → plus lisible qu'un simple ID numérique
    reference = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name="Référence commande"
    )

    # ── Relations ─────────────────────────────────────────────
    # Le client qui a passé la commande
    # SET_NULL : si le compte est supprimé, on garde l'historique des commandes
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='commandes',
        verbose_name="Client"
    )

    # ── Adresse de livraison (snapshot) ───────────────────────
    # On copie les champs de l'adresse plutôt que de faire une FK
    # Si le client modifie son adresse plus tard, la commande garde l'adresse d'origine
    adresse_livraison_nom      = models.CharField(max_length=150, verbose_name="Nom destinataire")
    adresse_livraison_telephone = models.CharField(max_length=20,  verbose_name="Téléphone livraison")
    adresse_livraison_adresse  = models.CharField(max_length=255, verbose_name="Adresse")
    adresse_livraison_ville    = models.CharField(max_length=100, verbose_name="Ville")
    adresse_livraison_region   = models.CharField(max_length=100, verbose_name="Région")
    adresse_livraison_pays     = models.CharField(max_length=100, default="Cameroun", verbose_name="Pays")

    # ── Montants ──────────────────────────────────────────────
    # Montant total calculé lors de la création (somme des lignes)
    montant_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Montant total (FCFA)"
    )

    # ── Statut FSM ────────────────────────────────────────────
    # FSMField = champ spécial django-fsm qui contrôle les transitions
    # protected=True → impossible de modifier le statut autrement que via les transitions
    statut = FSMField(
        default=EN_ATTENTE,
        choices=STATUT_CHOICES,
        protected=True,           # Bloque les modifications directes en DB
        verbose_name="Statut"
    )

    # ── Note du client ────────────────────────────────────────
    note_client = models.TextField(
        blank=True,
        verbose_name="Note / Instructions de livraison"
    )

    # ── Dates ─────────────────────────────────────────────────
    date_creation    = models.DateTimeField(auto_now_add=True, verbose_name="Date de commande")
    date_modification = models.DateTimeField(auto_now=True,    verbose_name="Dernière mise à jour")
    date_livraison   = models.DateTimeField(null=True, blank=True, verbose_name="Date de livraison")

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ['-date_creation']

    def __str__(self):
        return f"Commande #{str(self.reference)[:8].upper()} — {self.client}"

    @property
    def reference_courte(self):
        """Retourne les 8 premiers caractères de la référence UUID pour affichage"""
        return str(self.reference)[:8].upper()

    @property
    def peut_etre_annulee(self):
        """
        Vérifie si la commande peut encore être annulée.
        Une commande livrée ne peut plus être annulée.
        """
        return self.statut not in [self.LIVREE, self.ANNULEE]

    # ── Transitions FSM ───────────────────────────────────────
    # Chaque méthode décorée par @transition définit une transition autorisée.
    # source = statut(s) de départ autorisé(s)
    # target = statut d'arrivée
    # Django-fsm lève TransitionNotAllowed si la transition est interdite.

    @transition(field=statut, source=EN_ATTENTE, target=CONFIRMEE)
    def confirmer(self):
        """
        Confirme la commande.
        Déclenche le signal → email de confirmation via Celery (orders/signals.py).
        """
        pass  # La logique métier est dans le signal post_save

    @transition(field=statut, source=CONFIRMEE, target=EN_PREPARATION)
    def mettre_en_preparation(self):
        """Passe la commande en cours de préparation"""

    @transition(field=statut, source=EN_PREPARATION, target=EXPEDIEE)
    def expedier(self):
        """Marque la commande comme expédiée"""

    @transition(field=statut, source=EXPEDIEE, target=LIVREE)
    def livrer(self):
        """
        Marque la commande comme livrée.
        Déclenche le signal → rappel laisser un avis (3j après) via Celery.
        """
        from django.utils import timezone
        self.date_livraison = timezone.now()

    @transition(
        field=statut,
        source=[EN_ATTENTE, CONFIRMEE, EN_PREPARATION, EXPEDIEE],
        target=ANNULEE
    )
    def annuler(self):
        """
        Annule la commande et remet les produits en stock.
        Disponible depuis tous les statuts sauf LIVREE et ANNULEE.
        """
        # Remet le stock de chaque produit commandé
        for ligne in self.lignes.select_related('produit').all():
            if ligne.produit:
                ligne.produit.stock += ligne.quantite
                # update_fields évite de déclencher tous les signals du produit
                ligne.produit.save(update_fields=['stock', 'statut'])


# ═══════════════════════════════════════════════════════════════
# LIGNE DE COMMANDE
# Chaque ligne représente un produit commandé avec son prix capturé.
# Identique au concept de PanierItem mais pour une commande finalisée.
# ═══════════════════════════════════════════════════════════════

class LigneCommande(models.Model):
    """
    Une ligne d'une commande : produit + quantité + prix snapshot.

    Ces données sont figées à la création de la commande.
    Elles ne changent plus jamais, même si le produit est modifié ou supprimé.
    C'est la preuve historique de ce qui a été commandé et à quel prix.
    """

    # Lien vers la commande parente
    commande = models.ForeignKey(
        Commande,
        on_delete=models.CASCADE,
        related_name='lignes',     # commande.lignes.all() → toutes les lignes
        verbose_name="Commande"
    )

    # Le produit commandé
    # SET_NULL : si le produit est supprimé, la ligne historique est conservée
    produit = models.ForeignKey(
        'products.Produit',
        on_delete=models.SET_NULL,
        null=True,
        related_name='lignes_commande',
        verbose_name="Produit"
    )

    # Nom capturé au moment de la commande
    # Si le produit est renommé/supprimé plus tard, on garde le nom d'origine
    produit_nom = models.CharField(
        max_length=255,
        verbose_name="Nom du produit (au moment de la commande)"
    )

    # Quantité commandée
    quantite = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantité"
    )

    # Prix unitaire capturé au moment de la commande
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Prix unitaire (FCFA)"
    )

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        return f"{self.quantite}x {self.produit_nom} — Commande #{self.commande.reference_courte}"

    @property
    def sous_total(self):
        """Calcule le sous-total : quantite × prix_unitaire"""
        return self.quantite * self.prix_unitaire


# ═══════════════════════════════════════════════════════════════
# PAIEMENT
# Enregistre le paiement associé à une commande.
# Un seul paiement par commande (OneToOne).
# ═══════════════════════════════════════════════════════════════

class Paiement(models.Model):
    """
    Le paiement d'une commande.
    Enregistre le mode de paiement, le statut et la référence externe.
    Pour l'instant : paiement à la livraison uniquement.
    Prévu pour intégration Mobile Money (Orange Money, MTN MoMo) en Phase 6.
    """

    # ── Mode de paiement ──────────────────────────────────────
    class ModePaiement(models.TextChoices):
        LIVRAISON    = 'livraison',    'Paiement à la livraison'
        ORANGE_MONEY = 'orange_money', 'Orange Money'
        MTN_MOMO     = 'mtn_momo',    'MTN Mobile Money'
        CARTE        = 'carte',        'Carte bancaire'

    # ── Statut du paiement ────────────────────────────────────
    class StatutPaiement(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        REUSSI     = 'reussi',     'Réussi'
        ECHOUE     = 'echoue',     'Échoué'
        REMBOURSE  = 'rembourse',  'Remboursé'

    # Une commande n'a qu'un seul paiement (OneToOne)
    commande = models.OneToOneField(
        Commande,
        on_delete=models.CASCADE,
        related_name='paiement',
        verbose_name="Commande"
    )

    mode = models.CharField(
        max_length=20,
        choices=ModePaiement.choices,
        default=ModePaiement.LIVRAISON,
        verbose_name="Mode de paiement"
    )

    statut = models.CharField(
        max_length=15,
        choices=StatutPaiement.choices,
        default=StatutPaiement.EN_ATTENTE,
        verbose_name="Statut du paiement"
    )

    # Montant payé (peut différer du montant_total si remise appliquée)
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="Montant (FCFA)"
    )

    # Référence externe (numéro de transaction Mobile Money, etc.)
    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence externe (transaction)"
    )

    date_paiement = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date du paiement"
    )

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"

    def __str__(self):
        return f"Paiement {self.mode} — Commande #{self.commande.reference_courte} — {self.statut}"