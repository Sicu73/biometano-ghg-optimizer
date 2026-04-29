# -*- coding: utf-8 -*-
from __future__ import annotations

TR = {
 'Piano mensile':'Monthly planner','Sintesi annuale':'Annual summary','Database feedstock':'Feedstock database',
 'Scarica CSV':'Download CSV','Scarica Excel':'Download Excel','Scarica PDF':'Download PDF','Report PDF':'PDF report',
 'Excel modificabile':'Editable Excel','Biomassa':'Feedstock','Biomasse':'Feedstocks','Mese':'Month','Anno':'Year','Ore':'Hours',
 'Produzione':'Production','Risparmio GHG':'GHG saving','Emissioni':'Emissions','Conforme':'Compliant','Non conforme':'Not compliant',
 'Parametro':'Parameter','Valore':'Value','Unità':'Unit','Note':'Notes','Soglia':'Threshold','Esito':'Outcome','Totale':'Total',
 'Ricavo':'Revenue','Ricavi':'Revenue','Costo':'Cost','Costi':'Costs','Energia':'Energy','Elettricità':'Electricity','Calore':'Heat',
 'Liquame suino':'Pig slurry','Pollina ovaiole':'Layer manure','Trinciato di mais':'Maize silage','Trinciato di sorgo':'Sorghum silage',
 'Gennaio':'January','Febbraio':'February','Marzo':'March','Aprile':'April','Maggio':'May','Giugno':'June','Luglio':'July','Agosto':'August','Settembre':'September','Ottobre':'October','Novembre':'November','Dicembre':'December'
}

def _lang():
    try:
        import streamlit as st
        return st.session_state.get('lang','it')
    except Exception:
        return 'it'

def _t(x):
    if _lang() != 'en' or not isinstance(x,str): return x
    for a,b in sorted(TR.items(), key=lambda p: len(p[0]), reverse=True):
        x = x.replace(a,b)
    return x

def _selector():
    try:
        import streamlit as st
        if not st.session_state.get('_metaniq_lang_selector'):
            st.sidebar.radio('Lingua / Language', ['it','en'], format_func=lambda v: 'Italiano' if v=='it' else 'English', key='lang')
            st.session_state['_metaniq_lang_selector'] = True
    except Exception:
        pass

def _patch():
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st,'_metaniq_lang_patch',False): return
    def wrap(name):
        old = getattr(st,name,None)
        if old is None: return
        def f(*args, **kwargs):
            _selector(); args=list(args)
            if args: args[0]=_t(args[0])
            for k in ('label','body','help','placeholder'):
                if k in kwargs: kwargs[k]=_t(kwargs[k])
            return old(*args, **kwargs)
        setattr(st,name,f)
    for n in ['title','header','subheader','caption','markdown','write','button','radio','selectbox','multiselect','number_input','text_input','slider','expander']:
        wrap(n)
    if hasattr(st,'tabs'):
        old=st.tabs
        def tabs(names,*a,**k): _selector(); return old([_t(i) for i in names],*a,**k)
        st.tabs=tabs
    for n in ['dataframe','table']:
        old=getattr(st,n,None)
        if old:
            def mk(o):
                def f(data=None,*a,**k):
                    _selector()
                    try:
                        if _lang()=='en' and hasattr(data,'rename'):
                            data=data.rename(columns={c:_t(str(c)) for c in data.columns})
                    except Exception: pass
                    return o(data,*a,**k)
                return f
            setattr(st,n,mk(old))
    if hasattr(st,'download_button'):
        old=st.download_button
        def dl(*args,**kwargs):
            _selector(); args=list(args)
            if args: args[0]=_t(args[0])
            if 'label' in kwargs: kwargs['label']=_t(kwargs['label'])
            if _lang()=='en' and kwargs.get('file_name'):
                fn=kwargs['file_name']
                if '.' in fn:
                    b,e=fn.rsplit('.',1); kwargs['file_name']=b+'_en.'+e
            return old(*args,**kwargs)
        st.download_button=dl
    st._metaniq_lang_patch=True
_patch()
