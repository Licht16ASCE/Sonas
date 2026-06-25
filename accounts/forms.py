from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

from accounts.models import UserRole
from core.forms import apply_form_styles

User = get_user_model()


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)
        self.fields['username'].widget.attrs.setdefault('placeholder', 'Identifiant')
        self.fields['password'].widget.attrs.setdefault('placeholder', 'Mot de passe')

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        if username and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise forms.ValidationError('Identifiants invalides.')
            if not self.user_cache.is_active:
                raise forms.ValidationError('Ce compte est désactivé.')
        return self.cleaned_data


class AgentCreateForm(forms.Form):
    username = forms.CharField(max_length=150, label='Identifiant')
    email = forms.EmailField(label='Email')
    first_name = forms.CharField(max_length=150, label='Prénom')
    last_name = forms.CharField(max_length=150, label='Nom')
    phone = forms.CharField(max_length=20, required=False, label='Téléphone')
    password = forms.CharField(widget=forms.PasswordInput, label='Mot de passe')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_styles(self)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Cet identifiant existe déjà.')
        return username

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone=self.cleaned_data.get('phone', ''),
            role=UserRole.AGENT,
        )
