"""
Commande de peuplement initial pour démo / développement.
Usage: python manage.py seed_sonas
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from accounts.models import UserRole
from biens.models import Bien, BienStatut, BienType
from clients.models import Client
from contrats.models import Contrat, ContratStatut

User = get_user_model()


class Command(BaseCommand):
    help = 'Crée des utilisateurs et données de démonstration SONAS'

    def handle(self, *args, **options):
        users_data = [
            ('admin', UserRole.ADMIN, 'Admin', 'SONAS', True),
            ('gerant', UserRole.GERANT, 'Marie', 'Gérant', True),
            ('agent', UserRole.AGENT, 'Paul', 'Agent', True),
            ('client1', UserRole.CLIENT, 'Jean', 'Dupont', False),
        ]

        for username, role, first, last, is_staff in users_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@sonas.fr',
                    'first_name': first,
                    'last_name': last,
                    'role': role,
                    'is_staff': is_staff,
                    'is_superuser': role == UserRole.ADMIN,
                },
            )
            if created:
                user.set_password('sonas2024')
                user.save()
                self.stdout.write(f'  + Utilisateur {username} ({role})')

        client_user = User.objects.get(username='client1')
        client, _ = Client.objects.get_or_create(
            user=client_user,
            defaults={
                'raison_sociale': 'Dupont Immobilier',
                'adresse': '12 rue de la Paix',
                'code_postal': '75001',
                'ville': 'Paris',
            },
        )

        bien, created = Bien.objects.get_or_create(
            reference='BIEN-DEMO-001',
            defaults={
                'client': client,
                'type_bien': BienType.APPARTEMENT,
                'adresse': '12 rue de la Paix',
                'code_postal': '75001',
                'ville': 'Paris',
                'surface_m2': 85,
                'statut': BienStatut.VALIDE,
            },
        )
        if created:
            self.stdout.write('  + Bien demo')

        contrat, created = Contrat.objects.get_or_create(
            reference='CTR-DEMO-001',
            defaults={
                'client': client,
                'bien': bien,
                'date_debut': date.today() - timedelta(days=180),
                'date_fin': date.today() + timedelta(days=20),
                'statut': ContratStatut.ACTIF,
                'montant_annuel': 1200,
            },
        )
        if created:
            self.stdout.write('  + Contrat demo (expire J-20)')

        self.stdout.write(self.style.SUCCESS('\nDonnées demo créées.'))
        self.stdout.write('Comptes (mot de passe: sonas2024):')
        self.stdout.write('  admin / gerant / agent -> /sonas/')
        self.stdout.write('  client1 -> /client/')
