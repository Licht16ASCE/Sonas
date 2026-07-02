from django import forms
from django.contrib.auth import get_user_model

from core.forms import apply_form_styles
from .models import Client

User = get_user_model()


class ClientProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='Prénom')
    last_name = forms.CharField(max_length=150, label='Nom')
    email = forms.EmailField(label='Email')
    phone = forms.CharField(max_length=20, required=False, label='Téléphone')

    class Meta:
        model = Client
        fields = ('raison_sociale', 'siret', 'adresse', 'code_postal', 'ville')
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = user.phone

    def save(self, commit=True):
        client = super().save(commit=False)
        user = client.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
            client.save()
        return client


class ClientCreateForm(forms.ModelForm):
    """Formulaire interne de création client + compte utilisateur."""

    username = forms.CharField(max_length=150, label='Identifiant')
    email = forms.EmailField(label='Email')
    first_name = forms.CharField(max_length=150, label='Prénom')
    last_name = forms.CharField(max_length=150, label='Nom')
    phone = forms.CharField(max_length=20, required=False, label='Téléphone')
    password = forms.CharField(widget=forms.PasswordInput, label='Mot de passe')

    class Meta:
        model = Client
        fields = ('raison_sociale', 'siret', 'adresse', 'code_postal', 'ville', 'notes_internes')
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3}),
            'notes_internes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Cet identifiant existe déjà.')
        return username

    def save(self, commit=True):
        from accounts.models import UserRole

        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            role=UserRole.CLIENT,
        )
        client = user.client_profile
        for field in ('raison_sociale', 'siret', 'adresse', 'code_postal', 'ville', 'notes_internes'):
            if field in self.cleaned_data:
                setattr(client, field, self.cleaned_data[field])
        if commit:
            client.save()
        return client


class ClientRegisterForm(forms.Form):
    """Inscription publique — réservée aux clients."""

    username = forms.CharField(max_length=150, label='Identifiant')
    email = forms.EmailField(label='Email')
    first_name = forms.CharField(max_length=150, label='Prénom')
    last_name = forms.CharField(max_length=150, label='Nom')
    phone = forms.CharField(max_length=20, required=False, label='Téléphone')
    password1 = forms.CharField(widget=forms.PasswordInput, label='Mot de passe')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Confirmer le mot de passe')
    adresse = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
        label='Adresse',
    )
    code_postal = forms.CharField(max_length=10, required=False, label='Code postal')
    ville = forms.CharField(max_length=100, required=False, label='Ville')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        self.fields['username'].widget.attrs.setdefault('placeholder', 'ex. jean.dupont')
        self.fields['password1'].widget.attrs.setdefault('placeholder', '8 caractères minimum')
        self.fields['password2'].widget.attrs.setdefault('placeholder', 'Retapez le mot de passe')

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Cet identifiant est déjà pris.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Un compte existe déjà avec cet email.')
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Les mots de passe ne correspondent pas.')
        if p1 and len(p1) < 8:
            raise forms.ValidationError('Le mot de passe doit contenir au moins 8 caractères.')
        return cleaned

    def save(self):
        from accounts.models import UserRole

        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            role=UserRole.CLIENT,
        )
        client = user.client_profile
        client.adresse = self.cleaned_data.get('adresse', '')
        client.code_postal = self.cleaned_data.get('code_postal', '')
        client.ville = self.cleaned_data.get('ville', '')
        client.save()
        return user
