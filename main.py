import os
import uuid
import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ==========================================
# 1. CONFIGURATION DE LA BASE DE DONNÉES
# ==========================================
# Railway injecte DATABASE_URL. Si vide (local), on utilise SQLite.
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./nexus_local.db"

# Configuration de SQLAlchemy
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modèle SQL pour la table de logs (Visibilité Railway)
class TicketLog(Base):
    __tablename__ = "ticket_logs"
    id_ticket = Column(String, primary_key=True)
    date_insertion = Column(DateTime, default=datetime.datetime.utcnow)
    utilisateur = Column(String)
    domaine = Column(String)
    score_final = Column(Float)
    ethique_veto = Column(String)
    equipe_cible = Column(String)

# Création automatique des tables au démarrage
Base.metadata.create_all(bind=engine)

# ==========================================
# 2. INITIALISATION DE L'API
# ==========================================
app = FastAPI(
    title="Nexus-Surgical Engine API",
    description="Moteur de qualification et de routage intelligent des tickets.",
    version="1.1"
)

# ==========================================
# 3. MODÈLES DE DONNÉES (Pydantic)
# ==========================================
class TicketEntrant(BaseModel):
    nom_utilisateur: str = Field(..., examples=["Dupont"])
    rang: str = Field(..., examples=["VIP"], description="Stagiaire, Employé, Cadre, Directeur, VIP")
    domaine: str = Field(..., examples=["MÉDICAL"], description="MÉDICAL, INFRA, RH, MATÉRIEL")
    titre: str = Field(..., examples=["Arrêt respiratoire"])
    details: str = Field("", examples=["Le patient ne respire plus."])
    etat_declare: str = Field(..., examples=["URGENT"], description="URGENT ou NORMAL")
    score_base: float = Field(..., examples=[10.0], description="Gravité (0 à 10)")

class DecisionRoutage(BaseModel):
    id_ticket: str
    utilisateur: str
    domaine: str
    score_final: float
    ethique_veto: str
    equipe_cible: str

RANGS = {"Stagiaire": 1, "Employé": 2, "Cadre": 3, "Directeur": 4, "VIP": 5}

# ==========================================
# 4. LOGIQUE MÉTIER
# ==========================================
def calculer_decision(ticket: TicketEntrant) -> dict:
    importance = RANGS.get(ticket.rang, 1)
    est_veto = (ticket.score_base >= 9.0)

    if est_veto:
        score_final = ticket.score_base
        ethique = "OUI (Veto)"
        identite_finale = ticket.nom_utilisateur
    else:
        bonus_sla = (importance / 5.0) * 1.5
        bonus_etat = 0.5 if ticket.etat_declare.upper() == "URGENT" else 0.0
        score_final = min(10.0, ticket.score_base + bonus_sla + bonus_etat)
        ethique = "NON"
        identite_finale = f"{ticket.nom_utilisateur} ({ticket.rang})"

    score_final = round(score_final, 1)

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
# 5. ROUTES (Endpoints)
# ==========================================
@app.get("/")
def health_check():
    return {"statut": "Nexus-Surgical API opérationnelle", "database": DATABASE_URL.split("@")[-1]}

@app.post("/api/v1/router", response_model=DecisionRoutage)
def process_ticket(ticket: TicketEntrant):
    # 1. Calcul de la décision
    res = calculer_decision(ticket)
    
    # 2. Sauvegarde automatique en Base de Données
    db = SessionLocal()
    try:
        new_log = TicketLog(
            id_ticket=res["id_ticket"],
            utilisateur=res["utilisateur"],
            domaine=res["domaine"],
            score_final=res["score_final"],
            ethique_veto=res["ethique_veto"],
            equipe_cible=res["equipe_cible"]
        )
        db.add(new_log)
        db.commit()
    except Exception as e:
        print(f"Erreur Logging: {e}")
    finally:
        db.close()
        
    return res
