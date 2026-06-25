# SONAS — Plateforme de gestion immobilière & sinistres

Application SaaS full-stack Django 5 + TailwindCSS pour la gestion des clients, biens, contrats et sinistres.

## Stack

- **Backend** : Django 5+
- **Base de données** : PostgreSQL (SQLite en fallback dev)
- **Cache / Async** : Redis + Celery
- **Frontend** : TailwindCSS + Alpine.js
- **Auth** : Django Auth avec rôles métier

## Architecture

| Route | Espace |
|-------|--------|
| `/` | Landing page |
| `/client/` | Espace client (self-service) |
| `/sonas/` | Espace interne (agent, gérant, admin) |
| `/sonas/admin-secure/` | Admin Django sécurisé |

## Rôles

- **CLIENT** — Self-service uniquement
- **AGENT** — Traitement opérationnel
- **GERANT** — Validation métier des sinistres
- **ADMIN** — Gestion technique + override

## Installation

```bash
# 1. Environnement virtuel
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. Dépendances
pip install -r requirements.txt

# 3. Services (PostgreSQL + Redis) — optionnel
docker-compose up -d

# 4. Configuration
copy .env.example .env       # Windows
# cp .env.example .env       # Linux/Mac

# 5. Migrations
python manage.py migrate

# 6. Données de démo
python manage.py seed_sonas

# 7. Lancer le serveur
python manage.py runserver
```

## Celery (tâches async)

```bash
# Worker
celery -A config worker -l info

# Beat (expirations contrats + digest quotidien)
celery -A config beat -l info
```

## Comptes démo

Mot de passe : `sonas2024`

| Utilisateur | Rôle | Redirection |
|-------------|------|-------------|
| client1 | Client | `/client/` |
| agent | Agent | `/sonas/` |
| gerant | Gérant | `/sonas/` |
| admin | Admin | `/sonas/` |

## Modules

- **Clients** — CRUD, profil, historique activités
- **Biens** — Déclaration, validation (EN_ATTENTE / VALIDE / REJETE)
- **Contrats** — Liaison client+bien, alertes expiration J-30/J-15/J-7/J0
- **Sinistres** — Workflow DECLARE → EN_COURS → VALIDE/REJETE
- **Documents** — Upload lié aux sinistres et biens
- **Notifications** — Regroupement intelligent, digest quotidien
- **Actions en attente** — Reprise des tâches incomplètes

## Sécurité

- Session timeout : 20 minutes d'inactivité
- Middleware de protection par rôle
- Séparation stricte client / interne
- Logs des actions critiques (`logs/sonas.log`)
- Admin sur URL non standard
