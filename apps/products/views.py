"""
Vues HTML pour le catalogue produits.
Ces vues retournent des pages HTML qui chargent
les données via JavaScript (fetch API → JSON).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.core.cache import cache
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from .models import Produit, Categorie, ImageProduit

def est_admin(user):
    return user.is_authenticated and user.is_staff


# ===============================================================
# VUE — Page "Laisser un avis sur la plateforme"
# ===============================================================

from django.contrib.auth.decorators import login_required

@login_required(login_url='/compte/connexion/')
def avis_plateforme(request):
    """
    Page dédiée pour laisser un avis sur la plateforme HooYia Market.
    Accessible uniquement aux utilisateurs connectés.
    La soumission se fait via l'API POST /api/avis-app/creer/ en JS.
    """
    from apps.reviews.models import AvisApp
    deja_soumis = AvisApp.objects.filter(utilisateur=request.user).exists()
    return render(request, 'products/avis_plateforme.html', {
        'deja_soumis': deja_soumis,
    })


# ═══════════════════════════════════════════════════════════════
# VUE — Page d'accueil
# ═══════════════════════════════════════════════════════════════

def accueil(request):
    """
    Page d'accueil du site.

    Données injectées dans le template :
      - categories       : catégories racines pour la navbar et le menu
      - produits_vedette : jusqu'à 8 produits marqués en_vedette=True
      - nouveaux_arrivages: les 8 produits les plus récents (statut actif)
    """
    # ── Catégories racines — mises en cache 1h ──
    categories = cache.get('categories_racines')
    if not categories:
        categories = Categorie.objects.filter(
            parent=None,
            est_active=True
        )
        cache.set('categories_racines', categories, 3600)

    # ── Produits en vedette (maxi 8) ──
    # prefetch_related('images') évite les N+1 queries pour les images
    produits_vedette = (
        Produit.objects
        .filter(statut='actif', en_vedette=True)
        .prefetch_related('images')
        .select_related('categorie')
        [:8]
    )

    # ── Nouveaux arrivages (8 derniers produits actifs) ──
    nouveaux_arrivages = (
        Produit.objects
        .filter(statut='actif')
        .prefetch_related('images')
        .select_related('categorie')
        .order_by('-date_creation')
        [:8]
    )

    context = {
        'categories':        categories,
        'produits_vedette':  produits_vedette,
        'nouveaux_arrivages': nouveaux_arrivages,
        'titre':             'HooYia Market — Électronique & Informatique',
    }
    return render(request, 'home.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Liste des produits (Catalogue)
# ═══════════════════════════════════════════════════════════════

def liste_produits(request):
    """
    Page catalogue avec pagination Python (Django Paginator).
    Les filtres dynamiques restent gérés en JS, mais la pagination
    est rendue côté serveur via des liens HTML classiques.
    """
    from django.core.paginator import Paginator
    from .filters import ProduitFilter

    categories = Categorie.objects.filter(est_active=True, parent=None).prefetch_related('sous_categories')

    categorie_slug = request.GET.get('categorie', '')
    categorie_active = None
    if categorie_slug:
        categorie_active = Categorie.objects.filter(slug=categorie_slug).first()

    # Construire le queryset avec filtres GET
    qs = Produit.objects.filter(statut='actif').select_related('categorie').prefetch_related('images')

    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(Q(nom__icontains=search) | Q(description__icontains=search))

    if categorie_slug and categorie_active:
        # Si la catégorie a des enfants (mère), inclure tous les enfants
        # Si c'est une feuille (sous-catégorie), filtrer uniquement sur elle
        sous_slugs = list(categorie_active.sous_categories.values_list('slug', flat=True))
        if sous_slugs:
            # Catégorie mère : produits de la mère ET de tous ses enfants
            from django.db.models import Q
            qs = qs.filter(Q(categorie__slug=categorie_slug) | Q(categorie__slug__in=sous_slugs))
        else:
            # Sous-catégorie feuille : filtre exact
            qs = qs.filter(categorie__slug=categorie_slug)

    promo = request.GET.get('promo')
    if promo:
        qs = qs.filter(prix_promo__isnull=False)

    en_vedette = request.GET.get('en_vedette')
    if en_vedette:
        qs = qs.filter(en_vedette=True)

    ordering = request.GET.get('ordering', '-date_creation')
    allowed_orderings = ['prix', '-prix', '-date_creation', 'date_creation', '-note_moyenne']
    if ordering in allowed_orderings:
        qs = qs.order_by(ordering)
    else:
        qs = qs.order_by('-date_creation')

    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Conserver les paramètres GET sans 'page' pour les liens de pagination
    params = request.GET.copy()
    params.pop('page', None)
    params_str = params.urlencode()

    context = {
        'categories'      : categories,
        'categorie_active': categorie_active,
        'titre'           : 'Catalogue — HooYia Market',
        'page_obj'        : page_obj,
        'paginator'       : paginator,
        'params_str'      : params_str,
        'total_count'     : paginator.count,
        'search'          : search,
        'ordering'        : ordering,
    }
    return render(request, 'products/list.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Détail d'un produit
# ═══════════════════════════════════════════════════════════════

def detail_produit(request, slug):
    """
    Fiche détaillée d'un produit.
    Les données complètes (images, avis, prix) sont chargées
    via JavaScript depuis /api/produits/<id>/
    On récupère juste le produit pour le titre et les meta tags.
    """
    from apps.users.models import CustomUser

    # Mise en cache du produit 10 minutes
    cache_key = f'produit_slug_{slug}'
    produit   = cache.get(cache_key)

    if not produit:
        produit = get_object_or_404(
            Produit.objects.select_related('categorie', 'vendeur').prefetch_related('images'),
            slug=slug
        )
        cache.set(cache_key, produit, 600)

    # Récupère le premier admin actif (= vendeur) pour le bouton "Contacter le vendeur"
    admin = CustomUser.objects.filter(is_admin=True, is_active=True).first()

    context = {
        'produit'  : produit,
        'titre'    : f'{produit.nom} — HooYia Market',
        'admin_id' : admin.id if admin else None,
    }
    return render(request, 'products/detail.html', context)

# ═══════════════════════════════════════════════════════════════
# VUE — Ajouter un produit (admin uniquement)
# ═══════════════════════════════════════════════════════════════

@user_passes_test(est_admin, login_url='/compte/connexion/')
def ajouter_produit(request):
    categories = Categorie.objects.filter(parent=None, est_active=True).prefetch_related('sous_categories')

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        description_courte = request.POST.get('description_courte', '').strip()
        categorie_id = request.POST.get('categorie')
        prix = request.POST.get('prix')
        prix_promo = request.POST.get('prix_promo') or None
        stock = request.POST.get('stock', 0)
        stock_minimum = request.POST.get('stock_minimum', 5)
        statut = request.POST.get('statut', 'actif')
        en_vedette = 'en_vedette' in request.POST

        if not nom or not description or not prix:
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
        else:
            try:
                produit = Produit.objects.create(
                    nom=nom,
                    description=description,
                    description_courte=description_courte,
                    categorie_id=categorie_id if categorie_id else None,
                    prix=prix,
                    prix_promo=prix_promo,
                    stock=stock,
                    stock_minimum=stock_minimum,
                    statut=statut,
                    en_vedette=en_vedette,
                    vendeur=request.user,
                )

                # Traitement des images
                images = request.FILES.getlist('images')
                for i, img_file in enumerate(images):
                    ImageProduit.objects.create(
                        produit=produit,
                        image=img_file,
                        ordre=i,
                        est_principale=(i == 0),
                    )

                # Invalider le cache
                cache.delete('categories_api')
                cache.delete('categories_racines')

                messages.success(request, f"Produit « {produit.nom} » créé avec succès !")
                return redirect('products:detail', slug=produit.slug)

            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")

    context = {
        'categories': categories,
        'form': type('obj', (object,), {
            'nom': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
            'description': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
            'description_courte': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
            'prix': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
            'prix_promo': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
            'stock': type('f', (object,), {'value': lambda s: 0, 'errors': []})(),
            'stock_minimum': type('f', (object,), {'value': lambda s: 5, 'errors': []})(),
            'statut': type('f', (object,), {'value': 'actif', 'errors': []})(),
            'en_vedette': type('f', (object,), {'value': False, 'errors': []})(),
            'categorie': type('f', (object,), {'value': lambda s: '', 'errors': []})(),
        })(),
    }
    return render(request, 'products/ajouter_produit.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Modifier un produit (admin uniquement)
# ═══════════════════════════════════════════════════════════════

@user_passes_test(est_admin, login_url='/compte/connexion/')
def modifier_produit(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)
    categories = Categorie.objects.filter(parent=None, est_active=True).prefetch_related('sous_categories')

    if request.method == 'POST':
        produit.nom = request.POST.get('nom', produit.nom).strip()
        produit.description = request.POST.get('description', produit.description).strip()
        produit.description_courte = request.POST.get('description_courte', '').strip()
        categorie_id = request.POST.get('categorie')
        produit.categorie_id = categorie_id if categorie_id else None
        produit.prix = request.POST.get('prix', produit.prix)
        produit.prix_promo = request.POST.get('prix_promo') or None
        produit.stock = request.POST.get('stock', produit.stock)
        produit.stock_minimum = request.POST.get('stock_minimum', produit.stock_minimum)
        produit.statut = request.POST.get('statut', produit.statut)
        produit.en_vedette = 'en_vedette' in request.POST

        try:
            produit.save()

            # Nouvelles images
            images = request.FILES.getlist('images')
            for i, img_file in enumerate(images):
                ImageProduit.objects.create(
                    produit=produit,
                    image=img_file,
                    ordre=produit.images.count() + i,
                    est_principale=(produit.images.count() == 0 and i == 0),
                )

            cache.delete(f'produit_slug_{produit.slug}')
            messages.success(request, "Produit modifié avec succès !")
            return redirect('products:detail', slug=produit.slug)
        except Exception as e:
            messages.error(request, f"Erreur : {str(e)}")

    context = {
        'produit': produit,
        'categories': categories,
        'form': type('obj', (object,), {
            'nom': type('f', (object,), {'value': produit.nom, 'errors': []})(),
            'description': type('f', (object,), {'value': produit.description, 'errors': []})(),
            'description_courte': type('f', (object,), {'value': produit.description_courte, 'errors': []})(),
            'prix': type('f', (object,), {'value': str(produit.prix), 'errors': []})(),
            'prix_promo': type('f', (object,), {'value': str(produit.prix_promo) if produit.prix_promo else '', 'errors': []})(),
            'stock': type('f', (object,), {'value': produit.stock, 'errors': []})(),
            'stock_minimum': type('f', (object,), {'value': produit.stock_minimum, 'errors': []})(),
            'statut': type('f', (object,), {'value': produit.statut, 'errors': []})(),
            'en_vedette': type('f', (object,), {'value': produit.en_vedette, 'errors': []})(),
            'categorie': type('f', (object,), {'value': str(produit.categorie_id) if produit.categorie_id else '', 'errors': []})(),
        })(),
    }
    return render(request, 'products/ajouter_produit.html', context)


# ═══════════════════════════════════════════════════════════════
# VUE — Supprimer un produit (admin uniquement)
# ═══════════════════════════════════════════════════════════════

@user_passes_test(est_admin, login_url='/compte/connexion/')
def supprimer_produit(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)
    if request.method == 'POST':
        nom = produit.nom
        cache.delete(f'produit_slug_{produit.slug}')
        produit.delete()
        messages.success(request, f"Produit « {nom} » supprimé.")
        return redirect('products:liste')
    return redirect('products:detail', slug=produit.slug)

# ──────────────────────────────────────────────────────────────
# GESTION DES CATÉGORIES (admin uniquement)
# ──────────────────────────────────────────────────────────────

@user_passes_test(est_admin, login_url='/compte/connexion/')
def gestion_categories(request):
    """Liste + formulaire d'ajout/modification de catégories."""
    categories_racines = Categorie.objects.filter(parent=None, est_active=True)
    toutes_categories = Categorie.objects.filter(est_active=True)

    modifier_id = request.GET.get('modifier')
    categorie_edit = None
    if modifier_id:
        categorie_edit = get_object_or_404(Categorie, id=modifier_id)

    if request.method == 'POST':
        action = request.POST.get('action', 'creer')
        nom = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent') or None
        est_active = 'est_active' in request.POST

        if not nom:
            messages.error(request, "Le nom est obligatoire.")
        else:
            try:
                if action == 'modifier' and request.POST.get('categorie_id'):
                    cat = get_object_or_404(Categorie, id=request.POST.get('categorie_id'))
                    cat.nom = nom
                    cat.description = description
                    cat.parent_id = parent_id
                    cat.est_active = est_active
                    if 'image' in request.FILES:
                        cat.image = request.FILES['image']
                    cat.save()
                    cache.delete('categories_api')
                    cache.delete('categories_racines')
                    messages.success(request, f"Catégorie « {cat.nom} » modifiée avec succès !")
                else:
                    cat = Categorie.objects.create(
                        nom=nom,
                        description=description,
                        parent_id=parent_id,
                        est_active=est_active,
                    )
                    if 'image' in request.FILES:
                        cat.image = request.FILES['image']
                        cat.save()
                    cache.delete('categories_api')
                    cache.delete('categories_racines')
                    messages.success(request, f"Catégorie « {cat.nom} » créée avec succès !")
                return redirect('products:gestion_categories')
            except Exception as e:
                messages.error(request, f"Erreur : {str(e)}")

    return render(request, 'products/gestion_categories.html', {
        'categories_racines': categories_racines,
        'toutes_categories': toutes_categories,
        'categorie_edit': categorie_edit,
    })


