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
| Django | 5.2.11 | Backend principal |
| Django REST Framework | 3.16.1 | API JSON |
| SimpleJWT | 5.5.1 | Authentification par token JWT |
| Daphne | 4.2.1 | Serveur ASGI (HTTP + WebSocket) |
| Django Channels | 4.3.2 | WebSockets (chat + notifications) |
| Celery | 5.6.2 | Tâches asynchrones |
| Redis | 7.2.0 | Cache · Sessions · Broker Celery · Channels |
| PostgreSQL | 16.x | Base de données principale |
| django-mptt | 0.18.0 | Catégories hiérarchiques |
| django-fsm | 3.0.1 | Machine à états (statuts commande) |
| Pillow | 12.1.1 | Traitement images produits |
| django-celery-beat | 2.8.1 | Tâches planifiées (Beat) |
| flower | 2.0.1 | Monitoring Celery |
| TailwindCSS | CDN | Framework CSS frontend |
| JavaScript | ES6+ | Fetch API → rendu JSON dynamique |

---

## 3. Architecture complète

```
hooyia-market/
│
├── config/                              ✅ Configuration centrale
│   ├── __init__.py                      charge Celery au démarrage Django
│   ├── settings.py                      configuration complète (DB, Redis, JWT, Celery, MPTT...)
│   ├── urls.py                          routes principales (HTML + API + WebSocket)
│   ├── asgi.py                          Daphne — HTTP + WebSocket (chat + notifications)
│   ├── celery.py                        configuration Celery + Beat
│   └── wsgi.py
│
├── apps/
│   │
│   ├── audit/                           ✅ Traçabilité complète
│   │   ├── models.py                    AuditLog — IP, user, method, path, status, body
│   │   ├── middleware.py                AuditLogMiddleware — intercepte POST/PUT/PATCH/DELETE
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── views.py
│   │   └── tests.py
│   │
│   ├── users/                           ✅ Authentification & profils
│   │   ├── models.py                    CustomUser · AdresseLivraison · TokenVerificationEmail
│   │   ├── signals.py                   token email + panier auto à l'inscription
│   │   ├── forms.py                     Inscription · Connexion · Profil · Adresse
│   │   ├── serializers.py               Inscription · Profil · Adresse · ChangerMDP
│   │   ├── permissions.py               permissions custom DRF (IsOwner, IsVendeur...)
│   │   ├── views.py                     vues HTML
│   │   ├── api_views.py                 vues API JSON (JWT)
│   │   ├── urls.py                      routes HTML  /users/
│   │   ├── api_urls.py                  routes API   /api/auth/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── tests.py
│   │
│   ├── products/                        ✅ Catalogue produits
│   │   ├── models.py                    Produit · Categorie (mptt) · ImageProduit · MouvementStock
│   │   ├── managers.py                  ProduitActifManager · EnVedetteManager · StockFaibleManager
│   │   ├── signals.py                   resize Pillow (1200×1200) · invalidation cache Redis · update stock
│   │   ├── filters.py                   filtres django-filter (prix, catégorie, stock, statut...)
│   │   ├── serializers.py               6 serializers (liste, détail, créer, image, catégorie, stock)
│   │   ├── views.py                     accueil · liste · détail (avec cache Redis)
│   │   ├── api_views.py                 CategorieViewSet · ProduitViewSet
│   │   ├── urls.py                      routes HTML  /products/
│   │   ├── api_urls.py                  routes API   /api/produits/ · /api/categories/
│   │   ├── admin.py                     inline images · actions masse · export CSV
│   │   ├── apps.py
│   │   └── tests.py                     30 tests
│   │
│   ├── cart/                            ✅ Panier d'achat
│   │   ├── models.py                    Panier (OneToOne user) · PanierItem (prix_snapshot)
│   │   ├── services.py                  CartService : add · remove · update · calculate_total
│   │   ├── context_processors.py        cart_count → badge navbar
│   │   ├── serializers.py
│   │   ├── views.py                     vues HTML
│   │   ├── api_views.py                 CRUD panier + items
│   │   ├── urls.py                      routes HTML  /cart/
│   │   ├── api_urls.py                  routes API   /api/panier/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── tests.py                     17 tests
│   │
│   ├── orders/                          ✅ Commandes & paiements
│   │   ├── models.py                    Commande (FSM) · LigneCommande · Paiement
│   │   │                                EN_ATTENTE → CONFIRMEE → EN_PREPARATION → EXPEDIEE → LIVREE
│   │   │                                Tout sauf LIVREE → ANNULEE (remet le stock)
│   │   ├── services.py                  OrderService : create_from_cart · annuler
│   │   ├── signals.py                   CONFIRMEE → email Celery · LIVREE → rappel avis Celery
│   │   ├── serializers.py
│   │   ├── views.py                     vues HTML
│   │   ├── api_views.py                 CRUD commandes + actions FSM
│   │   ├── urls.py                      routes HTML  /orders/
│   │   ├── api_urls.py                  routes API   /api/commandes/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   └── tests.py                     19 tests
│   │
│   ├── reviews/                         ✅ Avis clients
│   │   ├── models.py                    Avis (note 1-5 · is_validated · unique_together user+produit)
│   │   ├── signals.py                   recalcul note_moyenne + nombre_avis sur Produit
│   │   ├── serializers.py
│   │   ├── api_views.py                 AvisViewSet : liste · créer · valider · supprimer
│   │   ├── api_urls.py                  routes API   /api/avis/
│   │   ├── admin.py                     badges validation · actions masse
│   │   ├── apps.py
│   │   ├── views.py
│   │   └── tests.py                     17 tests
│   │
│   ├── chat/                            ✅ Chat temps réel
│   │   ├── models.py                    Conversation (normalisée ID1<ID2) · MessageChat (is_read)
│   │   ├── consumers.py                 ChatConsumer — WebSocket async · broadcast Redis · marquage lu
│   │   ├── routing.py                   ws://localhost:8000/ws/chat/<id>/
│   │   ├── serializers.py
│   │   ├── views.py                     vues HTML chat_liste · chat_detail
│   │   ├── api_views.py                 liste · créer · détail · envoyer · marquer_lu
│   │   ├── urls.py                      routes HTML  /chat/
│   │   ├── api_urls.py                  routes API   /api/chat/
│   │   ├── admin.py                     inline messages · badges statut lu
│   │   ├── apps.py
│   │   └── tests.py                     25 tests (dont WebSocket via TransactionTestCase)
│   │
│   ├── notifications/                   ✅ Notifications & emails async
│   │   ├── models.py                    Notification (4 types) · EmailAsynchrone (log Celery)
│   │   ├── tasks.py                     5 tâches Celery (bind · retry x3) :
│   │   │                                  send_order_confirmation_email
│   │   │                                  send_status_update_email
│   │   │                                  send_review_reminder (countdown 3j)
│   │   │                                  alert_low_stock (Beat quotidien 8h)
│   │   │                                  cleanup_old_carts (Beat mensuel)
│   │   ├── consumers.py                 NotificationConsumer — groupe Redis par user
│   │   ├── routing.py                   ws://localhost:8000/ws/notifications/
│   │   ├── context_processors.py        notif_count → badge navbar
│   │   ├── serializers.py
│   │   ├── api_views.py                 liste · marquer_lue · tout_lire
│   │   ├── api_urls.py                  routes API   /api/notifications/
│   │   ├── admin.py                     badges colorés · actions masse
│   │   ├── apps.py
│   │   ├── views.py
│   │   └── tests.py                     19 tests (Celery mock + WebSocket)
│   │
│   └── __init__.py
│
├── templates/                           ⏳ Phase 5
│   ├── base.html                        layout principal (badges cart_count + notif_count)
│   ├── home.html
│   └── partials/
│       ├── navbar.html                  logo + badges + init WebSocket
│       ├── footer.html
│       └── toast.html                   notifications toast JS
│   └── (users/ products/ cart/ orders/ chat/ notifications/emails/)
│
├── static/
│   ├── img/
│   │   └── logo.svg                     ✅ #1E3A8A bleu marine + #F97316 orange
│   ├── js/                              ⏳ Phase 5
│   │   ├── api.js                       wrapper fetch() + JWT refresh auto
│   │   ├── products.js                  catalogue JSON + filtres + infinite scroll
│   │   ├── cart.js                      panier AJAX + badge navbar
│   │   ├── chat.js                      client WebSocket chat
│   │   └── notifications.js             client WebSocket notifications + badge
│   └── css/
│       └── custom.css                   ⏳ Phase 5
│
├── media/products/                      images uploadées (resize auto Pillow)
├── manage.py
├── requirements.txt                     ✅
├── .env                                 ✅
└── .gitignore                           ✅
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
git clone https://github.com/Ing-MONTHE/hooyia-market
cd hooyia-market

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
| http://localhost:5555 | Monitoring Celery (Flower) |
| ws://localhost:8000/ws/chat/\<id\>/ | WebSocket chat |
| ws://localhost:8000/ws/notifications/ | WebSocket notifications |

---

## 6. Avancement du projet

| Phase | Contenu | Statut |
|-------|---------|--------|
| **Phase 1** | Setup + config + `users` + `audit` | ✅ Complète |
| **Phase 2** | `products` | ✅ Complète |
| **Phase 3** | `cart` + `orders` | ✅ Complète |
| **Phase 4** | `reviews` + `chat` + `notifications` | ✅ Complète |
| **Phase 5** | Frontend HTML + TailwindCSS + JS | ⏳ À faire |
| **Phase 6** | Tests globaux + Lancement complet | ⏳ À faire |

### Bilan tests (Phases 1–4)

| App | Tests |
|-----|-------|
| `users` | ✅ |
| `products` | ✅ 30 tests |
| `cart` | ✅ 17 tests |
| `orders` | ✅ 19 tests |
| `reviews` | ✅ 17 tests |
| `chat` | ✅ 25 tests |
| `notifications` | ✅ 19 tests |
| **Total** | **≥ 127 tests** |

---

## 7. Structure des apps

### `apps.audit` ✅
- **AuditLog** : enregistre toutes les actions POST/PUT/PATCH/DELETE avec IP, user, method, path, status
- **AuditLogMiddleware** : s'exécute automatiquement à chaque requête HTTP

### `apps.users` ✅
- **CustomUser** : modèle utilisateur personnalisé (email comme identifiant unique)
- **AdresseLivraison** : adresses multiples, une seule par défaut via `save()`
- **TokenVerificationEmail** : token UUID, expire après 24h
- **Signals** : création token + email vérification + panier auto à l'inscription
- **JWT** : access token (1h) + refresh token (7 jours) avec blacklist

### `apps.products` ✅
- **Produit** : nom, slug auto-unique, description, prix, prix_promo, stock, statut
- **Categorie** : arbre hiérarchique via django-mptt
- **ImageProduit** : images multiples, resize automatique Pillow (1200×1200)
- **MouvementStock** : historique entrées/sorties, met à jour le stock via signal
- **Cache** : invalidation automatique Redis via signal post_save/delete

### `apps.cart` ✅
- **Panier** : lié à l'utilisateur (OneToOne), créé automatiquement à l'inscription
- **PanierItem** : produit + quantité + prix_snapshot (protège contre les changements de prix)
- **CartService** : add, remove, update, calculate_total

### `apps.orders` ✅
- **Commande** : FSM — `EN_ATTENTE → CONFIRMEE → EN_PREPARATION → EXPEDIEE → LIVREE`
- **Annulation** : possible depuis tout état sauf LIVREE, remet le stock automatiquement
- **LigneCommande** : détail produit + prix snapshot au moment de la commande
- **Paiement** : mode, statut, référence

### `apps.reviews` ✅
- **Avis** : note 1–5, commentaire, modération admin (is_validated)
- **Règle métier** : seuls les produits commandés et reçus peuvent être avisés (vérifié dans le serializer)
- **Signal** : recalcul automatique de `note_moyenne` et `nombre_avis` sur le Produit

### `apps.chat` ✅
- **Conversation** : entre deux utilisateurs, normalisée (participant1.id < participant2.id pour éviter les doublons)
- **MessageChat** : texte + horodatage + is_read
- **ChatConsumer** : WebSocket async, diffusion via Redis channel layer, marquage lu automatique

### `apps.notifications` ✅
- **Notification** : 4 types (commande, livraison, avis, stock)
- **EmailAsynchrone** : log de chaque tentative d'envoi email (statut en_attente/envoye/echec)
- **5 tâches Celery** : toutes avec bind + retry x3 — emails affichés en console en local
- **NotificationConsumer** : WebSocket par groupe Redis personnel à chaque utilisateur

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
| GET | `/api/produits/` | Public | Liste produits paginée + filtres |
| POST | `/api/produits/` | Vendeur | Créer produit |
| GET | `/api/produits/<id>/` | Public | Détail produit |
| PUT/PATCH | `/api/produits/<id>/` | Owner | Modifier produit |
| DELETE | `/api/produits/<id>/` | Admin | Supprimer produit |
| GET | `/api/categories/` | Public | Arbre catégories (mptt) |
| GET/POST | `/api/avis/` | GET: Public | Avis produits |
| PATCH | `/api/avis/<id>/valider/` | Admin | Valider un avis |
| GET/POST | `/api/panier/` | Auth | Voir/modifier panier |
| PATCH/DELETE | `/api/panier/items/<id>/` | Auth | Modifier item panier |
| GET/POST | `/api/commandes/` | Auth | Commandes utilisateur |
| POST | `/api/commandes/<id>/annuler/` | Owner | Annuler commande |
| GET | `/api/chat/` | Auth | Liste conversations |
| POST | `/api/chat/creer/` | Auth | Créer une conversation |
| GET | `/api/chat/<id>/` | Auth | Détail + messages |
| POST | `/api/chat/<id>/envoyer/` | Auth | Envoyer un message |
| POST | `/api/chat/<id>/marquer_lu/` | Auth | Marquer messages lus |
| GET | `/api/notifications/` | Auth | Notifications in-app |
| PATCH | `/api/notifications/<id>/lire/` | Auth | Marquer une notif lue |
| POST | `/api/notifications/tout_lire/` | Auth | Tout marquer comme lu |

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
| `send_order_confirmation_email` | Signal commande CONFIRMEE | Email HTML + Notification in-app |
| `send_status_update_email` | Transition FSM statut | Email mise à jour livraison |
| `send_review_reminder` | 3j après livraison (countdown) | Rappel laisser un avis |
| `alert_low_stock` | Beat quotidien à 8h | Email admin stock faible |
| `cleanup_old_carts` | Beat mensuel | Supprime paniers inactifs > 30j |

Chaque tâche : crée un `EmailAsynchrone` en DB → envoie l'email → met à jour statut → crée une `Notification` → diffuse via WebSocket.

---

## 11. Frontend — JavaScript & JSON (⏳ Phase 5)

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

Fichiers à créer : `api.js` · `products.js` · `cart.js` · `chat.js` · `notifications.js`
Templates à créer : `base.html` · `home.html` · `partials/` · `users/` · `products/` · `cart/` · `orders/` · `chat/` · emails HTML

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
