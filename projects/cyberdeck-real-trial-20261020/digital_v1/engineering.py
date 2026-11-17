"""Reproducible first-order device calculations and dimensioned layout.

These are scenario calculations, not measured battery life, CFD or structural FEA.
"""
from pathlib import Path
import csv
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyBboxPatch

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'analysis'
OUT.mkdir(exist_ok=True)
S=json.loads((ROOT/'design.json').read_text())
G=json.loads((ROOT/'cad/geometry_report.json').read_text())
B=json.loads((ROOT/'bom.json').read_text())
A=S['engineering_assumptions']


def write_analysis():
    from study_contract import calculate, input_hashes, load_requirements
    result=calculate(S,G,B,load_requirements(ROOT))
    result['input_sha256']=input_hashes(ROOT)
    scenarios=result['load_scenarios']
    usable=result['usable_output_energy_wh']
    (OUT/'calculations.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['id','description','manufacturer','mpn','specification','quantity','unit','acquisition','price_usd','price_basis','availability','url','open_issue']
    with (ROOT/'BOM.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(B['items'])
    fig,axes=plt.subplots(1,2,figsize=(12,4.9),layout='constrained')
    names=['Light','Work','Stress','High USB2\nkeyboard']
    low=[x['runtime_h'][0] for x in scenarios];high=[x['runtime_h'][1] for x in scenarios]
    axes[0].barh(names,high,color='#b9d8d0');axes[0].barh(names,low,color='#258272')
    axes[0].set(xlabel='Estimated runtime (hours)',title=f"{result['battery_nominal_cell_energy_wh']:g} Wh nominal bank: efficiency / capacity range",xlim=(0,max(high)*1.3))
    for i,(l,h) in enumerate(zip(low,high)):axes[0].text(h+.06,i,f'{l:.2f}–{h:.2f}',va='center',fontsize=9)
    pi=np.linspace(.4,2.7,150);usb=np.linspace(0,1.2,120);x,y=np.meshgrid(pi,usb)
    limit=result['bank_single_port_limit_a']
    display_a=A['display_w']['allocated']/result['supply_voltage_v']
    total=x+y+display_a
    axes[1].contourf(x,y,total,levels=[0,.85*limit,limit,max(float(total.max())+.1,limit+.1)],colors=['#c8e3da','#fae1ad','#efb7ae'])
    axes[1].contour(x,y,total,levels=[limit],colors='#a33e2f',linewidths=2)
    axes[1].scatter([r['pi_current_a'] for r in scenarios[1:]],[r['usb_current_a'] for r in scenarios[1:]],c=['#155c50','#155c50','#954225'],s=38)
    axes[1].set(xlabel='Pi board current (A), excluding display / USB',ylabel='Total USB load (A), including fan + keyboard',title=f"{result['supply_voltage_v']:g} V envelope with {display_a:g} A display allocation")
    axes[1].text(.5,1.05,f'Green: ≥15% current margin\nAmber: <15% margin\nRed: exceeds bank {limit:g} A',fontsize=9)
    fig.suptitle('FIELDDECK 7 • scenario calculations, not measured performance',fontsize=13)
    fig.savefig(OUT/'power_runtime.png',dpi=170);plt.close(fig)
    return result


def draw_layout():
    fig,(top,side)=plt.subplots(1,2,figsize=(14,8),gridspec_kw={'width_ratios':[1.55,1]},layout='constrained')
    top.add_patch(Rectangle((0,0),310,285,fill=False,lw=2))
    for x in (3,307):top.plot([x,x],[3,282],c='#aeb9c1',lw=.6)
    for name,rect,color in [('Keyboard 285 × 123',(12.5,16.5,285,123),'#d2d8df'),('Touch Display 2',(60.34,149.88,189.32,120.24),'#c2e0da'),('Bank (under keys)',(16,25,52.3,104),'#f6d3a9'),('Pi 4 (under fan)',(4,198,56,85),'#b1d1b2')]:
        x,y,w,h=rect;top.add_patch(Rectangle((x,y),w,h,facecolor=color,edgecolor='#526578',alpha=.7));top.text(x+w/2,y+h/2,name,ha='center',va='center',fontsize=9,rotation=90 if 'Bank' in name or 'Pi 4' in name else 0)
    for p in G['display_case_mount_centres_mm']:top.add_patch(Circle(p,5,fill=False,ec='#20725c',lw=1.3))
    for p in G['pi_mount_centres_mm']:top.add_patch(Circle(p,1.4,fill=False,ec='black'))
    for p in G['top_fastener_centres_mm']:top.add_patch(Circle(p,1.6,color='#b35c23'))
    top.plot([155,155],[0,285],'--',c='#777',lw=.8);top.plot([0,310],[140,140],'--',c='#777',lw=.8)
    top.add_patch(Rectangle((10,208.5),44,44,fill=False,ec='#986b3d',lw=2))
    top.annotate('Rear opening: x 3–76, z 5–30',xy=(39,285),xytext=(155,313),ha='center',arrowprops={'arrowstyle':'->'},fontsize=9)
    top.annotate('310',xy=(0,-12),xytext=(310,-12),ha='center',va='center',arrowprops={'arrowstyle':'<->'})
    top.annotate('285',xy=(-12,0),xytext=(-12,285),ha='center',va='center',arrowprops={'arrowstyle':'<->'})
    top.set(aspect='equal',xlim=(-30,330),ylim=(-25,325),xlabel='X / mm',ylabel='Y / mm',title='Top plan • front at y = 0 • hidden modules shown')
    side.add_patch(Rectangle((0,0),285,64,fill=False,lw=2))
    for rect,color in [((16.5,40,123,22),'#d2d8df'),((149.88,47.02,120.24,15),'#c2e0da'),((25,4,104,26),'#f6d3a9'),((198,7,85,1.6),'#63976a')]:
        side.add_patch(Rectangle(rect[:2],rect[2],rect[3],facecolor=color,edgecolor='#526578'))
    side.plot([0,285],[3,3],color='#526578');side.plot([0,285],[61,61],color='#b3632b',ls='--')
    side.text(80,52,'Keyboard',ha='center');side.text(79,17,'Bank',ha='center');side.text(210,53,'Display',ha='center')
    side.set(aspect='equal',xlim=(-8,300),ylim=(-15,85),xlabel='Y / mm',ylabel='Z / mm',title='Side envelope • projected modules, not a cut section')
    fig.suptitle('FIELDDECK 7 • nominal assembly dimensions • no scale guarantee on printed page')
    fig.savefig(ROOT/'views/dimensioned_layout.png',dpi=170)
    svg=ROOT/'views/dimensioned_layout.svg'
    fig.savefig(svg);plt.close(fig)
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')


if __name__=='__main__':
    r=write_analysis();draw_layout();print(json.dumps({'cost':r['cost_usd'],'runtime':r['load_scenarios'],'solid_mass_g':r['custom_100_percent_solid_petg_mass_g']}))
