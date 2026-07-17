# SONAS — Plateforme de gestion immobilière & sinistres

Application web Django pour la gestion des clients, biens immobiliers, contrats d'assurance, sinistres, documents et notifications. Deux espaces distincts : **client** (self-service) et **interne** (agent, gérant, admin).

## Fonctionnalités principales

- Parcours guidés (stepper) sur les formulaires de création
- Validation des biens et des contrats par l'équipe interne
- Génération automatique d'un **contrat PDF** contractuel à la création / validation
- Workflow sinistre avec **traitement agent** et **clôture gérant**
- **Indemnisation** avec plafond contractuel, rapport PDF et inactivation du contrat si dépassement
- **Consultation documentaire** interne avec recherche par client, type et texte libre
- Notifications regroupées et actions en attente (reprise des dossiers incomplets)
- Alertes d'expiration de contrat (J-30, J-15, J-7, J0) via Celery

## Stack technique

| Couche | Technologie |
|--------|-------------|
| Backend | Django 5+ |
| Base de données | PostgreSQL (SQLite en fallback sans Docker) |
| Cache / tâches async | Redis + Celery *(optionnel en dev)* |
| Frontend | TailwindCSS + Alpine.js |
| PDF | Playwright (Chromium) — même stack que WeddingPlanner |
| Auth | Django Auth + rôles métier |

## Architecture des espaces

| Route | Accès | Description |
|-------|-------|-------------|
| `/` | Public | Landing page |
| `/client/` | Client | Dashboard, profil, activités |
| `/client/biens/` | Client | Déclaration et suivi des biens |
| `/client/contrats/` | Client | Consultation des contrats |
| `/client/sinistres/` | Client | Déclaration et suivi des sinistres |
| `/client/documents/` | Client | Documents propres au client |
| `/client/notifications/` | Client | Notifications |
| `/sonas/` | Interne | Dashboard agent / gérant / admin |
| `/sonas/clients/` | Interne | Gestion et supervision clients |
| `/sonas/biens/` | Interne | Validation des biens |
| `/sonas/contrats/` | Interne | Création et gestion des contrats |
| `/sonas/sinistres/` | Interne | Traitement et validation sinistres |
| `/sonas/documents/` | Interne | Tous les documents + filtres |
| `/sonas/notifications/` | Interne | Notifications et actions en attente |
| `/sonas/agents/` | Gérant / Admin | Gestion de l'équipe agents |
| `/sonas/admin-secure/` | Admin | Interface Django admin |

## Rôles et responsabilités

| Rôle | Périmètre |
|------|-----------|
| **CLIENT** | Espace `/client/` uniquement — déclare biens/sinistres, consulte ses contrats et documents |
| **AGENT** | Traitement opérationnel — validation biens, instruction sinistres, proposition d'indemnisation, upload documents |
| **GERANT** | Validation métier — clôture ou rejet des sinistres transmis, supervision, gestion des agents |
| **ADMIN** | Administration technique — utilisateurs, logs, système, accès admin Django |

### Séparation des tâches (sinistres)