@user_passes_test(est_admin, login_url='/compte/connexion/')
def api_categories_crud(request):
    """Endpoint JSON pour le CRUD des catégories depuis le dashboard."""
    from django.http import JsonResponse
    import json

    if request.method == 'GET':
        # Liste toutes les catégories (racines + sous-catégories)
        cats = Categorie.objects.filter(est_active=True).select_related('parent').order_by('tree_id', 'lft')
        data = []
        for c in cats:
            data.append({
                'id': c.id,
                'nom': c.nom,
                'slug': c.slug,
                'description': c.description,
                'parent_id': c.parent_id,
                'parent_nom': c.parent.nom if c.parent else None,
                'est_active': c.est_active,
                'image': c.image.url if c.image else None,
                'niveau': 'Niveau 1' if c.parent else 'Niveau 0',
                'nb_produits': c.produits.count(),
            })
        return JsonResponse({'categories': data})

    elif request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        if not nom:
            return JsonResponse({'error': 'Le nom est obligatoire.'}, status=400)
        description = request.POST.get('description', '').strip()
        parent_id = request.POST.get('parent_id') or None
        est_active = request.POST.get('est_active', 'true') == 'true'
        cat_id = request.POST.get('cat_id')

        try:
            if cat_id:
                # Modification
                cat = get_object_or_404(Categorie, id=cat_id)
                cat.nom = nom
                cat.description = description
                cat.parent_id = parent_id
                cat.est_active = est_active
                if 'image' in request.FILES:
                    cat.image = request.FILES['image']
                cat.save()
                action = 'modified'
            else:
                # Création
                cat = Categorie.objects.create(
                    nom=nom,
                    description=description,
                    parent_id=parent_id,
                    est_active=est_active,
                )
                if 'image' in request.FILES:
                    cat.image = request.FILES['image']
                    cat.save()
                action = 'created'
            cache.delete('categories_api')
            cache.delete('categories_racines')
            return JsonResponse({
                'success': True,
                'action': action,
                'categorie': {
                    'id': cat.id,
                    'nom': cat.nom,
                    'slug': cat.slug,
                    'parent_id': cat.parent_id,
                    'parent_nom': cat.parent.nom if cat.parent else None,
                    'image': cat.image.url if cat.image else None,
                    'est_active': cat.est_active,
                    'niveau': 'Niveau 1' if cat.parent else 'Niveau 0',
                    'nb_produits': cat.produits.count(),
                }
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    elif request.method == 'DELETE':
        body = json.loads(request.body or '{}')
        cat_id = body.get('cat_id')
        if not cat_id:
            return JsonResponse({'error': 'cat_id manquant'}, status=400)
        cat = get_object_or_404(Categorie, id=cat_id)
        nom = cat.nom
        cat.est_active = False
        cat.save()
        cache.delete('categories_api')
        cache.delete('categories_racines')
        return JsonResponse({'success': True, 'nom': nom})

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@user_passes_test(est_admin, login_url='/compte/connexion/')
def supprimer_categorie(request, cat_id):
    """Suppression (désactivation) d'une catégorie."""
    cat = get_object_or_404(Categorie, id=cat_id)
    nom = cat.nom
    cat.est_active = False
    cat.save()
    cache.delete('categories_api')
    cache.delete('categories_racines')
    messages.success(request, f"Catégorie « {nom} » supprimée.")
    return redirect('products:gestion_categories')


# ──────────────────────────────────────────────────────────────
# DASHBOARD ADMIN PERSONNALISÉ
# ──────────────────────────────────────────────────────────────
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    """Dashboard d'administration HooYia — remplace l'admin Django natif."""
    from apps.users.models import CustomUser
    from apps.cart.models import Panier

    context = {
        'users_count':  CustomUser.objects.filter(is_active=True).count(),
        'paniers_count': Panier.objects.filter(items__isnull=False).distinct().count(),
        'categories': Categorie.objects.filter(parent=None, est_active=True).prefetch_related('sous_categories'),
    }
    return render(request, 'admin_dashboard.html', context)

# ── Autocomplete recherche ──
from django.http import JsonResponse
from django.db.models import Q

def autocomplete_search(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})
    produits = (
        Produit.objects
        .filter(statut='actif')
        .filter(Q(nom__icontains=q) | Q(categorie__nom__icontains=q))
        .select_related('categorie')
        .prefetch_related('images')
        [:8]
    )
    results = []
    for p in produits:
        img = p.images.filter(est_principale=True).first() or p.images.first()
        results.append({
            'nom': p.nom,
            'slug': p.slug,
            'prix': str(p.prix_actuel),
            'image': img.image.url if img else None,
        })
    return JsonResponse({'results': results})