import json,re,sys,os
E=json.load(open(sys.argv[1])); root=sys.argv[2]; dry='--dry' in sys.argv
texts={}
bad=0
for x in E:
    p=os.path.join(root,x['file'])
    s=texts.get(p) or open(p).read()
    pat=r'\s+'.join(re.escape(t) for t in x['old'].split())
    m=list(re.finditer(pat,s))
    if len(m)!=1: print('FAIL',x['id'],x['file'],len(m),x['old'][:60]); bad+=1; texts[p]=s; continue
    s=s[:m[0].start()]+x['new']+s[m[0].end():]; texts[p]=s
if not dry:
    for p,s in texts.items(): open(p,'w').write(s)
print('fails',bad)
