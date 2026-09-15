# Site — Ludovic Laidié, ultra gravel

Une page d'histoire dont les chiffres se mettent à jour tout seuls, et un carnet
où chaque post publié devient un article classé par thématique.

```
index.html          De Honfleur aux Badlands (page principale, générée)
blog.html           Le carnet, sommaire par thématique (généré)
<slug>.html         un article par fichier de content (générés)
content/            les articles, en texte simple
  _modele.md        le gabarit à copier pour chaque nouveau post
assets/site.css     toute la mise en forme du site
img/                photos
build/build.py      construit tout
build/templates/    les gabarits de page
.github/workflows/  la tâche qui reconstruit et publie
```

Rien ne se modifie dans les fichiers `.html` de la racine : ils sont réécrits à
chaque construction. Le texte vit dans `content/`, la mise en forme dans
`assets/site.css`, la structure dans `build/templates/`.

## Mise en ligne, une seule fois

### 1. Le dépôt GitHub

1. Sur github.com, bouton **New repository**. Nom au choix, par exemple `velo`.
   Laisse-le public et coche **Add a README** pour que la branche `main` existe.
2. Sur la page du dépôt, **Add file → Upload files**, glisse tout le contenu de
   ce dossier, puis **Commit changes**.

Si le dossier `.github` ne monte pas (certains navigateurs ignorent les dossiers
qui commencent par un point), crée le fichier à la main : **Add file → Create
new file**, tape `.github/workflows/refresh.yml` comme nom, colle le contenu.

### 2. Cloudflare Pages

1. Compte gratuit sur dash.cloudflare.com.
2. **Workers & Pages → Create → Pages → Connect to Git**, autorise GitHub,
   choisis le dépôt.
3. Réglages : **Framework preset** sur `None`, **Build command** vide,
   **Build output directory** sur `/`.
4. **Save and Deploy**.

Une minute plus tard le site est en ligne sur `https://<projet>.pages.dev`.
C'est cette adresse qui va dans la bio Instagram.

Cloudflare surveille ensuite la branche `main` : chaque commit est en ligne dans
la minute, sans rien repartager.

### 3. Les chiffres qui se mettent à jour seuls

1. Sur intervals.icu : **Settings → Developer → API key**, copie la clé.
2. Sur GitHub : **Settings → Secrets and variables → Actions → New repository
   secret**. Crée `ICU_API_KEY` avec la clé, puis `ICU_ATHLETE_ID` avec
   `i384564`.
3. Onglet **Actions → Construire le site → Run workflow** pour un premier
   passage.

La tâche tourne ensuite chaque nuit à 4h30, recalcule le graphique des semaines
et le compteur « depuis janvier 2025 », et commit si ça a bougé. Cloudflare
redéploie dans la foulée.

Si la clé manque ou qu'intervals.icu ne répond pas, le script garde les derniers
chiffres connus et le site reste en ligne.

## Publier un article

1. Copier `content/_modele.md` sous un nom daté, par exemple
   `content/2026-09-20-pneus-gravelman.md`.
2. Remplir l'entête et coller le texte du post.
3. Commit. La tâche reconstruit l'article et le sommaire, Cloudflare publie.

L'entête :

```
---
titre: Pression des pneus en Sologne
date: 2026-09-20
theme: Le matériel
resume: Une phrase qui s'affiche dans le sommaire et sous le titre.
slug: pneus-sologne
---
```

Thématiques disponibles, à recopier telles quelles : `Les données`,
`Le matériel`, `La course`, `La nutrition`, `Le récit`. Une thématique inconnue
crée simplement une nouvelle section en bas du sommaire.

Le `slug` fixe l'adresse (`pneus-sologne.html`). Une fois l'article partagé, ne
plus y toucher.

Mise en forme du texte : une ligne vide entre deux paragraphes, `## ` pour un
intertitre, `**gras**`, `- ` pour une liste, `> ` pour une citation mise en
avant, et des accents graves autour d'un chiffre pour le passer en chiffres
tabulaires. Les tableaux et les graphiques s'écrivent en HTML directement dans
le fichier, comme dans `content/2026-09-14-ventilation.md`.

## Tester sur ta machine

```bash
python3 build/build.py --articles-only   # sans appeler intervals.icu
python3 -m http.server 8000              # puis http://localhost:8000
```
