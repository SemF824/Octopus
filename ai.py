from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uuid

# ==========================================
# 1. INITIALISATION DE L'API
# ==========================================
app = FastAPI(
    title="Nexus-Surgical Engine API",
    description="Moteur de qualification et de routage intelligent des tickets de support.",
    version="1.0"
)


# ==========================================
# 2. MODÈLES DE DONNÉES (Validation stricte)
# ==========================================
# Pydantic s'assure que les données envoyées par le client sont correctes avant même le traitement.
class TicketEntrant(BaseModel):
    nom_utilisateur: str = Field(..., examples=["Dupont"])
    rang: str = Field(
        ...,
        examples=["VIP"],
        description="Stagiaire, Employé, Cadre, Directeur, VIP"
    )
    domaine: str = Field(
        ...,
        examples=["MÉDICAL"],
        description="MÉDICAL, INFRA, RH, MATÉRIEL"
    )
    titre: str = Field(..., examples=["Arrêt respiratoire"])
    details: str = Field("", examples=["Le patient ne respire plus."])
    etat_declare: str = Field(
        ...,
        examples=["URGENT"],
        description="URGENT ou NORMAL"
    )
    score_base: float = Field(
        ...,
        examples=[10.0],
        description="Gravité intrinsèque du problème (0 à 10)"
    )

class DecisionRoutage(BaseModel):
    id_ticket: str
    utilisateur: str
    domaine: str
    score_final: float
    ethique_veto: str
    equipe_cible: str


# Dictionnaire des importances (SLA)
RANGS = {"Stagiaire": 1, "Employé": 2, "Cadre": 3, "Directeur": 4, "VIP": 5}


# ==========================================
# 3. LE CŒUR DU MOTEUR (Logique Métier)
# ==========================================
def calculer_decision(ticket: TicketEntrant) -> dict:
    # Récupération de l'importance (SLA), par défaut 1 si inconnu
    importance = RANGS.get(ticket.rang, 1)

    # Règle de Veto Éthique (Sécurité maximale)
    est_veto = (ticket.score_base >= 9.0)

    if est_veto:
        score_final = ticket.score_base
        ethique = "OUI (Veto)"
        identite_finale = ticket.nom_utilisateur  # On masque le rang
    else:
        # Formule de calcul avec Bonus
        # Score = Base + Bonus SLA (Max 1.5) + Bonus Urgence (0.5)
        bonus_sla = (importance / 5.0) * 1.5
        bonus_etat = 0.5 if ticket.etat_declare.upper() == "URGENT" else 0.0

        score_final = min(10.0, ticket.score_base + bonus_sla + bonus_etat)
        ethique = "NON"
        identite_finale = f"{ticket.nom_utilisateur} ({ticket.rang})"

    score_final = round(score_final, 1)

    # Matrice de Routage
    if score_final >= 9.0:
        equipe = f"TASK FORCE {ticket.domaine.upper()}"
    elif score_final >= 5.0:
        equipe = f"EXPERTS {ticket.domaine.upper()}"
    else:
        equipe = "SUPPORT N1"

    return {
        "id_ticket": f"TKT-{uuid.uuid4().hex[:6].upper()}",
        "utilisateur": identite_finale,
        "domaine": ticket.domaine,
        "score_final": score_final,
        "ethique_veto": ethique,
        "equipe_cible": equipe
    }


# ==========================================
# 4. LES ROUTES DE L'API (Endpoints)
# ==========================================
@app.get("/")
def health_check():
    """Vérifie que le moteur est en ligne."""
    return {"statut": "Nexus-Surgical API en ligne et opérationnelle."}


@app.post("/api/v1/router", response_model=DecisionRoutage)
def process_ticket(ticket: TicketEntrant):
    """
    Reçoit un ticket en JSON, applique les règles métier et renvoie la décision de routage.
    """
    try:
        decision = calculer_decision(ticket)
        # 💡 Plus tard, c'est ICI que tu ajouteras : db.log_ticket(decision)
        return decision
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul : {str(e)}")
