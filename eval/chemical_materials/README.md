# Hardware Splicer — chemical and material evaluation recipes

Run all commands from the repository root. The deterministic material,
mechanical and electrical scenarios require no optional scientific models.

    PYTHONPATH=src python eval/chemical_materials/prusa_enclosure_screen_v1.py
    PYTHONPATH=src python eval/chemical_materials/three_layer_enclosure_v1.py

For actual supplier-data provenance, download the original Prusa ASA and PC
Blend PDFs to a private scratch folder with the exact names
prusament_asa.pdf and prusament_pc_blend.pdf. Pinned URLs and SHA256 are in
prusa_enclosure_screen_v1.py. Never check the original PDFs into git.

    PYTHONPATH=src python eval/chemical_materials/verify_prusa_tds.py /path/to/pdf_directory
    PYTHONPATH=src python eval/chemical_materials/registered_pdf_end_to_end.py /path/to/pdf_directory
    PYTHONPATH=src python eval/chemical_materials/registered_three_layer_end_to_end.py /path/to/pdf_directory

The source verifier requires the exact original PDF SHA256 and page-2 ISO75 HDT
values. A manufacturer PDF update intentionally fails until its provenance
is re-reviewed. The source workflow stores claims at proposed authority on
an isolated temporary MachineProject/ProjectStore and does not upgrade them.

The 11 three-layer scenarios are hand-authored software tests with synthetic
STEP Cartesian-point geometry and a synthetic logical electrical net, NOT
independent product-design validation. Passing does not establish real
temperature limits, structural fitness, insulation, flame resistance,
manufacturability or release authorization.
