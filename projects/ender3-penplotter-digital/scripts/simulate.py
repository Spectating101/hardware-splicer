"""GPL-3.0-only. SVG polylines -> Marlin-style G-code -> local trajectory replay.

No serial port, network, device or motion API is used.
"""
import csv
import json
import math
import re
import xml.etree.ElementTree as ET
import numpy as np
from common import ROOT, read_requirements, write_json, constraint


def make_svg(path):
    paths=[[(8,12),(42,12),(42,45),(8,45),(8,12)],[(4,45),(25,65),(46,45)],
           [(20,12),(20,30),(30,30),(30,12)],[(12,34),(19,34),(19,41),(12,41),(12,34)],
           [(32,34),(39,34),(39,41),(32,41),(32,34)],[(55,12),(92,12)],
           [(60,12),(60,29),(70,29),(70,12)],[(76,12),(76,40),(86,40),(86,12)]]
    paths.append([(76+9*math.cos(t),59+9*math.sin(t)) for t in np.linspace(0,2*math.pi,65)])
    for phase in [0,4,8]:
        paths.append([(x,4+phase+1.5*math.sin(x*.17)) for x in np.linspace(5,95,61)])
    drawing = ROOT / 'sources' / 'prompt-drawing.json'
    if drawing.is_file():
        paths = json.loads(drawing.read_text())
    lines=['<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="80mm" viewBox="0 0 100 80">',
           '<g fill="none" stroke="#12638a" stroke-width="0.35">']
    for pts in paths:
        lines.append('<polyline points="'+' '.join(f'{x:.4f},{80-y:.4f}' for x,y in pts)+'"/>')
    path.write_text('\n'.join(lines+['</g>','</svg>'])+'\n')


def source_to_bed(x,y,req):
    # Uniform fit keeps squares, circles and the authored aspect ratio unchanged.
    scale=min(req['drawing_width_mm']/100,req['drawing_height_mm']/80)
    return (117.5+(x-50)*scale,117.5+(y-40)*scale)


def parse_svg(path,req):
    paths=[]
    for node in ET.parse(path).getroot().iter():
        if node.tag.split('}')[-1]=='polyline':
            vals=[float(x) for x in re.split(r'[\s,]+',node.attrib['points'].strip())]
            if len(vals)<4 or len(vals)%2:raise ValueError('Malformed SVG polyline')
            if not all(math.isfinite(v) for v in vals) or any(not 0<=x<=100 or not 0<=y<=80 for x,y in zip(vals[::2],vals[1::2])):
                raise ValueError('Source artwork lies outside the declared 100 x 80 logical viewport')
            paths.append([source_to_bed(vals[i],80-vals[i+1],req)
                          for i in range(0,len(vals),2)])
    return paths


