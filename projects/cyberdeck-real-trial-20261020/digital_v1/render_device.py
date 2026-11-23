"""Orthographic views of the exported device GLB, with labelled cosmetic overlays.

No generative imagery: triangles come from the delivered CAD assembly. The key
legends and terminal display illustrate use; they are not a booted system.
"""
from pathlib import Path
import json
import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'views'
OUT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def render(filename,exploded=False,inside=False):
    scene=trimesh.load(ROOT/'cad/FIELDDECK_7.glb',force='scene')
    view=np.array([.85,-1.2,1.25]);view/=np.linalg.norm(view)
    right=np.cross([0,0,1],view);right/=np.linalg.norm(right)
    up=np.cross(view,right)
    centre=np.array([155,142.5,58 if exploded else 26])
    scale=2.55 if exploded else 3.15
    canvas=Image.new('RGB',(1500,1260),(238,241,244));d=ImageDraw.Draw(canvas)
    light=np.array([-.3,-.4,1]);light/=np.linalg.norm(light)
    def xy(p):
        q=np.array(p)-centre
        return np.column_stack((750+scale*(q@right),650-scale*(q@up)))
    pixels=np.array(canvas)
    zbuffer=np.full((1260,1500),-np.inf)
    def triangle(points,depth,color):
        lo=np.maximum(np.floor(points.min(axis=0)).astype(int),[0,0])
        hi=np.minimum(np.ceil(points.max(axis=0)).astype(int),[1499,1259])
        if np.any(lo>hi):return
        x,y=np.meshgrid(np.arange(lo[0],hi[0]+1)+.5,np.arange(lo[1],hi[1]+1)+.5)
        a,b,c=points
        denominator=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(denominator)<1e-8:return
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/denominator
        v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/denominator
        w=1-u-v
        z=u*depth[0]+v*depth[1]+w*depth[2]
        target=zbuffer[lo[1]:hi[1]+1,lo[0]:hi[0]+1]
        mask=(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8)&(z>target)
        target[mask]=z[mask]
        pixels[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=color
    for node in scene.graph.nodes_geometry:
        transform,name=scene.graph[node]
        m=scene.geometry[name].copy();m.apply_transform(transform)
        offset=np.zeros(3)
        if inside and (node.startswith('face_') or node.startswith('keyboard_') or node in ('touch_display_2_manufacturer','fan_guard','fan_envelope','fan_duct')):
            continue
        if exploded:
            if node.startswith('face_') or node in ('fan_guard','fan_envelope','fan_duct'):offset[2]=110
            elif node.startswith('keyboard_') or node=='touch_display_2_manufacturer':offset[2]=65
            elif node=='power_bank_nominal_envelope':offset[2]=24
        vertices=m.vertices+offset
        colors=m.visual.face_colors[:,:3]
        shades=.55+.45*np.maximum(0,m.face_normals@light)
        colors=(colors*shades[:,None]).astype(np.uint8)
        projected=xy(vertices)
        depth=(vertices-centre)@view
        for i,face in enumerate(m.faces):
            triangle(projected[face],depth[face],colors[i])
    canvas=Image.fromarray(pixels);d=ImageDraw.Draw(canvas)
    # Cosmetic surfaces are drawn only in assembled view; CAD retains plain
    # purchased-part envelopes rather than invented manufacturer detail.
    if not inside and not exploded:
        def patch(x,y,w,h,z,color):
            d.polygon([tuple(p) for p in xy([[x,y,z],[x+w,y,z],[x+w,y+h,z],[x,y+h,z]])],fill=color)
        patch(77.7,166.55,154.6,86.9,62.03,(15,31,41))
        for i,width in enumerate((119,90,109,62,100)):
            patch(87,232-i*11,width,1.3,62.05,(87,192,170) if i!=1 else (216,227,237))
        # Representative grid, not a replacement model for the exact keyboard.
        for row in range(6):
            for col in range(17):
                if row==0 and 5<=col<=10:continue
                patch(18+col*16.1,22+row*18,14.2,15.5,62.03,(66,73,82))
        patch(99,22,92,15.5,62.04,(66,73,82))
    title='FIELDDECK 7'
    sub='EXPLODED ASSEMBLY' if exploded else 'INTERNAL LAYOUT' if inside else 'LINUX FIELD TERMINAL'
    d.text((72,56),title,font=ImageFont.truetype(BOLD,44),fill=(28,40,54))
    d.text((74,115),sub,font=ImageFont.truetype(FONT,23),fill=(83,98,113))
    d.text((74,1175),'310 × 285 × 64 mm case  |  digital prototype  |  millimetres',font=ImageFont.truetype(FONT,21),fill=(50,65,82))
    d.text((74,1210),'Vendor display STEP + nominal purchased-module envelopes; screen and key detail are illustrative.',font=ImageFont.truetype(FONT,17),fill=(83,98,113))
    if inside:
        labels=[([42,77,30],'Removable 10,000 mAh bank',(78,830)),([32,231,25],'Pi 4 + rear USB / Ethernet',(78,210)),([225,175,52.5],'Display support posts',(1030,330)),([210,20,38],'Keyboard support / pads',(1030,940))]
    elif exploded:
        labels=[([270,230,174],'Faces; fan / duct preassembled',(1060,200)),([155,210,127],'7-inch Touch Display 2',(1000,450)),([155,78,127],'Wired USB keyboard',(70,680)),([155,130,3],'Four tray pieces + seam plates',(930,990))]
    else:
        labels=[([180,211,64],'7-inch landscape touch',(1030,290)),([220,70,64],'Wired keyboard',(1050,950)),([32,230.5,66],'USB-powered fan',(78,260))]
    for pt,label,pos in labels:
        anchor=tuple(xy([pt])[0]);end=(pos[0]+5,pos[1]+32)
        d.line((anchor,end),fill=(63,106,131),width=2);d.ellipse((anchor[0]-4,anchor[1]-4,anchor[0]+4,anchor[1]+4),fill=(40,123,151))
        font=ImageFont.truetype(FONT,18)
        bounds=d.textbbox(pos,label,font=font)
        d.rectangle((bounds[0]-5,bounds[1]-4,bounds[2]+5,bounds[3]+4),fill=(238,241,244))
        d.text(pos,label,font=font,fill=(32,65,86))
    canvas.save(OUT/filename)


if __name__=='__main__':
    render('assembled.png');render('exploded.png',exploded=True);render('internal.png',inside=True)
    print('Rendered assembled, exploded and internal views from FIELDDECK_7.glb')
