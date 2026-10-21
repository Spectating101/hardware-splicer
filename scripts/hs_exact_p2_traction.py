"""Source-derived pressure traction on clipped planar P1/P2 tetra faces.

Exact polynomial integration over Shapely/GEOS polygon-clipped triangles;
no need to sample a discontinuous point-in-polygon indicator at arbitrary
quadrature positions. The FE material/constraint/contact model is unchanged.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection


def _ring_moments(coords):
    v=np.asarray(coords,dtype=float)
    x,y=v[:-1,0],v[:-1,1]
    nx,ny=v[1:,0],v[1:,1]
    cross=x*ny-nx*y
    return np.array([
        np.sum(cross)/2,
        np.sum((x+nx)*cross)/6,
        np.sum((y+ny)*cross)/6,
        np.sum((x*x+x*nx+nx*nx)*cross)/12,
        np.sum((2*x*y+x*ny+nx*y+2*nx*ny)*cross)/24,
        np.sum((y*y+y*ny+ny*ny)*cross)/12,
    ],dtype=float)


def polygon_moments(poly):
    """Return integrals [1,x,y,x²,xy,y²] (all in supplied length units)."""
    if poly.is_empty:return np.zeros(6)
    if isinstance(poly,Polygon):
        rings=[(poly.exterior,1),*((ring,-1) for ring in poly.interiors)]
        sums=np.zeros(6)
        for ring,polarity in rings:
            values=_ring_moments(ring.coords)
            sums+=polarity*(1 if values[0]>=0 else -1)*values
        if abs(sums[0]-poly.area)>max(1e-8,poly.area*1e-8):
            raise ValueError('GEOS clipped polygon area/moment inconsistent')
        return sums
    if isinstance(poly,(MultiPolygon,GeometryCollection)):
        return sum((polygon_moments(part) for part in poly.geoms),np.zeros(6))
    return np.zeros(6)


def _line_moment(c,m):return c[0]*m[0]+c[1]*m[1]+c[2]*m[2]


def _product_moment(c,d,m):
    return (c[0]*d[0]*m[0]+(c[0]*d[1]+c[1]*d[0])*m[1]
           +(c[0]*d[2]+c[2]*d[0])*m[2]+c[1]*d[1]*m[3]
           +(c[1]*d[2]+c[2]*d[1])*m[4]+c[2]*d[2]*m[5])


def exact_planar_traction(basis,board_polygon,*,zplane_m,force_z_newtons,degree):
    """Assemble degree-1/2 shape-force exactly on intersected planar facets.

    Basis lives in SI metres; clipping and monomial integrals use millimetres.
    Uniform vertical load is force_z_newtons shared over the real polygon
    intersection of the source PCB projection and the CAD lip bottom face.
    """
    if degree not in (1,2):raise ValueError('only P1/P2 displacement basis supported')
    if not board_polygon.is_valid or board_polygon.is_empty:
        raise ValueError('invalid source PCB original board polygon')
    mesh=basis.mesh
    xyz_mm=mesh.p.T*1000
    facets=mesh.facets.T
    exterior=mesh.boundary_facets()
    selected=exterior[np.max(np.abs(xyz_mm[facets[exterior],2]-zplane_m*1000),axis=1)<.05]
    if len(selected)<4:raise ValueError('source lip planar surface not resolved')
    loads=np.zeros(basis.N)
    area=0.;nfacets=0
    edge_lookup={tuple(sorted(edge)):i for i,edge in enumerate(mesh.edges.T)} if degree==2 else {}
    for i in selected:
        nodeids=facets[i]
        coords=xyz_mm[nodeids,:2]
        geom=Polygon(coords)
        if not geom.is_valid or geom.area<=1e-10:continue
        clipped=geom.intersection(board_polygon)
        if clipped.is_empty:continue
        m=polygon_moments(clipped)
        if m[0]<=1e-9:continue
        transfer=np.linalg.inv(np.column_stack((np.ones(3),coords)))
        linear=[_line_moment(transfer[:,k],m) for k in range(3)]
        if degree==1:
            for k in range(3):loads[basis.nodal_dofs[2,int(nodeids[k])]]+=linear[k]
        else:
            for k in range(3):
                integral=2*_product_moment(transfer[:,k],transfer[:,k],m)-linear[k]
                loads[basis.nodal_dofs[2,int(nodeids[k])]]+=integral
            for a,b in ((0,1),(1,2),(0,2)):
                index=edge_lookup[tuple(sorted((int(nodeids[a]),int(nodeids[b]))))]
                loads[basis.edge_dofs[2,index]]+=4*_product_moment(transfer[:,a],transfer[:,b],m)
        area+=m[0];nfacets+=1
    if not 18<=area<=350:raise ValueError('unsupported source retaining lip projected area')
    total=float(loads.sum())
    if abs(total-area)>max(1e-5,area*1e-7):
        raise ValueError('partition-of-unity failed during exact P1/P2 load integration')
    loads*=force_z_newtons/area
    if abs(loads.sum()-force_z_newtons)>1e-9:
        raise ValueError('exact applied source traction force does not sum to declared total')
    return loads,{'clipped_lip_area_mm2':area,'loaded_original_CAD_facets':nfacets,
                  'integration':'GEOS planar polygon clipping + exact quadratic face shape moments',
                  'source_polygon_integral_not_quadrature_sample':True}
