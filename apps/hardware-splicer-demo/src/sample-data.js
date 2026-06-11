export const demoProjects = [
  {
    "id": "plant",
    "name": "Desk plant watering (brief)",
    "archetype": "automatic_watering",
    "goal": "Build a small automatic plant watering device from cheap or salvaged parts. It should read soil moisture and run a mini pump briefly when the plant is dry.",
    "level": "control_safety_project_package",
    "authorityScore": 0.52,
    "planningConfidence": 0.82,
    "claimable": true,
    "simulationReady": false,
    "releaseReady": false,
    "production": {
      "score": 0.595,
      "band": "control safety planning",
      "gatesPassed": 4,
      "gatesTotal": 9,
      "gaps": [
        "mechanical_release",
        "robotics_actuation_release",
        "integrated_bench",
        "field_validation",
        "release_review"
      ],
      "blockers": [
        "Run controlled mechanical bench fit/load/motion tests.",
        "Run controlled robotics bench tests: first motion, load/current, stall/limit, cycle, and thermal observations.",
        "Layer not closed: integrated_bench_ready."
      ]
    },
    "functionalDelivery": {
      "score": 90.9,
      "grade": "A"
    },
    "nextLevel": "production_ready_project_package",
    "claimBoundary": "Control stack is coherent. Bench evidence and reviewed release scope are still required.",
    "missingInfo": [
      "mechanical_release",
      "robotics_actuation_release",
      "integrated_bench",
      "field_validation",
      "release_review"
    ],
    "margins": [
      {
        "label": "current margin",
        "value": "1.526x",
        "width": "64%"
      },
      {
        "label": "runtime margin",
        "value": "6.098x",
        "width": "92%"
      },
      {
        "label": "functional delivery",
        "value": "90.9%",
        "width": "88%"
      }
    ],
    "subsystems": [
      {
        "id": "circuit",
        "label": "Circuit",
        "level": "compiler-verified DRC",
        "ready": true
      },
      {
        "id": "mechanical",
        "label": "Mechanical",
        "level": "candidate geometry",
        "ready": false
      },
      {
        "id": "robotics_actuation",
        "label": "Actuation",
        "level": "drive matched",
        "ready": false
      },
      {
        "id": "robotics_simulation",
        "label": "Simulation",
        "level": "evidence blocked",
        "ready": true
      },
      {
        "id": "robotics_platform",
        "label": "Platform",
        "level": "control safety architecture",
        "ready": true
      },
      {
        "id": "mechatronics",
        "label": "Mechatronics",
        "level": "partial trace",
        "ready": false
      }
    ],
    "evidenceRequests": [
      {
        "id": "measurement",
        "label": "Measured geometry capture",
        "unlocks": "mechanical authority"
      },
      {
        "id": "integrated_bench",
        "label": "Integrated bench capture",
        "unlocks": "simulation/bench authority"
      },
      {
        "id": "release_review",
        "label": "Reviewed scoped release",
        "unlocks": "production package claim"
      }
    ],
    "artifacts": [
      {
        "name": "PROJECT_INTAKE.json",
        "role": "normalized user brief"
      },
      {
        "name": "PRODUCTION_RELEASE_METRICS.json",
        "role": "weighted release gates"
      },
      {
        "name": "FUNCTIONAL_DELIVERY.json",
        "role": "honest fab delivery score"
      },
      {
        "name": "build_compilation/main_ctrl_build.kicad_pcb",
        "role": "DRC-clean KiCad PCB"
      }
    ]
  },
  {
    "id": "plant_release",
    "name": "Desk plant watering (evidence pack)",
    "archetype": "automatic_watering",
    "goal": "Same plant watering project with measured geometry, bench captures, field validation, and reviewed release scope attached.",
    "level": "production_ready_project_package",
    "authorityScore": 1.0,
    "planningConfidence": 0.95,
    "claimable": true,
    "simulationReady": true,
    "releaseReady": true,
    "production": {
      "score": 1.0,
      "band": "production release",
      "gatesPassed": 9,
      "gatesTotal": 9,
      "gaps": [],
      "blockers": []
    },
    "functionalDelivery": {
      "score": 90.9,
      "grade": "A"
    },
    "nextLevel": "field_validated_project_package",
    "claimBoundary": "Evidence-backed scoped release is closed.",
    "missingInfo": [],
    "margins": [
      {
        "label": "current margin",
        "value": "1.526x",
        "width": "64%"
      },
      {
        "label": "runtime margin",
        "value": "6.098x",
        "width": "92%"
      },
      {
        "label": "functional delivery",
        "value": "90.9%",
        "width": "88%"
      }
    ],
    "subsystems": [
      {
        "id": "circuit",
        "label": "Circuit",
        "level": "compiler-verified DRC",
        "ready": true
      },
      {
        "id": "mechanical",
        "label": "Mechanical",
        "level": "measured release",
        "ready": true
      },
      {
        "id": "robotics_actuation",
        "label": "Actuation",
        "level": "bench release",
        "ready": true
      },
      {
        "id": "robotics_simulation",
        "label": "Simulation",
        "level": "cleared",
        "ready": true
      },
      {
        "id": "robotics_platform",
        "label": "Platform",
        "level": "control safety architecture",
        "ready": true
      },
      {
        "id": "mechatronics",
        "label": "Mechatronics",
        "level": "integration trace closed",
        "ready": true
      }
    ],
    "evidenceRequests": [
      {
        "id": "measurement",
        "label": "Measured geometry capture",
        "unlocks": "mechanical authority"
      },
      {
        "id": "integrated_bench",
        "label": "Integrated bench capture",
        "unlocks": "simulation/bench authority"
      },
      {
        "id": "release_review",
        "label": "Reviewed scoped release",
        "unlocks": "production package claim"
      }
    ],
    "artifacts": [
      {
        "name": "PROJECT_INTAKE.json",
        "role": "normalized user brief"
      },
      {
        "name": "PRODUCTION_RELEASE_METRICS.json",
        "role": "weighted release gates"
      },
      {
        "name": "FUNCTIONAL_DELIVERY.json",
        "role": "honest fab delivery score"
      },
      {
        "name": "build_compilation/main_ctrl_build.kicad_pcb",
        "role": "DRC-clean KiCad PCB"
      }
    ]
  },
  {
    "id": "rover",
    "name": "Salvaged floor rover",
    "archetype": "rover",
    "goal": "Build a small RC rover from an ESP32, two DC gear motors, a front range sensor, and a printed chassis.",
    "level": "control_safety_project_package",
    "authorityScore": 0.52,
    "planningConfidence": 0.78,
    "claimable": true,
    "simulationReady": false,
    "releaseReady": false,
    "production": {
      "score": 0.595,
      "band": "control safety planning",
      "gatesPassed": 4,
      "gatesTotal": 9,
      "gaps": [
        "mechanical_release",
        "robotics_actuation_release",
        "integrated_bench",
        "field_validation",
        "release_review"
      ],
      "blockers": [
        "Run controlled mechanical bench fit/load/motion tests.",
        "Run controlled robotics bench tests: first motion, load/current, stall/limit, cycle, and thermal observations.",
        "Layer not closed: integrated_bench_ready."
      ]
    },
    "functionalDelivery": {
      "score": 90.9,
      "grade": "A"
    },
    "nextLevel": "simulation_bench_project_package",
    "claimBoundary": "Drive and safety architecture are coherent. Release blocked until measurements and bench evidence are attached.",
    "missingInfo": [
      "mechanical_release",
      "robotics_actuation_release",
      "integrated_bench",
      "field_validation",
      "release_review"
    ],
    "margins": [
      {
        "label": "current margin",
        "value": "1.35x",
        "width": "58%"
      },
      {
        "label": "runtime margin",
        "value": "5.928x",
        "width": "90%"
      },
      {
        "label": "wheel speed margin",
        "value": "1.664x",
        "width": "70%"
      }
    ],
    "subsystems": [
      {
        "id": "circuit",
        "label": "Circuit",
        "level": "compiler-verified DRC",
        "ready": true
      },
      {
        "id": "mechanical",
        "label": "Mechanical",
        "level": "reference geometry",
        "ready": false
      },
      {
        "id": "robotics_actuation",
        "label": "Actuation",
        "level": "electrical drive matched",
        "ready": true
      },
      {
        "id": "robotics_simulation",
        "label": "Simulation",
        "level": "physical evidence blocked",
        "ready": false
      },
      {
        "id": "robotics_platform",
        "label": "Platform",
        "level": "control safety architecture",
        "ready": true
      },
      {
        "id": "mechatronics",
        "label": "Mechatronics",
        "level": "partial trace",
        "ready": false
      }
    ],
    "evidenceRequests": [
      {
        "id": "measurement",
        "label": "Measured chassis geometry",
        "unlocks": "mechanical authority"
      },
      {
        "id": "motion_bench",
        "label": "First-motion/current bench",
        "unlocks": "controlled rover motion"
      },
      {
        "id": "release_review",
        "label": "Reviewed scoped release",
        "unlocks": "production package claim"
      }
    ],
    "artifacts": [
      {
        "name": "PROJECT_INTAKE.json",
        "role": "normalized user brief"
      },
      {
        "name": "PRODUCTION_RELEASE_METRICS.json",
        "role": "weighted release gates"
      },
      {
        "name": "ROBOTICS_SIMULATION.json",
        "role": "runtime and drive margins"
      }
    ]
  }
];
