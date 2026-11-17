"""Rebuild the evaluation figure from explicitly qualified reported values."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
P=Path(__file__).resolve().parent
D=json.loads((P/'evaluation-data.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':8.5,'axes.labelsize':8,'xtick.labelsize':7.5,'ytick.labelsize':7.5,'pdf.fonttype':42,'ps.fonttype':42,'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#77848c','axes.linewidth':.6,'grid.color':'#dce3e8','grid.linewidth':.5})
fig=plt.figure(figsize=(7,1.92),layout=None)
a=fig.add_axes([.073,.30,.365,.52]);b=fig.add_axes([.700,.30,.245,.52])
blue='#246083';teal='#23675b';grey='#7c8993'
x=D['selective_curve']['coverage_percent'];y=D['selective_curve']['accepted_accuracy_percent']
a.plot(x,y,color=blue,marker='o',markersize=3.8,linewidth=1.55,zorder=3)
for xx,yy in zip(x,y):
 a.annotate(f'{yy:.1f}',(xx,yy),xytext=(0,7),textcoords='offset points',ha='center',fontsize=7.1,color=blue)
a.set(xlim=(47,103),ylim=(83.8,96),xticks=x,yticks=[85,90,95],xlabel='Nominal accepted coverage (%)',ylabel='Accepted-case accuracy (%)')
a.grid(axis='y');a.set_title('(a) Selective operating points',loc='left',pad=9,fontweight='bold')
fig.text(.073,.015,'Presentation curve; nominal 972 pairs',fontsize=7,color='#56616b')
items=D['fusion_accuracy'];ys=list(range(len(items)))
for i,t in enumerate(items):
 c=teal if i==4 else grey if i==1 else blue
 b.plot(t['accuracy_percent'],i,'o',color=c,markersize=4.4 if i==4 else 3.6,zorder=3)
 b.annotate(f"{t['accuracy_percent']:.2f}",(t['accuracy_percent'],i),xytext=(5,0),textcoords='offset points',va='center',fontsize=7.3,color=c,fontweight='bold' if i==4 else 'normal')
b.set(yticks=ys,yticklabels=[t['name'] for t in items],xlim=(74,90),ylim=(-.65,4.65),xticks=[75,80,85,90],xlabel='Human-agreement accuracy (%)')
b.grid(axis='x');b.spines['left'].set_visible(False);b.tick_params(axis='y',length=0,pad=5)
b.set_title('(b) Full-coverage fusion',loc='left',pad=9,fontweight='bold')
fig.text(.555,.015,'Saved report; 986 pairs / 128 groups',fontsize=7,color='#56616b')
fig.savefig(P/'evaluation-results.pdf',metadata={'Title':'Criti-Cal selective routing and full-coverage fusion','Subject':'Two distinct reported protocols; see evaluation-data.json for provenance.'})
fig.savefig(P/'evaluation-results.png',dpi=240)
print(P/'evaluation-results.pdf')
