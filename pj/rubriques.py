"""Rubriques (industries) et villes du Québec les plus utiles pour la prospection.

Ces listes servent uniquement de raccourcis dans l'interface et le CLI :
n'importe quel terme de recherche accepté par PagesJaunes.ca fonctionne.
Le terme est envoyé tel quel au site, comme si on le tapait dans le champ
« Quoi ». Les rubriques officielles donnent les résultats les plus propres.
"""

# Regroupées par famille pour l'affichage dans le formulaire de scraping.
INDUSTRIES = {
    "Construction et rénovation": [
        "Plombiers et entrepreneurs en plomberie",
        "Électriciens",
        "Entrepreneurs généraux",
        "Couvreurs",
        "Entrepreneurs en chauffage",
        "Climatisation et ventilation",
        "Excavation",
        "Entrepreneurs en peinture",
        "Ébénistes",
        "Portes et fenêtres",
        "Entrepreneurs en revêtement de sol",
        "Arpenteurs-géomètres",
        "Architectes",
        "Ingénieurs",
    ],
    "Automobile": [
        "Garages de réparation d'automobiles",
        "Concessionnaires d'automobiles",
        "Carrosseries",
        "Pneus",
        "Remorquage de véhicules",
        "Lave-autos",
    ],
    "Restauration et alimentation": [
        "Restaurants",
        "Traiteurs",
        "Boulangeries",
        "Épiceries",
        "Boucheries",
        "Microbrasseries",
    ],
    "Santé et bien-être": [
        "Dentistes",
        "Cliniques médicales",
        "Physiothérapeutes",
        "Chiropraticiens",
        "Optométristes",
        "Pharmacies",
        "Vétérinaires",
        "Salons de coiffure",
        "Spas",
        "Centres de conditionnement physique",
    ],
    "Services professionnels": [
        "Avocats",
        "Comptables",
        "Comptables agréés",
        "Notaires",
        "Courtiers immobiliers",
        "Assurances",
        "Agences de placement",
        "Agences de publicité",
        "Consultants en informatique",
        "Traducteurs",
    ],
    "Commerce et détail": [
        "Quincailleries",
        "Meubles",
        "Vêtements",
        "Bijouteries",
        "Fleuristes",
        "Animaleries",
        "Magasins de sport",
    ],
    "Industrie et transport": [
        "Fabricants",
        "Métal en feuilles",
        "Soudure",
        "Machinerie industrielle",
        "Camionnage",
        "Déménagement",
        "Entreposage",
        "Gestion des déchets",
        "Distributeurs",
    ],
    "Services aux entreprises et bâtiments": [
        "Entretien ménager commercial",
        "Aménagement paysager",
        "Déneigement",
        "Systèmes de sécurité",
        "Extermination",
        "Imprimeries",
        "Serruriers",
    ],
}

# Aplati, pour la validation et l'autocomplétion.
TOUTES_INDUSTRIES = [nom for groupe in INDUSTRIES.values() for nom in groupe]

# Format attendu par PagesJaunes.ca dans le champ « Où » : « Ville QC ».
VILLES = [
    "Montreal QC",
    "Laval QC",
    "Longueuil QC",
    "Quebec QC",
    "Levis QC",
    "Gatineau QC",
    "Sherbrooke QC",
    "Trois-Rivieres QC",
    "Saguenay QC",
    "Terrebonne QC",
    "Repentigny QC",
    "Brossard QC",
    "Saint-Jerome QC",
    "Saint-Jean-sur-Richelieu QC",
    "Drummondville QC",
    "Granby QC",
    "Blainville QC",
    "Mirabel QC",
    "Shawinigan QC",
    "Rimouski QC",
    "Victoriaville QC",
    "Saint-Hyacinthe QC",
    "Rouyn-Noranda QC",
    "Sorel-Tracy QC",
    "Val-d'Or QC",
    "Alma QC",
    "Sept-Iles QC",
    "Joliette QC",
    "Vaudreuil-Dorion QC",
    "Boucherville QC",
    "Mascouche QC",
    "Salaberry-de-Valleyfield QC",
    "Beloeil QC",
    "Chateauguay QC",
    "Saint-Georges QC",
    "Thetford Mines QC",
    "Baie-Comeau QC",
    "Magog QC",
]

# Recherches provinciales : plus large, mais les résultats sont classés par
# proximité avec le centre de la région, donc à utiliser avec plusieurs pages.
REGIONS = [
    "Quebec QC",
    "Monteregie QC",
    "Laurentides QC",
    "Lanaudiere QC",
    "Estrie QC",
    "Mauricie QC",
    "Outaouais QC",
    "Bas-Saint-Laurent QC",
    "Abitibi-Temiscamingue QC",
    "Cote-Nord QC",
    "Chaudiere-Appalaches QC",
    "Centre-du-Quebec QC",
    "Gaspesie QC",
]
