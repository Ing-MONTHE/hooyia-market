"""
Management command — fix_paiements_livres

Met à jour le statut des paiements pour toutes les commandes
déjà marquées comme 'livree' mais dont le paiement est encore 'en_attente'.

Usage :
    python manage.py fix_paiements_livres
    python manage.py fix_paiements_livres --dry-run  # Aperçu sans modifier
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.orders.models import Commande, Paiement


class Command(BaseCommand):
    help = "Corrige le statut des paiements pour les commandes livrées."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les commandes affectées sans modifier la base.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        livrees = Commande.objects.filter(
            statut='livree'
        ).select_related('paiement')

        count = 0
        for c in livrees:
            try:
                p = c.paiement
                if p.statut != Paiement.StatutPaiement.REUSSI:
                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] Commande #{c.id} ({c.reference_courte}) "
                            f"— paiement statut='{p.statut}' → 'reussi'"
                        )
                    else:
                        p.statut        = Paiement.StatutPaiement.REUSSI
                        p.date_paiement = p.date_paiement or timezone.now()
                        p.save(update_fields=['statut', 'date_paiement'])
                        self.stdout.write(self.style.SUCCESS(
                            f"Commande #{c.id} ({c.reference_courte}) — paiement mis à jour."
                        ))
                    count += 1
            except Paiement.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Commande #{c.id} — pas de paiement associé."
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Commande #{c.id} — erreur : {e}"
                ))

        suffix = "(dry-run)" if dry_run else "mis à jour"
        self.stdout.write(self.style.SUCCESS(
            f"\nTotal : {count} paiement(s) {suffix}."
        ))