def replay(gcode,lift):
    xyz=np.array([117.5,117.5,lift]);feed=1200.;records=[];absolute=False;metric=False
    for number,line in enumerate(gcode.splitlines(),1):
        line=line.split(';')[0].strip()
        if not line:continue
        token=line.split()[0]
        if token=='G21':metric=True
        elif token=='G90':absolute=True
        elif token in ('G0','G1'):
            if not absolute or not metric:raise ValueError('Move lacks absolute metric mode')
            words=dict((k,float(v)) for k,v in re.findall(r'([XYZF])(-?\d+(?:\.\d+)?)',line))
            target=xyz.copy()
            for idx,k in enumerate('XYZ'):
                if k in words:target[idx]=words[k]
            feed=words.get('F',feed)
            distance=float(np.linalg.norm(target-xyz));duration=distance/(feed/60)
            draw=abs(xyz[2])<1e-8 and abs(target[2])<1e-8 and np.linalg.norm(target[:2]-xyz[:2])>1e-8
            records.append(dict(line=number,x0=float(xyz[0]),y0=float(xyz[1]),z0=float(xyz[2]),
                x1=float(target[0]),y1=float(target[1]),z1=float(target[2]),
                feed_mm_min=feed,duration_s=duration,drawing=int(draw)))
            xyz=target
        elif token in ('M104','M140'):
            if not re.search(r'\bS0(?:\s|$)',line):raise ValueError('Nonzero heater setpoint')
        elif token not in ('M107','M400'):raise ValueError('Unsupported command '+token)
    return records


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    req=read_requirements();folder=ROOT/'simulation';folder.mkdir(exist_ok=True)
    svg=folder/'example.svg';make_svg(svg);paths=parse_svg(svg,req)
    offset=json.loads((ROOT/'sources/interface.json').read_text())['pen_offset_from_nozzle_xy_mm']
    lines=['; DIGITAL SIMULATION EXAMPLE ONLY - not a physical machine job',
        '; Requires calibrated pen-paper Z=0 and XY tool offset. Homing and setup are excluded.',
        f'; Tool XY offset from original nozzle: {offset[0]:.4f}, {offset[1]:.4f} mm',
        'G21','G90','M104 S0','M140 S0','M107',f'G0 Z{req["pen_lift_mm"]:.4f} F300']
    for path in paths:
        x,y=path[0];lines.append(f'G0 X{x-offset[0]:.4f} Y{y-offset[1]:.4f} F1200')
        lines.append('G1 Z0.0000 F180')
        for x,y in path[1:]:lines.append(f'G1 X{x-offset[0]:.4f} Y{y-offset[1]:.4f} F600')
        lines.append(f'G0 Z{req["pen_lift_mm"]:.4f} F300')
    lines+=['M400','; End local digital example. No physical machine acceptance is implied.']
    code='\n'.join(lines)+'\n';(folder/'example.gcode').write_text(code)
    records=replay(code,req['pen_lift_mm'])
    with (folder/'trajectory.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    # Reconstruct ink FROM GCODE. Original SVG coordinates are not reused for the render.
    fig,ax=plt.subplots(figsize=(9,8));ax.add_patch(plt.Rectangle((0,0),235,235,facecolor='#dbe3e9',edgecolor='#5a6b75'))
    pw,ph=req['paper_width_mm'],req['paper_height_mm']
    px0,py0=(235-pw)/2,(235-ph)/2
    ax.add_patch(plt.Rectangle((px0,py0),pw,ph,facecolor='#fffef6',edgecolor='#c4ba9e',linestyle='--'))
    ax.text(117.5,py0+2,f'{pw:g} × {ph:g} mm paper',ha='center',va='bottom',fontsize=8,color='#786d50')
    draw_length=0.;travel_length=0.;total_time=0.;xyz=[];bad_travel=0
    for row in records:
        xy=np.array([[row['x0'],row['y0']],[row['x1'],row['y1']]])+np.array(offset)
        xyz.extend([[*xy[0],row['z0']],[*xy[1],row['z1']]])
        total_time+=row['duration_s'];length=float(np.linalg.norm(xy[1]-xy[0]))
        if row['drawing']:
            draw_length+=length;ax.plot(xy[:,0],xy[:,1],color='#12638a',lw=1.25)
        elif length>0:
            travel_length+=length;ax.plot(xy[:,0],xy[:,1],color='#aab5b8',lw=.5,linestyle=':')
            if min(row['z0'],row['z1'])<req['pen_lift_mm']-1e-6:bad_travel+=1
    pts=np.array(xyz);minbed=float(min(pts[:,:2].min(),235-pts[:,:2].max()))
    # Fixtures may overhang a bed edge. Their measured lower face stays30mm above pen tip.
    # Check clearance above the stated <=1mm tape obstruction, not a fictitious XY exclusion.
    eng=json.loads((ROOT/'reports/engineering.json').read_text())
    fixture_margin=eng['metrics']['pen_tip_to_clamp_mm']-1.
    ctrl=np.array([[r['x1'],r['y1']] for r in records]);ctrlmargin=float(min(ctrl.min(),235-ctrl.max()))
    ink_xy=np.array([[r['x'+n]+offset[0],r['y'+n]+offset[1]] for r in records if r['drawing'] for n in ('0','1')])
    if not len(ink_xy):raise ValueError('The requested artwork contains no ink segments')
    ink_paper_margin=float(min((ink_xy-[px0,py0]).min(),(np.array([px0+pw,py0+ph])-ink_xy).min()))
    half=np.array([req['drawing_width_mm'],req['drawing_height_mm']])/2
    ink_viewport_margin=float(min((ink_xy-(117.5-half)).min(),((117.5+half)-ink_xy).min()))
    constraints=[constraint('pen_tip_on_bed',minbed,0,minbed>=0,'mm','Affine segment endpoints bound all linear XY positions'),
        constraint('fixture_vertical_clearance',fixture_margin,2,fixture_margin>=2,'mm','Measured fixture lower face30mm above tip minus assumed1mm tape; excludes frame/wires'),
        constraint('controller_travel',ctrlmargin,0,ctrlmargin>=0,'mm','Manufacturer Configuration.h 0..235mm XY, compensated tip offset'),
        constraint('pen_up_travel',bad_travel,0,bad_travel==0,'segments','Every XY travel move must stay at requested lift'),
        constraint('pen_lift_clearance',req['pen_lift_mm']-1.,1.,req['pen_lift_mm']>=2,'mm','Assumed tape height <=1mm; uncertainty is not physical validation'),
        constraint('ink_paper_margin',ink_paper_margin,10,ink_paper_margin>=10-.00011,'mm','Every emitted ink endpoint leaves 10 mm paper margin; 0.00011 mm serialization tolerance'),
        constraint('ink_in_viewport',ink_viewport_margin,0,ink_viewport_margin>=-.00011,'mm','Every emitted ink segment stays inside the requested source viewport; 0.00011 mm serialization tolerance'),
        constraint('Z_travel',float(pts[:,2].max()),req['pen_lift_mm'],pts[:,2].min()>=0 and pts[:,2].max()<=req['pen_lift_mm']+1e-6,'mm','Every commanded segment endpoint lies within paper Z0 and requested lift')]
    canvas_scale=min(req['drawing_width_mm']/100,req['drawing_height_mm']/80)
    report=dict(case_id='ender3-penplotter',requirements=req,requirements_met=all(c['passed'] for c in constraints),
        physical_validation_performed=False,constraints=constraints,
        metrics={'source_canvas_scale_mm_per_unit':canvas_scale,
                  'source_canvas_width_mm':100*canvas_scale,'source_canvas_height_mm':80*canvas_scale,
                  'draw_length_mm':draw_length,'travel_length_mm':travel_length,'ideal_feed_time_s':total_time,
                 'segment_count':len(records),'stroke_count':len(paths),'pen_center_bed_margin_mm':minbed,
                  'ink_paper_margin_mm':ink_paper_margin,'ink_viewport_margin_mm':ink_viewport_margin,
                 'fixture_bed_clearance_mm':fixture_margin,'controller_travel_margin_mm':ctrlmargin,
                 'pen_lift_mm':req['pen_lift_mm'],'non_drawing_XY_without_lift':bad_travel,
                 'minimum_commanded_Z_mm':float(pts[:,2].min()),'maximum_commanded_Z_mm':float(pts[:,2].max())},
        limitations=['Initial position and pen-paper datum are assumed; homing is excluded.',
                     'Ideal feed time excludes acceleration, controller buffering, backlash and settling.',
                     'Bed and fixture corridor checks exclude wiring, rollers, machine frame and human handling.'])
    write_json(ROOT/'reports/simulation.json',report)
    eng=json.loads((ROOT/'reports/engineering.json').read_text())
    eng['constraints']=[c for c in eng['constraints'] if not c['id'].startswith('motion_')]
    eng['constraints'] += [{**c,'id':'motion_'+c['id']} for c in constraints]
    eng['metrics'].update(report['metrics']);eng['requirements_met']=all(c['passed'] for c in eng['constraints'])
    write_json(ROOT/'reports/engineering.json',eng)
    ax.set(xlim=(-5,240),ylim=(-5,240),aspect='equal',xlabel='Pen tip X on bed (mm)',ylabel='Pen tip Y on bed (mm)',
           title='Digital G-code replay: blue drawing, dotted pen-up travel')
    fig.text(.5,.015,'VIRTUAL reference donor · no physical validation · heaters commanded off',ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(folder/'plotted_drawing.png',dpi=170);plt.close(fig)
    print('SVG -> G-code -> replay:',len(records),'segments; requirements_met=',report['requirements_met'])


if __name__=='__main__':main()
