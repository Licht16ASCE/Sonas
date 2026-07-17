#!/usr/bin/env python
"""
Génère docs/UML_SONAS.docx à partir du contenu UML (stdlib uniquement).
Usage: python scripts/generate_uml_docx.py
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'docs' / 'UML_SONAS.docx'


def _run(text: str, bold: bool = False) -> str:
    props = '<w:b/>' if bold else ''
    return (
        f'<w:r><w:rPr>{props}</w:rPr>'
        f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
    )


def heading(text: str, level: int = 1) -> str:
    style = f'Heading{level}'
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f'{_run(text, bold=True)}</w:p>'
    )


def paragraph(text: str) -> str:
    if not text.strip():
        return '<w:p/>'
    return f'<w:p>{_run(text)}</w:p>'


def bullet(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListParagraph"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f'{_run(text)}</w:p>'
    )


def code_block(text: str) -> str:
    lines = []
    for line in text.strip().split('\n'):
        lines.append(
            f'<w:p><w:pPr><w:pStyle w:val="CodeBlock"/></w:pPr>'
            f'{_run(line)}</w:p>'
        )
    return ''.join(lines)


def table_row(cells: list[str], header: bool = False) -> str:
    row = '<w:tr>'
    for cell in cells:
        tag = 'w:tc'
        inner = (
            f'<w:p>{_run(cell, bold=header)}</w:p>'
        )
        row += f'<{tag}>{inner}</{tag}>'
    row += '</w:tr>'
    return row


def table(headers: list[str], rows: list[list[str]]) -> str:
    body = table_row(headers, header=True)
    for row in rows:
        body += table_row(row)
    return (
        '<w:tbl>'
        '<w:tblPr><w:tblW w:w="5000" w:type="pct"/></w:tblPr>'
        f'{body}</w:tbl><w:p/>'
    )


def build_document_body() -> str:
    parts: list[str] = []

    parts.append(heading('Documentation UML — SONAS', 1))
    parts.append(paragraph(
        'Projet TFC_Francesco — Plateforme de gestion immobilière & sinistres. '
        'Stack : Django 5, PostgreSQL/SQLite, TailwindCSS, Alpine.js. '
        'Version document : Juillet 2026.'
    ))

    # --- 1. Contexte ---
    parts.append(heading('1. Contexte et périmètre', 1))
    parts.append(paragraph(
        'SONAS est une application web Django pour la gestion de clients immobiliers, '
        'biens, contrats d\'assurance, sinistres, documents et notifications. '
        'Deux espaces strictement séparés : /client/ (self-service) et /sonas/ (interne).'
    ))
    parts.append(table(
        ['Espace', 'URL', 'Acteurs'],
        [
            ['Client', '/client/*', 'Client'],
            ['Interne', '/sonas/*', 'Agent, Gérant, Admin'],
        ],
    ))
    parts.append(paragraph('Sécurité : User.role, décorateurs core/decorators.py, RoleProtectionMiddleware, session 20 min.'))

    # --- 2. Acteurs ---
    parts.append(heading('2. Acteurs du système', 1))

    parts.append(heading('2.1 Client (UserRole.CLIENT)', 2))
    for item in [
        'Dashboard : /client/',
        'Déclare biens et sinistres, souscrit contrats',
        'Consulte et upload des documents',
        'Gère profil entreprise et paramètres compte',
        'Restriction : aucun accès à /sonas/',
    ]:
        parts.append(bullet(item))

    parts.append(heading('2.2 Agent (UserRole.AGENT)', 2))
    for item in [
        'Valide biens, active contrats',
        'Instruit sinistres, propose indemnisation',
        'Transmet au gérant (ne clôture pas)',
    ]:
        parts.append(bullet(item))

    parts.append(heading('2.3 Gérant (UserRole.GERANT)', 2))
    for item in [
        'Toutes capacités agent + clôture/rejet sinistres',
        'Lance indemnisation via lancer_indemnisation()',
        'Gère les agents (/sonas/agents/)',
    ]:
        parts.append(bullet(item))

    parts.append(heading('2.4 Administrateur (UserRole.ADMIN)', 2))
    for item in [
        'Clôture sinistres (comme gérant)',
        'Logs audit (/sonas/logs/), système (/sonas/systeme/)',
        'Django Admin (/sonas/admin-secure/)',
    ]:
        parts.append(bullet(item))

    # --- 3. DCU ---
    parts.append(heading('3. Diagramme de cas d\'utilisation (DCU)', 1))
    parts.append(paragraph(
        'Le DCU global distingue l\'espace client (inscription, profil, biens, contrats, '
        'sinistres, documents, notifications) de l\'espace interne (validation biens, '
        'activation contrats, instruction sinistres, indemnisation, clôture, gestion clients, '
        'documents globaux, agents, administration).'
    ))
    parts.append(heading('Cas d\'utilisation Client (principaux)', 2))
    parts.append(table(
        ['ID', 'Cas d\'utilisation', 'URL'],
        [
            ['UC-C01', 'Dashboard', '/client/'],
            ['UC-C04', 'Déclarer bien', '/client/biens/nouveau/'],
            ['UC-C06', 'Souscrire contrat', '/client/contrats/nouveau/'],
            ['UC-C08', 'Déclarer sinistre', '/client/sinistres/nouveau/'],
            ['UC-C11', 'Upload document', '/client/documents/upload/'],
            ['UC-C12', 'Paramètres', '/accounts/parametres/'],
        ],
    ))
    parts.append(heading('Cas d\'utilisation Interne (principaux)', 2))
    parts.append(table(
        ['ID', 'Cas d\'utilisation', 'Accès'],
        [
            ['UC-I09', 'Valider/rejeter bien', 'internal_required'],
            ['UC-I13', 'Activer contrat', 'internal_required'],
            ['UC-I18', 'Traiter sinistre', 'internal_required'],
            ['UC-V01', 'Clôturer/rejeter sinistre', 'gerant_or_admin_required'],
            ['UC-G01', 'Gérer agents', 'gerant_required'],
            ['UC-A02', 'Logs audit', 'admin_required'],
        ],
    ))

    parts.append(heading('Schéma DCU (Mermaid)', 2))
    parts.append(code_block('''flowchart TB
    C((Client)) --> UC1[S'inscrire / Se connecter]
    C --> UC3[Déclarer un bien]
    C --> UC4[Souscrire un contrat]
    C --> UC5[Déclarer un sinistre]
    A((Agent)) --> UC9[Valider bien]
    A --> UC11[Instruire sinistre]
    G((Gérant)) --> UC13[Clôturer sinistre]
    G --> UC16[Gérer agents]
    AD((Admin)) --> UC17[Administration système]'''))

    # --- 4. Classes ---
    parts.append(heading('4. Diagramme de classes', 1))
    parts.append(paragraph(
        'Modèle métier centré sur User, Client, Bien, Contrat, Sinistre, Document, '
        'RapportIndemnisation, Notification, ActionEnAttente.'
    ))
    parts.append(heading('Relations principales', 2))
    for item in [
        'User 1 — 0..1 Client (client_profile)',
        'Client 1 — * Bien, Contrat',
        'Bien 1 — * Contrat',
        'Contrat 1 — * Sinistre',
        'Sinistre 1 — 0..* RapportIndemnisation',
        'Document lié à exactement un : bien OU sinistre OU contrat',
    ]:
        parts.append(bullet(item))

    parts.append(heading('Contrat — méthodes métier', 2))
    for item in [
        'can_declare_sinistre() : contrat ACTIF, non bloqué, plafond disponible',
        'plafond_disponible() : plafond - montant_indemnise_cumule',
        'deduire_indemnisation(montant) : déduction du cumul',
        'invalider_plafond() : statut INACTIF + sinistres_bloques=True',
    ]:
        parts.append(bullet(item))

    parts.append(heading('Schéma classes (Mermaid)', 2))
    parts.append(code_block('''classDiagram
    User "1" --> "0..1" Client
    Client "1" --> "*" Bien
    Client "1" --> "*" Contrat
    Bien "1" --> "*" Contrat
    Contrat "1" --> "*" Sinistre
    Sinistre "1" --> "0..*" RapportIndemnisation
    Bien "1" --> "*" Document
    Sinistre "1" --> "*" Document
    Contrat "1" --> "*" Document'''))

    # --- 5. États ---
    parts.append(heading('5. Diagrammes d\'états', 1))

    parts.append(heading('5.1 Bien', 2))
    parts.append(code_block('''EN_ATTENTE → VALIDE (agent valide)
EN_ATTENTE → REJETE (agent rejette)'''))

    parts.append(heading('5.2 Contrat', 2))
    parts.append(code_block('''BROUILLON → ACTIF (agent active)
ACTIF → INACTIF (plafond épuisé/dépassé)
ACTIF → EXPIRE (date_fin dépassée)'''))

    parts.append(heading('5.3 Sinistre', 2))
    parts.append(code_block('''DECLARE → EN_COURS (agent prend en charge)
EN_COURS → EN_COURS (agent transmet, soumis_validation=True)
EN_COURS → VALIDE (gérant clôture)
EN_COURS → REJETE (gérant rejette)'''))

    # --- 6. Séquences ---
    parts.append(heading('6. Diagrammes de séquence', 1))

    parts.append(heading('6.1 Authentification', 2))
    parts.append(paragraph(
        '1. POST /accounts/login/ → LoginForm.authenticate(). '
        '2. login(request, user). '
        '3. Redirect : CLIENT → /client/, interne → /sonas/. '
        '4. RoleProtectionMiddleware bloque les accès croisés.'
    ))

    parts.append(heading('6.2 Déclaration bien', 2))
    parts.append(paragraph(
        'Client POST bien_create_client → Bien(EN_ATTENTE) → ActiviteClient + '
        'ActionEnAttente(BIEN_INCOMPLET) + notification agents(BIEN_A_VALIDER). '
        'Agent POST bien_validate → VALIDE ou REJETE → notification client.'
    ))

    parts.append(heading('6.3 Contrat + PDF', 2))
    parts.append(paragraph(
        'Client POST contrat_create_client → Contrat(BROUILLON) → generate_contrat_pdf() '
        '→ Document(CONTRAT_PDF) → redirect consolidation. '
        'Agent POST contrat_activate → statut ACTIF → notification client.'
    ))

    parts.append(heading('6.4 Déclaration sinistre', 2))
    parts.append(paragraph(
        'Prérequis : contrat.can_declare_sinistre(). '
        'Sinistre(DECLARE, plafond=plafond_disponible) → pending SINISTRE_INCOMPLET + '
        'notify agents SINISTRE_A_TRAITER.'
    ))

    parts.append(heading('6.5 Traitement agent', 2))
    parts.append(paragraph(
        'Agent POST sinistre_update_status → EN_COURS. '
        'Agent POST sinistre_traiter → indemnisation_accordee, montant, notes, '
        'soumis_validation=True → notify gérants SINISTRE_A_VALIDER.'
    ))

    parts.append(heading('6.6 Clôture gérant', 2))
    parts.append(paragraph(
        'Gérant POST sinistre_validate action=cloturer. '
        'Si indemnisation : lancer_indemnisation() → deduire plafond → '
        'RapportIndemnisation + Document(RAPPORT). '
        'Si plafond dépassé : contrat.invalider_plafond() → INACTIF. '
        'Sans indemnisation : clôture sans déduction.'
    ))

    parts.append(heading('6.7 Upload document', 2))
    parts.append(paragraph(
        'Vérification ACL (_user_can_access_sinistre/bien). '
        'Save Document → resolve pending (SINISTRE_INCOMPLET, BIEN_INCOMPLET, etc.). '
        'Recherche interne : /sonas/documents/ filtres client, type, q.'
    ))

    parts.append(heading('Schéma séquence clôture (Mermaid)', 2))
    parts.append(code_block('''sequenceDiagram
    Gérant->>sinistre_validate: POST cloturer
    sinistre_validate->>lancer_indemnisation: si indemnisation
    lancer_indemnisation->>Contrat: deduire_indemnisation
    lancer_indemnisation->>RapportIndemnisation: create
    lancer_indemnisation->>Document: RAPPORT PDF'''))

    # --- 7. Composants ---
    parts.append(heading('7. Diagramme de composants', 1))
    parts.append(paragraph(
        'Couches : Templates (Tailwind/Alpine) → Views → Forms/Services → Models → DB/media. '
        'Services clés : contrats/services.py (PDF), sinistres/services.py (indemnisation), '
        'documents/services.py (filtres), notifications/services.py.'
    ))

    # --- 8. Déploiement ---
    parts.append(heading('8. Diagramme de déploiement', 1))
    parts.append(paragraph(
        'Navigateur → Django WSGI → PostgreSQL/SQLite + media/. '
        'Optionnel : Redis + Celery (alertes expiration contrats J-30/J-15/J-7/J0).'
    ))

    # --- 9. Matrice ---
    parts.append(heading('9. Matrice acteur × cas d\'utilisation', 1))
    parts.append(table(
        ['Cas d\'utilisation', 'Client', 'Agent', 'Gérant', 'Admin'],
        [
            ['Déclarer bien', 'Oui', 'Oui*', 'Oui*', 'Oui*'],
            ['Valider bien', 'Non', 'Oui', 'Oui', 'Oui'],
            ['Activer contrat', 'Non', 'Oui', 'Oui', 'Oui'],
            ['Traiter sinistre', 'Non', 'Oui', 'Oui', 'Oui'],
            ['Clôturer sinistre', 'Non', 'Non', 'Oui', 'Oui'],
            ['Gérer agents', 'Non', 'Non', 'Oui', 'Non'],
            ['Logs / système', 'Non', 'Non', 'Non', 'Oui'],
            ['Paramètres compte', 'Oui', 'Oui', 'Oui', 'Oui'],
        ],
    ))
    parts.append(paragraph('* Création au nom d\'un client (espace interne)'))

    # --- 10. Références ---
    parts.append(heading('10. Références code source', 1))
    parts.append(table(
        ['Élément', 'Fichier'],
        [
            ['User / rôles', 'accounts/models.py'],
            ['Middleware rôles', 'core/middleware.py'],
            ['Contrat + plafond', 'contrats/models.py'],
            ['PDF contrat', 'contrats/services.py'],
            ['Sinistre', 'sinistres/models.py'],
            ['Indemnisation', 'sinistres/services.py'],
            ['Documents + filtres', 'documents/services.py'],
            ['Notifications', 'notifications/services.py'],
            ['URLs', 'config/urls.py'],
        ],
    ))

    parts.append(paragraph(
        'Document généré pour le TFC SONAS. '
        'Version Markdown complète : docs/README_UML.md'
    ))

    return ''.join(parts)


DOCUMENT_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {body}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
    </w:sectPr>
  </w:body>
</w:document>'''

STYLES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal" w:default="1">
    <w:name w:val="Normal"/>
    <w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:pPr><w:spacing w:before="360" w:after="120"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/><w:color w:val="4338CA"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:pPr><w:spacing w:before="240" w:after="80"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="26"/><w:color w:val="4F46E5"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/>
    <w:pPr><w:ind w:left="720"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock">
    <w:name w:val="Code Block"/>
    <w:pPr><w:ind w:left="360"/></w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr>
  </w:style>
</w:styles>'''

NUMBERING_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="\\u2022"/>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1">
    <w:abstractNumId w:val="0"/>
  </w:num>
</w:numbering>'''

CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>'''

RELS_ROOT = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

RELS_DOC = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>'''


def generate() -> Path:
    body = build_document_body()
    doc_xml = DOCUMENT_XML.format(body=body)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', CONTENT_TYPES)
        zf.writestr('_rels/.rels', RELS_ROOT)
        zf.writestr('word/document.xml', doc_xml.encode('utf-8'))
        zf.writestr('word/styles.xml', STYLES_XML)
        zf.writestr('word/numbering.xml', NUMBERING_XML)
        zf.writestr('word/_rels/document.xml.rels', RELS_DOC)

    return OUTPUT


if __name__ == '__main__':
    path = generate()
    print(f'Generated: {path}')
