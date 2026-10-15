import copy,os
from sexp import *
LIBDIR='/usr/share/kicad/symbols'
_cache={}
def lib(name,path=None):
    if name not in _cache:
        _cache[name]=parse(open(path or f'{LIBDIR}/{name}.kicad_sym').read())
    return _cache[name]
EXTRA={}
def raw(libname,sym):
    L=lib(libname,EXTRA.get(libname))
    for s in find(L,'symbol'):
        if s[1]==sym: return s
    raise KeyError(libname+':'+sym)
def flat(libname,sym):
    s=copy.deepcopy(raw(libname,sym))
    ext=find1(s,'extends')
    if ext:
        p=flat(libname,ext[1])
        props={e[1]:e for e in find(s,'property')}
        out=[Sym('symbol'),sym]
        for e in p[2:]:
            if isinstance(e,list) and e[0]=='property' and e[1] in props: out.append(props.pop(e[1]))
            elif isinstance(e,list) and e[0]=='symbol':
                e=copy.deepcopy(e); e[1]=e[1].replace(ext[1],sym,1); out.append(e)
            else: out.append(e)
        out[2:2]=[]
        for v in props.values(): out.append(v)
        s=out
    return s
def pins(libname,sym,unit=1):
    s=flat(libname,sym); res={}
    for u in find(s,'symbol'):
        parts=u[1].rsplit('_',2); un=int(parts[1]); st=int(parts[2])
        if un not in (0,unit) or st not in (0,1): continue
        for p in find(u,'pin'):
            at=find1(p,'at'); num=find1(p,'number')[1]; nm=find1(p,'name')[1]
            ln=find1(p,'length'); res.setdefault(num,[]).append(dict(x=float(at[1]),y=float(at[2]),a=float(at[3]) if len(at)>3 else 0.0,name=nm,num=num,type=str(p[1]),len=float(ln[1])))
    return res
