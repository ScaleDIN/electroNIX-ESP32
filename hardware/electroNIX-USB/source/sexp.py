import re
TOK=re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')
class Sym(str): pass
def parse(s):
    stack=[[]];pos=0
    for m in TOK.finditer(s):
        o,c,q,a=m.groups()
        if o: stack.append([])
        elif c: x=stack.pop(); stack[-1].append(x)
        elif q is not None: stack[-1].append(q[1:-1].replace('\\"','"').replace('\\\\','\\'))
        elif a is not None: stack[-1].append(Sym(a))
    return stack[0][0]
def dump(x,ind=0):
    if isinstance(x,list):
        if not x: return '()'
        simple=all(not isinstance(e,list) for e in x)
        if simple: return '('+' '.join(dump(e) for e in x)+')'
        out='('+dump(x[0])
        for e in x[1:]:
            out+='\n'+'  '*(ind+1)+dump(e,ind+1) if isinstance(e,list) else ' '+dump(e)
        return out+')'
    if isinstance(x,Sym): return str(x)
    if isinstance(x,(int,float)):
        if isinstance(x,float): return ('%.4f'%x).rstrip('0').rstrip('.')
        return str(x)
    return '"'+str(x).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def find(x,tag): return [e for e in x if isinstance(e,list) and e and e[0]==tag]
def find1(x,tag):
    r=find(x,tag); return r[0] if r else None
