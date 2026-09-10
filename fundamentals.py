import json
import math
import os

FINANCIALS_FILE = "financials.json"


def charger_financials():
    """Charge le fichier financials.json s'il existe."""
    if not os.path.exists(FINANCIALS_FILE):
        return {}
    try:
        with open(FINANCIALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def analyser_valeur_et_fondamentaux(ticker, cours_actuel):
    """Analyse une action à partir de financials.json et du cours du jour."""
    financials = charger_financials()
    if ticker not in financials:
        return None

    data = financials[ticker]
    nom = data.get("Nom", ticker)
    secteur = data.get("Secteur", "N/A")
    bpa = float(data.get("BPA", 0))
    dividende = float(data.get("Dividende", 0))
    nb_actions = int(data.get("Nombre_Actions", 0))
    vnc = float(data.get("VNC", 0))

    # --- RATIOS DE VALORISATION ---
    pe_ratio = (cours_actuel / bpa) if bpa > 0 else 0
    pb_ratio = (cours_actuel / vnc) if vnc > 0 else 0
    dividend_yield = (
        (dividende / cours_actuel * 100) if cours_actuel > 0 else 0
    )
    payout_ratio = (dividende / bpa * 100) if bpa > 0 else 0
    roe = (bpa / vnc * 100) if vnc > 0 else 0

    # --- NOMBRE DE GRAHAM ET MARGE DE SÉCURITÉ ---
    # Formule Benjamin Graham : sqrt(22.5 * BPA * VNC)
    if bpa > 0 and vnc > 0:
        nombre_graham = math.sqrt(22.5 * bpa * vnc)
        marge_securite_graham = (
            ((nombre_graham - cours_actuel) / nombre_graham) * 100
            if nombre_graham > 0
            else 0
        )
    else:
        nombre_graham = 0
        marge_securite_graham = 0

    # Totaux d'entreprise
    capitalisation = cours_actuel * nb_actions
    resultat_net_total = bpa * nb_actions
    capitaux_propres_totaux = vnc * nb_actions

    # --- CALCUL DU SCORE FONDAMENTAL COMPOSITE (0 - 100) ---
    score = 0

    # 1. Rendement du dividende (Max 25 pts)
    if dividend_yield >= 8.0:
        score += 25
    elif dividend_yield >= 5.0:
        score += 15
    elif dividend_yield > 0:
        score += 8

    # 2. Marge de sécurité Graham (Max 25 pts)
    if marge_securite_graham >= 20.0:
        score += 25
    elif marge_securite_graham > 0:
        score += 15

    # 3. Valorisation P/E (Max 25 pts)
    if 0 < pe_ratio <= 10:
        score += 25
    elif 10 < pe_ratio <= 15:
        score += 15
    elif pe_ratio > 15:
        score += 5

    # 4. Rentabilité ROE (Max 25 pts)
    if roe >= 15.0:
        score += 25
    elif roe >= 10.0:
        score += 15
    elif roe > 0:
        score += 8

    return {
        "ticker": ticker,
        "nom": nom,
        "secteur": secteur,
        "cours_actuel": cours_actuel,
        "bpa": bpa,
        "dividende": dividende,
        "vnc": vnc,
        "nb_actions": nb_actions,
        "capitalisation": capitalisation,
        "resultat_net_total": resultat_net_total,
        "capitaux_propres_totaux": capitaux_propres_totaux,
        "pe_ratio": round(pe_ratio, 2),
        "pb_ratio": round(pb_ratio, 2),
        "dividend_yield": round(dividend_yield, 2),
        "payout_ratio": round(payout_ratio, 2),
        "roe": round(roe, 2),
        "nombre_graham": round(nombre_graham, 0),
        "marge_securite_graham": round(marge_securite_graham, 2),
        "score_composite": min(100, score),
    }