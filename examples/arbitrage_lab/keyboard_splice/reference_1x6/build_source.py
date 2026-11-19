"""Original reference: one-row, six-switch Cherry-MX keypad with controller header.

Native KiCad source for end-to-end *virtual* full-keyboard copper reconstruction.
No MCU/firmware, USB, donor board, or physical validation is represented.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pcbnew as p

KEYS = (25.0, 50.0, 75.0, 100.0, 125.0, 150.0)
BUSES = (50.0, 52.54, 55.08, 57.62, 60.16, 62.7)
TOP = 25.0
HEADER = 10.0


def pos(x, y):
    return p.VECTOR2I(p.FromMM(x), p.FromMM(y))


def place(board, library, name, ref, x, y):
    directory = Path("/usr/share/kicad/footprints")/(library+".pretty")
    footprint = p.FootprintLoad(str(directory), name)
    if footprint is None:
        raise ValueError("KiCad footprint missing: "+name)
    footprint.SetReference(ref)
    footprint.SetPosition(pos(x,y))
    board.Add(footprint)
    return footprint


def assign(footprint, mapping):
    pads={str(pad.GetNumber()):pad for pad in footprint.Pads()}
    for number, net in mapping.items():
        if str(number) not in pads:
            raise ValueError("Missing physical pad "+str(number))
        pads[str(number)].SetNet(net)


def track(board, net, ax, ay, bx, by, layer=p.F_Cu):
    item = p.PCB_TRACK(board)
    item.SetStart(pos(ax,ay))
    item.SetEnd(pos(bx,by))
    item.SetWidth(p.FromMM(.3))
    item.SetLayer(layer)
    item.SetNet(net)
    board.Add(item)


def via(board, net, x, y):
    item = p.PCB_VIA(board)
    item.SetPosition(pos(x,y))
    item.SetWidth(p.F_Cu,p.FromMM(1.0))
    item.SetWidth(p.B_Cu,p.FromMM(1.0))
    item.SetDrill(p.FromMM(.4))
    item.SetViaType(p.VIATYPE_THROUGH)
    item.SetNet(net)
    board.Add(item)


def build(path):
    board=p.BOARD()
    nets={}
    for name in ["ROW_0"] + [f"COL_{i}" for i in range(6)]:
        net = p.NETINFO_ITEM(board,name)
        board.Add(net)
        nets[name]=net
    for i,x in enumerate(KEYS):
        switch=place(board,"Button_Switch_Keyboard","SW_Cherry_MX_1.00u_PCB",
                     f"SW{i+1}",x,TOP)
        assign(switch,{"1":nets["ROW_0"],"2":nets[f"COL_{i}"]})
    header=place(board,"Connector_PinHeader_2.54mm",
                 "PinHeader_1x07_P2.54mm_Vertical","J1",HEADER,BUSES[0])
    assign(header,{**{str(i+1):nets[f"COL_{i}"] for i in range(6)},
                   "7":nets["ROW_0"]})
    for a,b in zip(KEYS,KEYS[1:]):
        track(board,nets["ROW_0"],a,TOP,b,TOP)
    track(board,nets["ROW_0"],HEADER,65.24,14,65.24)
    track(board,nets["ROW_0"],14,65.24,14,TOP)
    track(board,nets["ROW_0"],14,TOP,KEYS[0],TOP)
    for i,x in enumerate(KEYS):
        y=BUSES[i]
        col=nets[f"COL_{i}"]
        sx=x-6.35
        track(board,col,sx,TOP+2.54,sx,y,p.F_Cu)
        via(board,col,sx,y)
        track(board,col,sx,y,HEADER,y,p.B_Cu)
    corners=((0.0,0.0),(176.0,0.0),(176.0,87.0),(0.0,87.0))
    for a,b in zip(corners,corners[1:]+corners[:1]):
        edge=p.PCB_SHAPE(board)
        edge.SetShape(p.SHAPE_T_SEGMENT)
        edge.SetStart(pos(*a))
        edge.SetEnd(pos(*b))
        edge.SetLayer(p.Edge_Cuts)
        edge.SetWidth(p.FromMM(.05))
        board.Add(edge)
    path.parent.mkdir(parents=True,exist_ok=True)
    p.SaveBoard(str(path),board)
    print("SOURCE",path,"SWITCHES",6,"CONTROLLER_HEADER_PINS",7)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    build(args.output)
