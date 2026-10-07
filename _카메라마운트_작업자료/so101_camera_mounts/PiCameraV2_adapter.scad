// Millimetres. Dimensional prototype v0.1; physical fit not tested.
// Select part="plate" or part="spacer". Print one plate and four spacers.
// Requires the official SO101 hex-nut wrist camera bracket, not included.
part = "plate";
$fn = 96;
bracket_pitch = 27;
camera_pitch_x = 21;
camera_pitch_y = 12.5;
hole_diameter = 2.2;
plate_size = 35;
plate_thickness = 3;
relief_diameter = 18;
spacer_height = 5;
spacer_outer_diameter = 5;

module through_hole(x, y, h) {
    translate([x, y, -0.1]) cylinder(h=h+0.2, d=hole_diameter);
}

module adapter() {
    difference() {
        translate([-plate_size/2, -plate_size/2, 0])
            cube([plate_size, plate_size, plate_thickness]);
        for (x=[-bracket_pitch/2, bracket_pitch/2])
            for (y=[-bracket_pitch/2, bracket_pitch/2])
                through_hole(x, y, plate_thickness);
        for (x=[-camera_pitch_x/2, camera_pitch_x/2])
            for (y=[-camera_pitch_y/2, camera_pitch_y/2])
                through_hole(x, y, plate_thickness);
        translate([0, 0, -0.1]) cylinder(h=plate_thickness+0.2, d=relief_diameter);
    }
}

module spacer() {
    difference() {
        cylinder(h=spacer_height, d=spacer_outer_diameter);
        through_hole(0, 0, spacer_height);
    }
}

if (part == "plate") adapter();
else if (part == "spacer") spacer();
