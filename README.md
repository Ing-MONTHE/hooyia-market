# 🛒 HooYia Market

> Plateforme e-commerce spécialisée dans la vente d'électronique, d'équipements informatiques et d'accessoires.  
> Inspirée d'Amazon, construite avec Django et son écosystème avancé.

---

## 📋 Table des matières

1. [Présentation](#1-présentation)
2. [Stack technique](#2-stack-technique)
3. [Architecture complète](#3-architecture-complète)
4. [Installation locale](#4-installation-locale)
5. [Lancer le projet](#5-lancer-le-projet)
6. [Avancement du projet](#6-avancement-du-projet)
7. [Structure des apps](#7-structure-des-apps)
8. [API REST — Endpoints](#8-api-rest--endpoints)
9. [WebSockets](#9-websockets)
10. [Celery — Tâches asynchrones](#10-celery--tâches-asynchrones)
11. [Frontend — JavaScript & JSON](#11-frontend--javascript--json)
12. [Logo & Charte graphique](#12-logo--charte-graphique)

---

## 1. Présentation

**HooYia Market** est une plateforme e-commerce complète développée avec Django 5.
Elle implémente les concepts avancés du framework :

- **API RESTful** via Django REST Framework — données échangées en JSON
- **Chat temps réel** via WebSockets (Daphne + Django Channels)
- **Tâches asynchrones** via Celery (emails de confirmation, notifications, rappels)
- **Cache & Sessions** via Redis
- **Frontend dynamique** : HTML + TailwindCSS + JavaScript (fetch API → affichage JSON)

---

## 2. Stack technique

| Technologie | Version | Rôle |
|-------------|---------|------|
| Django | 5.0.6 | Backend principal |
| Django REST Framework | 3.15.2 | API JSON |
| SimpleJWT | 5.3.1 | Authentification par token JWT |
| Daphne | 4.1.2 | Serveur ASGI (HTTP + WebSocket) |
| Django Channels | 4.1.0 | WebSockets (chat + notifications) |
| Celery | 5.4.0 | Tâches asynchrones |
| Redis | 7.x | Cache · Sessions · Broker Celery · Channels |
| PostgreSQL | 16.x | Base de données principale |
| django-mptt | 0.16.0 | Catégories hiérarchiques |
| django-fsm | 2.8.2 | Machine à états (statuts commande) |
| Pillow | 10.3.0 | Traitement images produits |
| TailwindCSS | CDN | Framework CSS frontend |
| JavaScript | ES6+ | Fetch API → rendu JSON dynamique |

---

## 3. Architecture complète

```
hooYia_market/
│
├── config/
│   ├── __init__.py          ✅ charge Celery au démarrage
│   ├── settings.py          ✅ configuration complète locale
│   ├── urls.py              ✅ routes principales
│   ├── asgi.py              ✅ Daphne (HTTP + WebSocket)
│   ├── wsgi.py              ✅ généré par Django
│   └── celery.py            ✅ configuration Celery
│
├── apps/
│   ├── __init__.py
│   │
│   ├── users/               ✅ COMPLÈTE
│   │   ├── migrations/
│   │   ├── templates/users/
│   │   │   ├── login.html         ⏳ Phase 5
│   │   │   ├── register.html      ⏳ Phase 5
│   │   │   └── profile.html       ⏳ Phase 5
│   │   ├── models.py        ✅ CustomUser, AdresseLivraison, TokenVerificationEmail
│   │   ├── admin.py         ✅
│   │   ├── apps.py          ✅
│   │   ├── forms.py         ✅
│   │   ├── serializers.py   ✅
│   │   ├── views.py         ✅
│   │   ├── api_views.py     ✅
│   │   ├── urls.py          ✅
│   │   ├── api_urls.py      ✅
│   │   ├── permissions.py   ✅
│   │   ├── signals.py       ✅
│   │   └── tests.py         ✅
│   │
│   ├── products/            ⏳ Phase 2
│   │   ├── migrations/
│   │   ├── templates/products/
│   │   │   ├── list.html
│   │   │   └── detail.html
│   │   ├── models.py        ← Produit, Categorie, ImageProduit, MouvementStock
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── api_views.py
│   │   ├── urls.py
│   │   ├── api_urls.py
│   │   ├── managers.py
│   │   ├── filters.py
│   │   ├── signals.py
│   │   └── tests.py
│   │
│   ├── cart/                ⏳ Phase 3
│   │   ├── migrations/
│   │   ├── templates/cart/
│   │   │   └── cart.html
│   │   ├── models.py        ← Panier, PanierItem
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── api_views.py
│   │   ├── urls.py
│   │   ├── api_urls.py
│   │   ├── services.py
│   │   └── context_processors.py
│   │
│   ├── orders/              ⏳ Phase 3
│   │   ├── migrations/
│   │   ├── templates/orders/
│   │   │   ├── checkout.html
│   │   │   ├── confirm.html
│   │   │   └── history.html
│   │   ├── models.py        ← Commande (FSM), LigneCommande, Paiement
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── api_views.py
│   │   ├── urls.py
│   │   ├── api_urls.py
│   │   ├── services.py
│   │   └── signals.py
│   │
│   ├── reviews/             ⏳ Phase 4
│   │   ├── migrations/
│   │   ├── models.py        ← Avis
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── serializers.py
│   │   ├── api_views.py
│   │   ├── api_urls.py
│   │   └── signals.py
│   │
│   ├── chat/                ⏳ Phase 4
│   │   ├── migrations/
│   │   ├── templates/chat/
│   │   │   └── chat.html
│   │   ├── models.py        ← Conversation, MessageChat
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── consumers.py     ← ChatConsumer (WebSocket)
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── api_views.py
│   │   ├── urls.py
│   │   ├── api_urls.py
│   │   └── routing.py
│   │
│   ├── notifications/       ⏳ Phase 4
│   │   ├── migrations/
│   │   ├── templates/notifications/emails/
│   │   │   ├── order_confirm.html
│   │   │   └── status_update.html
│   │   ├── models.py        ← Notification, EmailAsynchrone
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── consumers.py     ← NotificationConsumer (WebSocket)
│   │   ├── tasks.py         ← tâches Celery
│   │   ├── serializers.py
│   │   ├── api_views.py
│   │   ├── api_urls.py
│   │   ├── routing.py
│   │   └── context_processors.py
│   │
│   └── audit/               ✅ COMPLÈTE
│       ├── migrations/
│       ├── models.py        ✅ AuditLog
│       ├── middleware.py    ✅ AuditLogMiddleware
│       └── admin.py         ✅
│
├── templates/               ⏳ Phase 5
│   ├── base.html
│   ├── home.html
│   └── partials/
│       ├── navbar.html
│       ├── footer.html
│       └── toast.html
│
├── static/
│   ├── img/
│   │   └── logo.svg         ✅ Logo HooYia Market
│   ├── js/                  ⏳ Phase 5
│   │   ├── api.js
│   │   ├── products.js
│   │   ├── cart.js
│   │   ├── chat.js
│   │   └── notifications.js
│   └── css/
│       └── custom.css       ⏳ Phase 5
│
├── media/
│   └── products/
│
├── venv/
├── manage.py
├── requirements.txt         ✅
├── .env                     ✅
├── .gitignore               ✅
└── README.md                ✅
```

---

## 4. Installation locale

### Prérequis
- Python 3.12+
- PostgreSQL 16+
- Redis 7+

### Étapes

```bash
# 1. Cloner le projet
git clone https://github.com/ton-compte/hooYia_market.git
cd hooYia_market

# 2. Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Créer le fichier .env
SECRET_KEY=hooYia-super-secret-key-2024!
DEBUG=True
DB_NAME=hooYia_db
DB_USER=postgres
DB_PASSWORD=ton_mot_de_passe
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://127.0.0.1:6379
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# 5. Créer la base de données
createdb hooYia_db

# 6. Appliquer les migrations
python manage.py migrate

# 7. Créer un superutilisateur
python manage.py createsuperuser
```

---

## 5. Lancer le projet

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — Serveur principal (HTTP + WebSocket)
daphne -b 127.0.0.1 -p 8000 config.asgi:application

# Terminal 3 — Worker Celery
celery -A config worker --loglevel=info

# Terminal 4 — Celery Beat (tâches planifiées)
celery -A config beat --loglevel=info

# Optionnel — Monitoring Celery
celery -A config flower --port=5555
```

### URLs disponibles

| URL | Description |
|-----|-------------|
| http://localhost:8000 | Site principal |
| http://localhost:8000/admin | Administration Django |
| http://localhost:8000/api/produits/ | API produits (JSON) |
| http://localhost:5555 | Monitoring Celery |
| ws://localhost:8000/ws/chat/\<id\>/ | WebSocket chat |
| ws://localhost:8000/ws/notifications/ | WebSocket notifications |

---

## 6. Avancement du projet

| Phase | Contenu | Statut |
|-------|---------|--------|
| **Phase 1** | Setup + config + `users` + `audit` | ✅ Complète |
| **Phase 2** | `products` | ⏳ À faire |
| **Phase 3** | `cart` + `orders` | ⏳ À faire |
| **Phase 4** | `reviews` + `chat` + `notifications` | ⏳ À faire |
| **Phase 5** | Frontend HTML + TailwindCSS + JS | ⏳ À faire |
| **Phase 6** | Tests globaux + Lancement complet | ⏳ À faire |

### Fichiers complétés ✅

| App | Fichiers créés |
|-----|---------------|
| `config/` | `settings.py`, `urls.py`, `asgi.py`, `celery.py`, `__init__.py` |
| `audit/` | `models.py`, `middleware.py`, `admin.py` |
| `users/` | `models.py`, `admin.py`, `apps.py`, `forms.py`, `serializers.py`, `views.py`, `api_views.py`, `urls.py`, `api_urls.py`, `permissions.py`, `signals.py`, `tests.py` |
| `static/img/` | `logo.svg` |
| Racine | `.env`, `.gitignore`, `requirements.txt`, `README.md` |

---

## 7. Structure des apps

### `apps.users` ✅
- **CustomUser** : modèle utilisateur personnalisé (email comme identifiant)
- **AdresseLivraison** : adresses multiples, une seule par défaut via `save()`
- **TokenVerificationEmail** : token UUID, expire après 24h
- **Signals** : création token + email vérification + panier auto à l'inscription
- **JWT** : access token (1h) + refresh token (7 jours) avec blacklist

### `apps.audit` ✅
- **AuditLog** : enregistre toutes les actions POST/PUT/PATCH/DELETE
- **AuditLogMiddleware** : s'exécute automatiquement à chaque requête

### `apps.products` ⏳ Phase 2
- **Produit** : nom, slug, description, prix, stock, catégorie, images
- **Categorie** : arbre hiérarchique via django-mptt
- **ImageProduit** : images multiples, resize automatique Pillow
- **MouvementStock** : historique entrées/sorties stock

### `apps.cart` ⏳ Phase 3
- **Panier** : lié à l'utilisateur (OneToOne)
- **PanierItem** : produit + quantité + prix snapshot
- **CartService** : add, remove, update, calculate_total

### `apps.orders` ⏳ Phase 3
- **Commande** : statuts FSM (EN_ATTENTE → LIVREE)
- **LigneCommande** : détail produit + prix snapshot
- **Paiement** : mode, statut, référence

### `apps.reviews` ⏳ Phase 4
- **Avis** : note (1-5), commentaire
- Signal → recalcul note_moyenne du produit

### `apps.chat` ⏳ Phase 4
- **Conversation** + **MessageChat**
- **ChatConsumer** WebSocket

### `apps.notifications` ⏳ Phase 4
- **Notification** + **EmailAsynchrone**
- **Tâches Celery** : emails confirmation, rappels, alertes stock

---

## 8. API REST — Endpoints

> Authentification : `Authorization: Bearer <access_token>`

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| POST | `/api/auth/register/` | Public | Inscription |
| POST | `/api/auth/token/` | Public | Connexion → JWT |
| POST | `/api/auth/token/refresh/` | Public | Renouveler token |
| POST | `/api/auth/logout/` | Auth | Déconnexion |
| GET/PUT | `/api/auth/profil/` | Auth | Voir/modifier profil |
| POST | `/api/auth/changer-password/` | Auth | Changer mot de passe |
| GET/POST | `/api/auth/adresses/` | Auth | Adresses livraison |
| DELETE | `/api/auth/adresses/<id>/` | Auth | Supprimer adresse |
| GET | `/api/produits/` | Public | Liste produits paginée |
| POST | `/api/produits/` | Vendeur | Créer produit |
| GET | `/api/produits/<id>/` | Public | Détail produit |
| PUT/PATCH | `/api/produits/<id>/` | Owner | Modifier produit |
| DELETE | `/api/produits/<id>/` | Admin | Supprimer produit |
| GET/POST | `/api/avis/` | GET: Public | Avis produits |
| GET | `/api/categories/` | Public | Arbre catégories |
| GET/POST | `/api/panier/` | Auth | Voir/modifier panier |
| PATCH/DELETE | `/api/panier/items/<id>/` | Auth | Modifier item |
| GET/POST | `/api/commandes/` | Auth | Commandes utilisateur |
| POST | `/api/commandes/<id>/annuler/` | Owner | Annuler commande |
| GET | `/api/notifications/` | Auth | Notifications |
| PATCH | `/api/notifications/<id>/lire/` | Auth | Marquer lu |

---

## 9. WebSockets

```javascript
// Chat temps réel
const chatSocket = new WebSocket(
  `ws://localhost:8000/ws/chat/${conversationId}/`
);
chatSocket.onmessage = (e) => {
  const data = JSON.parse(e.data); // { message, sender, timestamp }
  afficherMessage(data);
};
chatSocket.send(JSON.stringify({ message: 'Bonjour !' }));

// Notifications temps réel
const notifSocket = new WebSocket(
  'ws://localhost:8000/ws/notifications/'
);
notifSocket.onmessage = (e) => {
  const data = JSON.parse(e.data); // { titre, message, unread_count }
  mettreAJourBadge(data.unread_count);
};
```

---

## 10. Celery — Tâches asynchrones

| Tâche | Déclencheur | Description |
|-------|-------------|-------------|
| `send_order_confirmation_email` | Signal commande CONFIRMEE | Email HTML confirmation |
| `send_status_update_email` | Transition FSM | Email mise à jour livraison |
| `send_review_reminder` | 3j après livraison (Beat) | Rappel laisser un avis |
| `alert_low_stock` | Tous les jours à 8h (Beat) | Email admin stock faible |
| `cleanup_old_carts` | Tous les 30j (Beat) | Supprime paniers inactifs |

---

## 11. Frontend — JavaScript & JSON

```javascript
// static/js/api.js — wrapper global fetch()
async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('access_token');
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
      'X-CSRFToken': getCsrfToken(),
      ...options.headers,
    },
  });
  if (response.status === 401) {
    await refreshToken();
    return apiFetch(url, options);
  }
  return response.json();
}
```

---

## 12. Logo & Charte graphique

| Élément | Valeur |
|---------|--------|
| Fichier logo | `static/img/logo.svg` ✅ |
| Couleur principale | `#1E3A8A` (bleu marine) |
| Couleur accent | `#F97316` (orange) |
| Police | Georgia, serif |

```html
<!-- Dans navbar.html -->
<img src="{% static 'img/logo.svg' %}"
     alt="HooYia Market"
     class="h-12 w-auto">
```

| Contexte | Taille |
|----------|--------|
| Navbar | `h-12` (48px) |
| Page login/register | `h-16` (64px) |
| Email Celery | `width: 180px` |

---

> **HooYia Market** — Développé avec :  
> Django 5 · DRF · Celery · Redis · Daphne · TailwindCSS · JavaScript JSON/Fetch