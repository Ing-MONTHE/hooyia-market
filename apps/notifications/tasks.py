"""
HooYia Market — notifications/tasks.py
Tâches Celery pour les notifications (emails, rappels).
Implémentation complète prévue en Phase 4.
"""
from config.celery import app


@app.task
def send_order_confirmation_email(commande_id):
    """Envoie l'email de confirmation de commande (stub Phase 4)"""
    pass


@app.task
def send_review_reminder(commande_id):
    """Envoie le rappel pour laisser un avis (stub Phase 4)"""
    pass