Seul le **gérant** (ou l'admin) peut **clôturer** ou **rejeter** un sinistre. L'**agent** instruit le dossier et **transmet** sa décision d'indemnisation.

```mermaid
flowchart LR
    A[Déclaré] -->|Agent| B[En cours]
    B -->|Agent : Oui/Non indemnisation| C[Transmis au gérant]
    C -->|Gérant : Clôturer| D[Validé]
    C -->|Gérant : Rejeter| E[Rejeté]
    D -->|Si indemnisation| F[Rapport PDF + déduction plafond]
    F -->|Plafond dépassé/épuisé| G[Contrat inactif]
```

## Flux indemnisation & plafond

Chaque contrat possède un **plafond d'indemnisation** (`plafond_indemnisation`) et un cumul des montants déjà versés.

Lors de la clôture avec indemnisation :

1. L'agent indique si une indemnisation est accordée et le montant proposé
2. Le gérant valide la clôture
3. Le système calcule le montant effectif, déduit du plafond contractuel
4. Un **rapport d'indemnisation** (document PDF) est généré et rattaché au sinistre
5. Si le plafond est **dépassé ou épuisé**, le contrat passe en statut **Inactif** et les nouveaux sinistres sont bloqués

Sans indemnisation : clôture simple, **aucune déduction** sur le plafond.

## Documents

Les documents peuvent être liés à un **bien**, un **sinistre** ou un **contrat**.

Types disponibles : Justificatif, Photo, Rapport, Contrat PDF, Autre.

**Espace interne** (`/sonas/documents/`) — accessible aux agents et gérants :

- Filtre par **client**
- Filtre par **type** de document
- Recherche texte (titre, nom client, références bien/sinistre/contrat)
- Colonnes Client et entité associée

## Installation

### Prérequis

- Python 3.11+
- *(Optionnel)* Docker pour PostgreSQL et Redis

### Démarrage rapide (SQLite, sans Docker)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux / macOS

pip install -r requirements.txt
python -m playwright install chromium
copy .env.example .env         # Windows — laisser DATABASE_URL vide pour SQLite
# cp .env.example .env         # Linux / macOS

python manage.py migrate
python manage.py seed_sonas
python manage.py runserver
```

Application disponible sur [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### Avec PostgreSQL + Redis (Docker)

```bash
docker-compose up -d
```

Configurer `.env` :

```env
DATABASE_URL=postgres://sonas:sonas@localhost:5432/sonas_db
REDIS_URL=redis://localhost:6379/0
```

Puis migrations, seed et serveur comme ci-dessus.

## Celery (tâches planifiées)

Celery est utilisé pour les expirations de contrats et le digest quotidien de notifications. **Non requis** pour tester l'application en local (le serveur Django suffit).

```bash
celery -A config worker -l info
celery -A config beat -l info
```

## Comptes de démonstration

Mot de passe pour tous les comptes : **`sonas2024`**

| Utilisateur | Rôle | Espace |
|-------------|------|--------|
| `client1` | Client | `/client/` |
| `agent` | Agent | `/sonas/` |
| `gerant` | Gérant | `/sonas/` |
| `admin` | Admin | `/sonas/` |

### Données créées par `seed_sonas`

- Client **Dupont Immobilier** (`client1`)
- Bien **BIEN-DEMO-001** (appartement, statut Validé)
- Contrat **CTR-DEMO-001** (actif, expire dans ~20 jours, plafond **50 000 $**)

```bash
python manage.py seed_sonas
```

## Modules applicatifs

| Module | Description |
|--------|-------------|
| **accounts** | Utilisateurs, rôles, équipe agents |
| **clients** | Profils clients, historique d'activité |
| **biens** | Déclaration, validation (`EN_ATTENTE` / `VALIDE` / `REJETE`) |
| **contrats** | Liaison client + bien, PDF contractuel, plafond, alertes expiration |
| **sinistres** | Workflow complet, indemnisation, rapports |
| **documents** | Upload, stockage, recherche interne |
| **notifications** | Alertes, regroupement, actions en attente |
| **core** | Landing, dashboards, logs système |

## Structure du projet

```
TFC_Francesco/
├── accounts/          # Auth, rôles, agents
├── biens/
├── clients/
├── config/            # Settings, URLs, Celery
├── contrats/
├── core/
├── documents/
├── notifications/
├── sinistres/
├── static/            # CSS (sonas.css, contrat-visuel.css)
├── templates/         # Templates Django + partials
├── media/             # Fichiers uploadés (documents, PDF)
├── logs/              # sonas.log
├── manage.py
├── requirements.txt
└── docker-compose.yml
```

## Sécurité

- Timeout de session : **20 minutes** d'inactivité
- Middleware de protection par rôle (séparation stricte client / interne)
- Admin Django sur URL non standard (`/sonas/admin-secure/` par défaut)
- Journalisation des actions critiques dans `logs/sonas.log`
- Fichiers média servis uniquement en mode `DEBUG`

## Variables d'environnement

| Variable | Description | Défaut |
|----------|-------------|--------|
| `DEBUG` | Mode debug | `True` |
| `SECRET_KEY` | Clé Django | *(à changer en prod)* |
| `DATABASE_URL` | Connexion PostgreSQL | *(vide → SQLite)* |
| `REDIS_URL` | Connexion Redis / Celery | `redis://localhost:6379/0` |
| `ALLOWED_HOSTS` | Hôtes autorisés | `localhost,127.0.0.1` |
| `ADMIN_URL` | Chemin admin Django | `sonas/admin-secure/` |

## Licence

Projet académique / démonstration — usage interne.

## Documentation UML

Modélisation complète (DCU, classes, états, séquences, composants, déploiement) :

- **Markdown :** [docs/README_UML.md](docs/README_UML.md)
- **Word :** [docs/UML_SONAS.docx](docs/UML_SONAS.docx)

Regénérer le fichier Word :

```bash
python scripts/generate_uml_docx.py
```
