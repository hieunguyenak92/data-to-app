# Data to App

### Vos fichiers deviennent des logiciels. Vos décisions survivent au prochain import.

[English](README.md) · [Tiếng Việt](README.vi.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [简体中文](README.zh-CN.md) · [ไทย](README.th.md) · [Français](README.fr.md)

**Confiez à Claude ou Codex vos fichiers et un vrai travail. Recevez une application que vous pouvez exécuter, examiner et vous approprier.**

Data to App transforme CSV et Excel en logiciel opérationnel attentif à l'origine des données : fiches consultables, vues utiles, modifications autorisées et imports répétés. L'agent façonne le parcours ; un moteur déterministe Python/SQLite distingue les fiches sources, les modifications locales et les nouveaux instantanés. Vous recevez l'application fonctionnelle, son code et ses données locales.

**[Créez votre premier espace](#lancer-lespace-de-stock)** · **[Installer pour Claude ou Codex](docs/INSTALL.md)** · **[Explorer le contrat de données](docs/DATA-CONTRACT.md)** · **[Explorer la démonstration guidée](https://hieunguyenak92.github.io/data-to-app/)**

![Espace de stock synthétique généré par Data to App](docs/assets/workspace.jpg)

*Runtime local réel avec données synthétiques. Le nouvel instantané a été rapproché tout en conservant une décision locale.*

> **Le prochain import, en clair.** La valeur source est `12`. Vous la changez en `20`. Le nouveau fichier indique `14`. Data to App conserve votre `20` et présente le conflit entre source, local et nouvel import pour vous laisser décider. Les changements identiques convergent ; les décisions différentes restent visibles.

## Commencez par un vrai travail

Après [l'installation de la skill](docs/INSTALL.md), demandez à l'agent :

> Utilise Data to App sur `./exports`. Construis un outil local de stock avec recherche, vue des articles sous le seuil et modification des seuils de réapprovisionnement et des notes. Conserve ces modifications au prochain import et montre les changements qui demandent une décision. Lance l'application et vérifie les actions principales.

La skill conduit l'agent à examiner les fichiers, choisir les identifiants et opérations, construire l'application et l'utiliser. Vous décrivez le travail ; l'agent établit le modèle technique. Une ambiguïté importante sur une clé, une unité ou une règle métier peut demander une réponse claire de votre part.

Elle convient notamment aux exports de stock et de commandes, aux contacts à corriger régulièrement et aux dossiers de projets ou de services reçus par fichiers périodiques. La première version se concentre sur des tables locales ayant chacune une clé et sur les parcours demandés.

## Conçue pour le deuxième import

| Capacité | Ce qu'elle apporte |
| --- | --- |
| **Profilage attentif à l'identité** | Des éléments sur les clés candidates, valeurs manquantes, doublons et identifiants à zéros initiaux. |
| **Vérification des jointures** | Des clés sans correspondance et risques de multiplication des lignes détectés avant combinaison. |
| **Rapprochement à trois voies** | Source, local et nouvel import séparés, avec décisions par champ lors d'un conflit. |
| **Aperçu d'import** | Ajouts, mises à jour, fiches absentes et conflits visibles avant application de l'instantané. |
| **Interface opérationnelle** | Recherche, vues configurées, édition autorisée, résolution des conflits, historique et export CSV. |
| **Code applicatif portable** | Une application Python/SQLite avec ressources locales, indépendante de la skill installée. |

Ces mécanismes fournissent des éléments de décision à l'agent. Une colonne unique est une clé candidate, sans prouver une identité métier durable. Une jointure réussie techniquement ne démontre pas que ses totaux ont le sens attendu.

## Lancer l'espace de stock

Il faut **Python 3.10+**. L'import CSV et l'environnement généré utilisent la bibliothèque standard. Les données incluses sont synthétiques.

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

Ouvrez **http://127.0.0.1:8765**. Recherchez un produit, ouvrez son éditeur, modifiez un champ autorisé puis exportez le résultat. L'état est conservé dans la base SQLite propre à l'espace, y compris après redémarrage.

Pour prévisualiser l'instantané de produits suivant, utilisez un autre terminal dans le répertoire du dépôt :

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

Ajoutez `--apply` pour l'appliquer ou utilisez l'aperçu et la confirmation dans l'application. Modifiez un champ qui change aussi dans le nouveau fichier pour observer la résolution des conflits.

Un import représente **l'instantané complet d'une table**. Les fiches absentes sont marquées manquantes et conservées. Un export partiel marquera donc comme manquantes les fiches omises. Les changements de schéma et clés dupliquées portant des valeurs différentes sont rejetés avant modification.

## Utiliser vos fichiers

Un CSV est une table texte ; un XLSX est un classeur Excel. Pour les XLSX, installez le lecteur optionnel dans l'environnement Python qui exécute les outils :

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

Limites d'entrée : **10 MiB par fichier, 50,000 lignes par table, 200 colonnes et 1,000,000 cellules**. XLSX utilise la première feuille par défaut et signale les autres. Les formules ne sont pas recalculées.

Commencez avec la demande ci-dessus ou examinez directement les fichiers :

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
```

L'agent peut s'appuyer sur le profil pour configurer le modèle et construire l'espace. Les procédures techniques sont dans le [guide d'installation et de CLI en anglais](docs/INSTALL.md).

## Export, propriété et limites

Le CSV exporté contient les valeurs effectives des fiches actives, avec les modifications locales acceptées. La protection contre les formules peut ajouter une apostrophe devant certaines cellules exportées à risque ; les valeurs internes restent inchangées. Les fiches manquantes restent conservées localement.

Le serveur généré écoute sur `127.0.0.1`, sert des ressources locales et n'exige aucun service hébergé pour ses fonctions centrales. Pendant la construction, les politiques de fichiers et de données de votre hôte d'IA continuent de s'appliquer. Bases, entrées et exports peuvent contenir des données sensibles. [Confidentialité, en anglais](docs/PRIVACY.md).

Cette version est un espace local, sans authentification multiutilisateur ni garantie de déploiement cloud. Elle n'exécute pas les formules de tableur et ne promet ni déduction de toutes les règles métier, ni migration arbitraire de schéma, ni restauration universelle. Vérifiez les résultats importants avant leur utilisation opérationnelle.

**Commencez avec l'espace synthétique. Puis confiez un vrai travail à votre agent.**
