# Carnet de prospection Québec — source de la page

`carnet.html` est le code de la page publiée à
https://claude.ai/code/artifact/aea59a3f-49a6-429f-a6d0-9c96ea273016

Ce n'est pas un fichier HTML autonome : il est publié comme Artefact sur
claude.ai, qui l'enveloppe dans un squelette (`<!doctype>`, `<head>`, `<body>`)
et lui accorde des capacités d'exécution. D'où deux particularités :

- le fichier commence directement par `<title>` et `<style>`, sans balises
  `<html>` ni `<body>` ;
- les fiches et les notes ne sont pas dans le fichier. Elles vivent dans le
  magasin de documents de l'artefact, que la page lit via
  `claude.use("db")` et la collection `leads`. Ouvert hors de claude.ai, le
  fichier s'affiche donc mais reste vide — c'est prévu et géré.

## Format d'un document `leads/<id de fiche PagesJaunes>`

```json
{
  "nom": "Excavation Gagnon",
  "tel": "418-722-3630",
  "tels": ["418-722-3630", "418-730-3630"],
  "secteur": "Entrepreneurs en excavation",
  "adresse": "103-190 rue du Hâvre",
  "ville": "Rimouski",
  "province": "QC",
  "cp": "G5M 0B9",
  "web": "http://www.excavationgagnon.ca/",
  "annonce": false,
  "urlPj": "https://www.pagesjaunes.ca/bus/...",
  "statut": "a_appeler",
  "notes": [{"d": "2026-09-08T14:12:00Z", "t": "Rappeler lundi", "r": "repondu"}]
}
```

Les champs saisis pendant les appels — `statut`, `notes`, `rappel`, `contact`,
`courriel` — sont écrits par la page. `scripts/preparer_carnet.py` produit les
autres. Un ajout de fiches n'écrit que des identifiants nouveaux : les notes
existantes ne sont jamais touchées.

## Mettre la page à jour

Republier ce fichier sur la même URL depuis une session Claude Code. Les
capacités déclarées (`db`, `downloads`) se reportent d'elles-mêmes si on ne
les repasse pas.
