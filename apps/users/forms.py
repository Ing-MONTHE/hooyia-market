"""
HooYia Market — users/forms.py
Formulaires Django pour les vues HTML.
Les formulaires gèrent la validation côté serveur
et la génération des champs HTML.
"""
from django import forms
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser, AdresseLivraison


# ═══════════════════════════════════════════════════════════════
# FORMULAIRE — Inscription
# ═══════════════════════════════════════════════════════════════

class InscriptionForm(forms.ModelForm):
    """
    Formulaire d'inscription affiché sur la page register.html.
    Gère la validation et la création du compte.
    """

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class'      : 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Mot de passe'
        }),
        validators=[validate_password],
        label="Mot de passe"
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class'      : 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirmer le mot de passe'
        }),
        label="Confirmer le mot de passe"
    )

    class Meta:
        model  = CustomUser
        fields = ['username', 'email', 'nom', 'prenom', 'telephone']
        widgets = {
            'username' : forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': "Nom d'utilisateur"
            }),
            'email'    : forms.EmailInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Adresse email'
            }),
            'nom'      : forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Nom'
            }),
            'prenom'   : forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Prénom'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Téléphone (ex: +237 6XX XXX XXX)'
            }),
        }

    def clean_email(self):
        """Vérifie l'unicité de l'email"""
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cet email.")
        return email.lower()

    def clean(self):
        """Vérifie que les deux mots de passe correspondent"""
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        """Sauvegarde avec le mot de passe hashé"""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_active = False  # Inactif jusqu'à vérification email
        if commit:
            user.save()
        return user


# ═══════════════════════════════════════════════════════════════
# FORMULAIRE — Connexion
# ═══════════════════════════════════════════════════════════════

class ConnexionForm(forms.Form):
    """
    Formulaire de connexion simple.
    On utilise forms.Form (pas ModelForm) car
    on ne crée pas d'objet, on vérifie juste les identifiants.
    """

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class'      : 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Adresse email',
            'autofocus'  : True
        }),
        label="Email"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class'      : 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Mot de passe'
        }),
        label="Mot de passe"
    )


# ═══════════════════════════════════════════════════════════════
# FORMULAIRE — Modification du profil
# ═══════════════════════════════════════════════════════════════

class ProfilForm(forms.ModelForm):
    """
    Permet à l'utilisateur de modifier ses informations
    personnelles (pas l'email, pas le mot de passe).
    """

    class Meta:
        model  = CustomUser
        fields = ['username', 'nom', 'prenom', 'telephone', 'photo_profil']
        widgets = {
            'username' : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'nom'      : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'prenom'   : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'telephone': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
        }


# ═══════════════════════════════════════════════════════════════
# FORMULAIRE — Adresse de livraison
# ═══════════════════════════════════════════════════════════════

class AdresseForm(forms.ModelForm):

    class Meta:
        model  = AdresseLivraison
        fields = [
            'nom_complet', 'telephone', 'adresse',
            'ville', 'region', 'pays',
            'code_postal', 'is_default'
        ]
        widgets = {
            'nom_complet': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'telephone'  : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'adresse'    : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'ville'      : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'region'     : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'pays'       : forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
            'code_postal': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-lg'}),
        }