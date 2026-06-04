module assembly_preview() {
  rod_d = 8.0;
  rod_spacing = 40.0;
  rod_len = 250.0;
  
  module rods(){
    color([0.7,0.7,0.7]) {
      translate([0, -rod_spacing/2, 0]) rotate([0,90,0]) cylinder(h=rod_len, d=rod_d, center=false);
      translate([0,  rod_spacing/2, 0]) rotate([0,90,0]) cylinder(h=rod_len, d=rod_d, center=false);
    }
  }
  rods();
  color([0.3,0.3,0.3]) translate([0, -25, -10]) cube([rod_len, 20, 20], center=false);
  color([0.3,0.3,0.3]) translate([0,  5, -10]) cube([rod_len, 20, 20], center=false);
  color([0.1,0.1,0.1]) translate([0,0,rod_d/2]) cube([rod_len, 2, 1], center=false);
  // Import and position printable parts manually if you want a full assembly preview.
}
assembly_preview();
