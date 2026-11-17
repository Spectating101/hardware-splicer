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
    identifiers=[r['id'] for r in B['items']]
    identities=[(r['manufacturer'],r['mpn']) for r in B['items'] if r.get('manufacturer') and r.get('mpn')]
    assert len(identifiers)==len(set(identifiers)), 'Duplicate BOM line identifier'
    assert len(identities)==len(set(identities)), 'Duplicate selected commercial module in BOM'
    usable=[10*A['power_bank_cell_voltage_v']*.85*.75,10*A['power_bank_cell_voltage_v']*1*.9]
    scenarios=[]
    for name,pi,display,keys in [('light',.65,2.4,.1),('work',1,2.4,.1),('stress_allocation',1.75,3,.1),('high_power_keyboard_sensitivity',1.75,3,.5)]:
        current=pi+display/5+keys+A['fan_current_a']
        scenarios.append(dict(name=name,pi_current_a=pi,display_w=display,keyboard_a=keys,current_a=round(current,3),power_w=round(5*current,3),
                              current_headroom_a=round(3-current,3),runtime_h=[round(e/(5*current),2) for e in usable]))
    volume=sum(p['volume_mm3'] for p in G['parts'] if p['printable'])
    # Conservative homogeneous solid CAD mass. Sparse infill is not a simple
    # multiplier for thin walls/perimeters; no invented slicer mass is given.
    solid_mass=volume/1000*S['print']['density_g_cm3']
    # Longest display-post bending model: four posts share a 0.35 kg panel
    # lateral inertial load, with an intentionally weak printed PETG modulus.
    od,id_=10,6
    inertia=math.pi/64*(od**4-id_**4)
    lateral_force=.35*9.80665*2/4
    length=49.54
    stress=lateral_force*length*(od/2)/inertia
    deflection=lateral_force*length**3/(3*1500*inertia)
    # Air temperature rise is an energy balance only. The fan's real operating
    # point, leakage, PCB junction-to-air path and PETG temperature are unknown.
    fractions=np.array([.05,.10,.20,.40])
    heat_w=12.6
    air_rise=heat_w/(1.2*1005*(8.9/3600)*fractions)
    retail=sum(p['price_usd'] for p in B['items'] if p['price_basis']=='observed retail')
    allowance=sum(p['price_usd'] for p in B['items'] if p['price_basis']!='observed retail')
    # USB2 22 AWG power conductors: 53.5 mOhm/m at 20C, 0.5m each way.
    # Contact resistance is swept rather than silently assumed zero.
    resistances=[.0535+r for r in (0,.05,.1)]
    result={
      'calculation_type':'first_order_scenarios_not_physical_simulation',
      'battery_nominal_cell_energy_wh':36,'usable_output_energy_wh':usable,
      'battery_basis':'10Ah x assumed 3.6V cell nominal; 75-90% conversion, 85-100% usable capacity. Not 10Ah at 5V.',
      'load_scenarios':scenarios,'bank_single_port_limit_a':3,'pi_usb_aggregate_limit_a':1.2,
      'power_cable_loop_resistance_ohm':resistances,
      'stress_cable_drop_v':[round(2.52*r,3) for r in resistances],
      'stress_pi_voltage_if_bank_exactly_5v':[round(5-2.52*r,3) for r in resistances],
      'voltage_caveat':'At the upper contact resistance, Pi input can approach/breach its undervoltage threshold. A 3A wattage margin does not establish voltage stability.',
      'custom_solid_volume_cm3':round(volume/1000,2),'custom_100_percent_solid_petg_mass_g':round(solid_mass,1),
      'mass_note':'Actual sliced mass not computed; 30% infill does not imply 30% of this mass. Display mass budget 250-350g; other module/hardware mass assumptions recorded in README.',
      'post_lateral_2g_check':{'panel_mass_assumption_kg':.35,'load_per_post_n':lateral_force,'length_mm':length,'section_second_moment_mm4':inertia,'elastic_modulus_assumption_mpa':1500,'allowable_stress_assumption_mpa':10,'bending_stress_mpa':stress,'tip_deflection_mm':deflection,'scope':'Ideal cantilever with equal load sharing; excludes base/root, layers, screws, seams, glass and impact. Not a drop rating.'},
      'cooling_sensitivity':{'heat_assumption_w':heat_w,'fan_free_air_m3_h':8.9,'delivered_fraction':fractions.tolist(),'bulk_air_rise_c':air_rise.tolist(),'scope':'Energy balance, not CFD, CPU junction temperature or a fan/system operating point.'},
      'cost_usd':{'observed_retail_subtotal':round(retail,2),'explicit_allowance_subtotal':round(allowance,2),'planning_total':round(retail+allowance,2),'scope':B['pricing_scope']},
      'open_digital_fit_items':['bank ports/button and built-in cable not dimensioned','keyboard underside/pad retention and cable bend not manufacturer CAD','display lug thread/engagement nominal only','GPIO extension connector rating and retention unverified','flexible cable bends/routing not solid interference verified'],
      'physical_validation_performed':False}
    (OUT/'calculations.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['id','description','manufacturer','mpn','specification','quantity','unit','acquisition','price_usd','price_basis','availability','url','open_issue']
    with (ROOT/'BOM.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(B['items'])
    fig,axes=plt.subplots(1,2,figsize=(12,4.9),layout='constrained')
    names=['Light','Work','Stress','High USB2\nkeyboard']
    low=[x['runtime_h'][0] for x in scenarios];high=[x['runtime_h'][1] for x in scenarios]
    axes[0].barh(names,high,color='#b9d8d0');axes[0].barh(names,low,color='#258272')
    axes[0].set(xlabel='Estimated runtime (hours)',title='36 Wh nominal bank: efficiency / capacity range',xlim=(0,6))
    for i,(l,h) in enumerate(zip(low,high)):axes[0].text(h+.06,i,f'{l:.2f}–{h:.2f}',va='center',fontsize=9)
    pi=np.linspace(.4,2.7,150);usb=np.linspace(0,1.2,120);x,y=np.meshgrid(pi,usb)
    total=x+y+.6
    axes[1].contourf(x,y,total,levels=[0,2.55,3,5],colors=['#c8e3da','#fae1ad','#efb7ae'])
    axes[1].contour(x,y,total,levels=[3],colors='#a33e2f',linewidths=2)
    axes[1].scatter([1,1.75,1.75],[.17,.17,.57],c=['#155c50','#155c50','#954225'],s=38)
    axes[1].set(xlabel='Pi board current (A), excluding display / USB',ylabel='Total USB load (A), including fan + keyboard',title='5 V power envelope with 0.6 A display allocation')
    axes[1].text(.5,1.05,'Green: ≥15% current margin\nAmber: <15% margin\nRed: exceeds bank 3 A',fontsize=9)
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
