from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.address_validation import validate_adresse_ville_rdc
from core.forms import apply_form_styles
from core.geo_rdc import ville_choices
from .models import Client

User = get_user_model()


def _apply_ville_rdc(form, *, required=False):
    """Remplace le champ ville libre par un select des villes RDC."""
    current = ''
    if form.data:
        current = form.data.get('ville') or ''
    elif form.instance and getattr(form.instance, 'ville', None):
        current = form.instance.ville
    elif form.initial.get('ville'):
        current = form.initial['ville']

    form.fields['ville'] = forms.ChoiceField(
        choices=ville_choices(),
        label='Ville (RDC)',
        required=required,
        help_text='Choisissez d\'abord la ville pour cibler la recherche d\'adresse sur la carte.',
        widget=forms.Select(attrs={'id': 'id_ville'}),
    )
    if current and current not in dict(form.fields['ville'].choices):
        form.fields['ville'].choices = list(form.fields['ville'].choices) + [
            (current, f'{current} (existante)'),
        ]
    if 'code_postal' in form.fields:
        form.fields['code_postal'].widget.attrs['placeholder'] = 'ex. 01234'
    if 'adresse' in form.fields:
        form.fields['adresse'].widget.attrs.setdefault('placeholder', 'Ex. Boulevard du 30 Juin')
        form.fields['adresse'].widget.attrs.setdefault('autocomplete', 'street-address')
        form.fields['adresse'].widget.attrs.setdefault('id', 'id_adresse')
        form.fields['adresse'].help_text = (
            'Adresse vérifiable sur OpenStreetMap dans la ville sélectionnée (RDC).'
        )


def _clean_adresse_ville(cleaned, *, required=False):
    adresse = (cleaned.get('adresse') or '').strip()
    ville = (cleaned.get('ville') or '').strip()
    cleaned['adresse'] = adresse
    if adresse or required:
        detail = validate_adresse_ville_rdc(adresse, ville, required=required)
        if detail and detail.get('postcode') and not cleaned.get('code_postal'):
            cleaned['code_postal'] = detail['postcode']
    return cleaned


class ClientProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, label='Prénom')
    last_name = forms.CharField(max_length=150, label='Nom')
    email = forms.EmailField(label='Email')
    phone = forms.CharField(max_length=20, required=False, label='Téléphone')

    class Meta:
        model = Client
        fields = ('raison_sociale', 'siret', 'ville', 'adresse', 'code_postal')
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3, 'id': 'id_adresse'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_ville_rdc(self, required=False)
        apply_form_styles(self)
        if self.instance and self.instance.pk:
            user = self.instance.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['phone'].initial = user.phone

    def clean(self):
        cleaned = super().clean()
        try:
            return _clean_adresse_ville(cleaned, required=False)
        except ValidationError as exc:
            self.add_error('adresse', exc)
            return cleaned

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
        fields = ('raison_sociale', 'siret', 'ville', 'adresse', 'code_postal', 'notes_internes')
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3, 'id': 'id_adresse'}),
            'notes_internes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_ville_rdc(self, required=False)
        apply_form_styles(self)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Cet identifiant existe déjà.')
        return username

    def clean(self):
        cleaned = super().clean()
        try:
            return _clean_adresse_ville(cleaned, required=False)
        except ValidationError as exc:
            self.add_error('adresse', exc)
            return cleaned

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
    ville = forms.ChoiceField(
        choices=[],
        required=False,
        label='Ville (RDC)',
        widget=forms.Select(attrs={'id': 'id_ville'}),
    )
    adresse = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2, 'id': 'id_adresse'}),
        required=False,
        label='Adresse',
    )
    code_postal = forms.CharField(max_length=10, required=False, label='Code postal')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ville'].choices = ville_choices()
        self.fields['ville'].help_text = (
            'Choisissez d\'abord la ville pour cibler la recherche d\'adresse sur la carte.'
        )
        self.fields['adresse'].help_text = (
            'Adresse vérifiable sur OpenStreetMap dans la ville sélectionnée (RDC).'
        )
        apply_form_styles(self)
        self.fields['username'].widget.attrs.setdefault('placeholder', 'ex. jean.dupont')
        self.fields['password1'].widget.attrs.setdefault('placeholder', '8 caractères minimum')
        self.fields['password2'].widget.attrs.setdefault('placeholder', 'Retapez le mot de passe')
        self.fields['code_postal'].widget.attrs.setdefault('placeholder', 'ex. 01234')
        self.fields['adresse'].widget.attrs.setdefault('placeholder', 'Ex. Boulevard du 30 Juin')

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
        try:
            return _clean_adresse_ville(cleaned, required=False)
        except ValidationError as exc:
            self.add_error('adresse', exc)
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
