# -*- coding: utf-8 -*-
"""Tests per il campo e_l (Land Use Change) — Patch 8.

Verifica:
1. La formula calculate_emission_total accetta e include e_l
2. Le voci food/feed nel FEEDSTOCK_DB hanno e_l=0.0 + requires_no_luc_declaration=True
3. Le voci Annex IX (sottoprodotti/effluenti) hanno e_l=0.0
4. La firma originale (senza e_l) resta backward-compatible
"""
import pytest

from emission_factors_override import calculate_emission_total


class TestCalculateEmissionTotalWithEl:
    def test_backward_compat_senza_e_l(self):
        """Vecchie chiamate senza e_l devono comportarsi come prima."""
        v = calculate_emission_total(eec=10, esca=0, etd=1, ep=5)
        assert v == 10 + 1 + 5 - 0

    def test_e_l_aggiunge_alla_somma(self):
        """e_l si aggiunge al totale (RED III All. V Parte C)."""
        v = calculate_emission_total(eec=10, esca=0, etd=1, ep=5, e_l=3)
        assert v == 10 + 3 + 1 + 5 - 0

    def test_e_l_negativo_consentito(self):
        """e_l <0 (ripristino LUC virtuoso) consentito tecnicamente."""
        v = calculate_emission_total(eec=10, esca=0, etd=1, ep=5, e_l=-2)
        assert v == 10 - 2 + 1 + 5

    def test_esca_sottrae_anche_con_e_l(self):
        v = calculate_emission_total(eec=10, esca=3, etd=1, ep=5, e_l=2)
        assert v == 10 + 2 + 1 + 5 - 3

    def test_extra_credits_sottratti(self):
        v = calculate_emission_total(eec=10, esca=0, etd=1, ep=5,
                                      e_l=2, extra_credits=4)
        assert v == 10 + 2 + 1 + 5 - 4


class TestFeedstockDbHasEl:
    def test_food_feed_crops_have_e_l_and_no_luc_flag(self):
        """Colture dedicate (mais, sorgo, ...) devono avere e_l=0 e flag."""
        import sys
        from pathlib import Path
        # Carica app_mensile come modulo per leggere FEEDSTOCK_DB
        if "app_mensile" not in sys.modules:
            try:
                import app_mensile  # noqa: F401
            except Exception:
                pytest.skip("app_mensile non importabile (richiede Streamlit context)")
        from app_mensile import FEEDSTOCK_DB
        food_feed = [n for n, d in FEEDSTOCK_DB.items()
                     if d.get("cat") == "Colture dedicate"]
        assert food_feed, "Nessuna coltura dedicata trovata nel DB"
        for name in food_feed:
            d = FEEDSTOCK_DB[name]
            assert "e_l" in d, f"{name} senza e_l"
            assert d["e_l"] == 0.0, f"{name} ha e_l != 0 (default deve essere 0)"
            assert d.get("requires_no_luc_declaration") is True, (
                f"{name} senza flag requires_no_luc_declaration"
            )
            assert d.get("annex_ix") is None, (
                f"{name} ha annex_ix valorizzato — incoerente per food/feed"
            )

    def test_manure_have_baseline_assumption(self):
        """Effluenti zootecnici con manure credit devono avere baseline doc."""
        import sys
        if "app_mensile" not in sys.modules:
            try:
                import app_mensile  # noqa: F401
            except Exception:
                pytest.skip("app_mensile non importabile")
        from app_mensile import FEEDSTOCK_DB
        effluenti = [n for n, d in FEEDSTOCK_DB.items()
                     if d.get("cat") == "Effluenti zootecnici"]
        assert effluenti, "Nessun effluente zootecnico trovato"
        for name in effluenti:
            d = FEEDSTOCK_DB[name]
            assert d.get("baseline_assumption"), (
                f"{name} senza baseline_assumption (Patch 10 incompleta)"
            )
            assert d.get("baseline_warning"), (
                f"{name} senza baseline_warning (Patch 10 incompleta)"
            )
            assert d.get("e_l") == 0.0, f"{name} e_l != 0 (sottoprodotto)"
