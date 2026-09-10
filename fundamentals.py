import json
import os


def charger_financials():
    """Charge les données financières depuis financials.json ou retourne un dictionnaire par défaut."""
    if os.path.exists("financials.json"):
        try:
            with open("financials.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Données par défaut si le fichier json n'est pas présent
    return {
        "NTLC": {
            "Nom": "NESTLE CI",
            "Secteur": "Industrie",
            "BPA": 650.0,
            "VNC": 2200.0,
            "Dividende": 520.0,
            "ROE": 25.5,
            "PER": 9.8,
            "CapitauxPropres": 35000000000,
            "ResultatNet": 10500000000,
            "Capitalisation": 120000000000,
        },
        "ABJC": {
            "Nom": "SERVAIR ABIDJAN CI",
            "Secteur": "Services",
            "BPA": 280.0,
            "VNC": 1400.0,
            "Dividende": 229.0,
            "ROE": 18.2,
            "PER": 12.5,
            "CapitauxPropres": 18000000000,
            "ResultatNet": 3800000000,
            "Capitalisation": 45000000000,
        },
        "SMBC": {
            "Nom": "SMB CI",
            "Secteur": "Industrie",
            "BPA": 1450.0,
            "VNC": 6200.0,
            "Dividende": 800.0,
            "ROE": 22.0,
            "PER": 8.5,
            "CapitauxPropres": 42000000000,
            "ResultatNet": 9800000000,
            "Capitalisation": 85000000000,
        },
        "BOAC": {
            "Nom": "BANK OF AFRICA CI",
            "Secteur": "Finances",
            "BPA": 510.0,
            "VNC": 3100.0,
            "Dividende": 380.0,
            "ROE": 16.5,
            "PER": 14.07,
            "CapitauxPropres": 95000000000,
            "ResultatNet": 15500000000,
            "Capitalisation": 210000000000,
        },
        "NEIC": {
            "Nom": "NEI-CEDA CI",
            "Secteur": "Services",
            "BPA": 45.0,
            "VNC": 350.0,
            "Dividende": 30.0,
            "ROE": 12.0,
            "PER": 11.2,
            "CapitauxPropres": 5000000000,
            "ResultatNet": 650000000,
            "Capitalisation": 7500000000,
        },
        "TTLC": {
            "Nom": "TOTALENERGIES MARKETING CI",
            "Secteur": "Distribution",
            "BPA": 190.0,
            "VNC": 1100.0,
            "Dividende": 160.0,
            "ROE": 17.0,
            "PER": 10.5,
            "CapitauxPropres": 28000000000,
            "ResultatNet": 4900000000,
            "Capitalisation": 55000000000,
        },
    }


def analyser_valeur_et_fondamentaux(ticker, cours):
    """Calcule le Nombre de Graham, la marge de sécurité et le score synthétique."""
    financials = charger_financials()
    data = financials.get(ticker)

    if not data:
        return None

    bpa = float(data.get("BPA", 0))
    vnc = float(data.get("VNC", 0))
    dividende = float(data.get("Dividende", 0))
    roe = float(data.get("ROE", 0))
    pe_ratio = float(data.get("PER", 0))

    # Nombre de Graham = sqrt(22.5 * BPA * VNC)
    produit = 22.5 * bpa * vnc
    nombre_graham = produit**0.5 if produit > 0 else 0

    marge_securite = (
        ((nombre_graham - cours) / nombre_graham) * 100
        if nombre_graham > 0
        else 0
    )
    dividend_yield = (dividende / cours * 100) if cours > 0 else 0
    pb_ratio = (cours / vnc) if vnc > 0 else 0
    payout_ratio = (dividende / bpa * 100) if bpa > 0 else 0

    # Score synthétique sur 100
    score = 50.0
    if marge_securite > 20:
        score += 20
    elif marge_securite > 0:
        score += 10

    if dividend_yield >= 7.0:
        score += 15
    elif dividend_yield >= 4.0:
        score += 8

    if roe >= 15.0:
        score += 15
    elif roe >= 10.0:
        score += 7

    score = min(100.0, max(0.0, score))

    return {
        "nom": data.get("Nom", ticker),
        "secteur": data.get("Secteur", "Inconnu"),
        "bpa": bpa,
        "vnc": vnc,
        "dividende": dividende,
        "roe": roe,
        "pe_ratio": pe_ratio,
        "pb_ratio": round(pb_ratio, 2),
        "dividend_yield": round(dividend_yield, 2),
        "payout_ratio": round(payout_ratio, 1),
        "nombre_graham": round(nombre_graham, 0),
        "marge_securite_graham": round(marge_securite, 1),
        "score_composite": round(score, 1),
        "capitalisation": data.get("Capitalisation", 0),
        "resultat_net_total": data.get("ResultatNet", 0),
        "capitaux_propres_totaux": data.get("CapitauxPropres", 0),
    }