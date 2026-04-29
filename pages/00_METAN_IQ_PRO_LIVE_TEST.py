# -*- coding: utf-8 -*-
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Metan.iQ PRO LIVE",
    page_icon="⚡",
    layout="wide",
)

st.title("Metan.iQ PRO LIVE — Carlo Test")
st.success("Se vedi questa pagina, il deploy Streamlit sta caricando le modifiche da GitHub master.")
st.markdown("""
## Nuovo nome software

**Metan.iQ PRO LIVE**

Questa pagina è stata aggiunta per verificare in modo oggettivo che il software live riceve le modifiche dal repository.

### Stato verifica

- Repository: `Sicu73/biometano-ghg-optimizer`
- Branch: `master`
- File visibile: `pages/00_METAN_IQ_PRO_LIVE_TEST.py`
- Obiettivo: prova live di modifica nome software
""")
