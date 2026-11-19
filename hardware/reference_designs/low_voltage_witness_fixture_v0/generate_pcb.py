#!/usr/bin/env /usr/bin/python3
"""Generate KiCad 9 PCB for a bounded 5V/0.5A current witness interposer.

All footprints and net assignments come from the matching KiCad schematic export.
Manual routing is disclosed; native DRC and schematic/PCB parity must independently
pass before any proposed fabrication. No device operation is authorized here.
"""
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import pcbnew as p

ROOT=Path(__file__).resolve().parent
NAME="low_voltage_witness_fixture_v0"
FOOTPRINTS=Path("/usr/share/kicad/footprints")
MM=p.FromMM
P={
 "J1":("TerminalBlock_Phoenix","TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal","SOURCE",(110,90),0),
 "F1":("Fuse","Fuseholder_Cylinder-5x20mm_Schurter_FAB_0031-355x_Horizontal_Closed","1A_FUSE",(130,90),0),
 "J3":("TerminalBlock_Phoenix","TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal","ADA_SHUNT",(169,90),0),
 "R1":("Resistor_SMD","R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm","0.010R_4T",(180,101),0),
 "J2":("TerminalBlock_Phoenix","TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal","LOAD",(202,90),0),
 "J4":("Connector_PinHeader_2.54mm","PinHeader_1x02_P2.54mm_Vertical","ADA_VBUS",(195,110),0),
 "J5":("Connector_PinHeader_2.54mm","PinHeader_1x02_P2.54mm_Vertical","REF_SHUNT",(162,112),0),
 "J6":("Connector_PinHeader_2.54mm","PinHeader_1x02_P2.54mm_Vertical","REF_VBUS",(195,122),0),
 "TP1":("TestPoint","TestPoint_THTPad_D2.0mm_Drill1.0mm","KELVIN_P",(162,105),0),
 "TP2":("TestPoint","TestPoint_THTPad_D2.0mm_Drill1.0mm","KELVIN_N",(176,116),0),
 "TP3":("TestPoint","TestPoint_THTPad_D2.0mm_Drill1.0mm","LOAD_P",(211,109),0),
 "TP4":("TestPoint","TestPoint_THTPad_D2.0mm_Drill1.0mm","RETURN",(214,124),0),
 "H1":("MountingHole","MountingHole_3.2mm_M3","M3",(104,80),0),
 "H2":("MountingHole","MountingHole_3.2mm_M3","M3",(220,80),0),
 "H3":("MountingHole","MountingHole_3.2mm_M3","M3",(104,130),0),
 "H4":("MountingHole","MountingHole_3.2mm_M3","M3",(220,130),0),
}
def xy(x,y):return p.VECTOR2I(MM(x),MM(y))
def fp(board,ref,spec):
 library,name,value,(x,y),angle=spec
 obj=p.FootprintLoad(str(FOOTPRINTS/(library+".pretty")),name)
 if not obj:raise RuntimeError(f"no footprint {ref} {library}:{name}")
 obj.SetReference(ref)
 obj.SetFPIDAsString(library+":"+name)
 obj.SetValue(value)
 obj.SetPosition(xy(x,y))
 obj.SetOrientationDegrees(angle)
 board.Add(obj)
 obj.Reference().SetVisible(False)
 if ref.startswith("H"):
  obj.SetAttributes(obj.GetAttributes()|p.FP_BOARD_ONLY|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
  obj.Reference().SetVisible(False)
 return obj
def pad(board,ref,number):
 obj=board.FindFootprintByReference(ref)
 result=obj.FindPadByNumber(str(number)) if obj else None
 if not result:raise ValueError(f"pad missing {ref}.{number}")
 return result
def pos(board,ref,number):
 o=pad(board,ref,number).GetPosition()
 return (o.x/1e6,o.y/1e6)
def track(board,net,points,layer,width):
 n=board.FindNet("/"+net)
 if n is None:raise ValueError("missing "+net)
 for a,b in zip(points,points[1:]):
  if a==b:continue
  t=p.PCB_TRACK(board)
  t.SetStart(xy(*a));t.SetEnd(xy(*b))
  t.SetWidth(MM(width));t.SetLayer(layer);t.SetNet(n)
  board.Add(t)
def via(board,net,point,diam=0.85,drill=0.4):
 n=board.FindNet("/"+net)
 v=p.PCB_VIA(board)
 v.SetPosition(xy(*point));v.SetWidth(p.F_Cu,MM(diam));v.SetDrill(MM(drill))
 v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(n)
 board.Add(v)
def add_text(board,value,x,y,size=0.9,angle=0):
 obj=p.PCB_TEXT(board)
 obj.SetText(value);obj.SetPosition(xy(x,y));obj.SetLayer(p.F_SilkS)
 obj.SetTextHeight(MM(size));obj.SetTextWidth(MM(size))
 obj.SetTextThickness(MM(0.13));obj.SetTextAngle(p.EDA_ANGLE(angle,p.DEGREES_T))
 board.Add(obj)
def build():
 board=p.BOARD();board.SetCopperLayerCount(2)
 setup=board.GetDesignSettings()
 setup.m_MinClearance=MM(0.2)
 setup.m_TrackMinWidth=MM(0.2)
 setup.m_ViasMinSize=MM(0.7)
 setup.m_MinThroughDrill=MM(0.3)
 netclass=setup.m_NetSettings.GetDefaultNetclass()
 netclass.SetTrackWidth(MM(0.25));netclass.SetClearance(MM(0.2))
 for ref,spec in P.items():fp(board,ref,spec)
 xml=ROOT/"netlist.xml"
 if not xml.exists():
  subprocess.run(["kicad-cli","sch","export","netlist",str(ROOT/(NAME+".kicad_sch")),
                  "--format","kicadxml","-o",str(xml)],check=True,stdout=subprocess.DEVNULL)
 root=ET.parse(xml).getroot()
 for item in root.findall("./components/comp"):
  ref=item.get("ref"); f=board.FindFootprintByReference(ref)
  if f is None:raise RuntimeError("schematic component without footprint: "+ref)
  f.SetValue(item.findtext("value"))
  f.SetPath(p.KIID_PATH(item.findtext("tstamps",default="")))
 for item in root.findall("./nets/net"):
  n=p.NETINFO_ITEM(board,item.get("name"));board.Add(n)
  for node in item.findall("node"):pad(board,node.get("ref"),node.get("pin")).SetNet(n)
 for (a,b) in zip([(100,76),(225,76),(225,134),(100,134)],[(225,76),(225,134),(100,134),(100,76)]):
  item=p.PCB_SHAPE(board)
  item.SetShape(p.SHAPE_T_SEGMENT);item.SetStart(xy(*a));item.SetEnd(xy(*b))
  item.SetLayer(p.Edge_Cuts);item.SetWidth(MM(0.05));board.Add(item)
 # Named, explicit front/back copper current and Kelvin paths.
 # For connector PTH J1 / J2, pin 2 is +5 mm in X, not Y.
 track(board,"SRC_PLUS",[pos(board,"J1","1"),(110,84),(130,84),pos(board,"F1","1")],p.F_Cu,0.65)
 track(board,"FUSED_PLUS",[pos(board,"F1","2"),pos(board,"J3","1")],p.F_Cu,0.65)
 track(board,"ADA_OUT",[pos(board,"J3","2"),(174,95),(176,98),pos(board,"R1","1")],p.F_Cu,0.6)
 track(board,"LOAD_PLUS",[pos(board,"R1","4"),(187,103.5),(196,103.5),
                            (196,90),pos(board,"J2","1")],p.F_Cu,0.65)
 # B.Cu return bypasses the two-terminal input connector and shunt sense pins.
 track(board,"RETURN",[pos(board,"J1","2"),(115,129),(214,129),
                        (214,94),(207,94),pos(board,"J2","2")],p.B_Cu,0.65)
 track(board,"RETURN",[pos(board,"J4","2"),(189,112.54),(189,129)],p.B_Cu,0.3)
 track(board,"RETURN",[pos(board,"J6","2"),(195,129)],p.B_Cu,0.3)
 track(board,"RETURN",[pos(board,"TP4","1"),(214,129)],p.B_Cu,0.3)
 # Load-voltage sense taps, kept away from R1 and J2 return (PTH pad 2).
 track(board,"LOAD_PLUS",[pos(board,"J2","1"),(199,90),(199,105),
                           (195,105),pos(board,"J4","1")],p.F_Cu,0.25)
 track(board,"LOAD_PLUS",[pos(board,"J4","1"),(204,110),(204,122),
                           pos(board,"J6","1")],p.F_Cu,0.25)
 track(board,"LOAD_PLUS",[pos(board,"TP3","1"),(207,105),(199,105)],p.F_Cu,0.25)
 # Kelvin reference pads 2 and 3 never carry the main current.
 track(board,"REF_SENSE_P",[pos(board,"R1","2"),(171,105),
                            pos(board,"TP1","1")],p.F_Cu,0.2)
 track(board,"REF_SENSE_P",[pos(board,"TP1","1"),pos(board,"J5","1")],p.B_Cu,0.2)
 track(board,"REF_SENSE_N",[pos(board,"R1","3"),(186,98)],p.F_Cu,0.2)
 via(board,"REF_SENSE_N",(186,98))
 track(board,"REF_SENSE_N",[(186,98),(186,116),pos(board,"TP2","1"),
                            (162,116),pos(board,"J5","2")],p.B_Cu,0.2)
 add_text(board,"HS 5V WITNESS v0",163,78,1.0)
 add_text(board,"0.5A MAX TEST ONLY",162,132,0.82)
 board.BuildConnectivity()
 return board
def main():
 board=build()
 p.SaveBoard(str(ROOT/(NAME+".kicad_pcb")),board)
 for ref in ("J1","F1","J3","R1","J2","J4","J5","J6"):
  print(ref,[(pd.GetNumber(),pd.GetNetname(),(pd.GetPosition().x/1e6,pd.GetPosition().y/1e6))
        for pd in board.FindFootprintByReference(ref).Pads()])
 print("WROTE",ROOT/(NAME+".kicad_pcb"))
if __name__=="__main__":main()
